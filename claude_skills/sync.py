"""Three-pass deploy loop: sync this system's subscribed skills + CLAUDE.md.

The three passes are:

  1. Plan: filter the registry to subscribed, non-conflict, non-retired
     skills; walk the target commands_target dir; classify each skill as
     add / update / unchanged / remove. Render the would-be CLAUDE.md.
  2. Render: when --apply is not set, return the plan dict (and unified
     diffs for diff mode) without touching disk.
  3. Apply: per-file copy of new/updated skills, per-file unlink of
     skills the registry says we previously deployed but are no longer
     subscribed; write CLAUDE.md via write_managed; update last_deploy
     and append to deployment_log.jsonl.

Per-repo runtime mirroring (Step 1 of the convention pivot):

After the main user-global commands_target deploy, ``sync()`` also
mirrors each subscribed skill into its **home_repo's** ``.claude/commands/``
runtime directory (so the skill is auto-loaded when the user ``cd``s
into the repo). For skills carrying a ``deploys_to_repos`` list, the
skill is additionally mirrored into each listed repo's runtime dir.

The runtime dirs are gitignored after ``migrate-domain-skills --apply``
(Step 2), so this never produces commits — it just keeps the runtime
artifact in sync with the source-of-truth at ``agent-io/skills/``.

Hard rules (do not relax):
  - Never rmtree a directory; always per-file unlink + rmdir empty leaves.
  - Never delete a file the registry doesn't show us having deployed.
  - Never deploy a conflict=True skill (skipped silently from add/update).
  - Never deploy a retired skill.
  - Never write outside ~/.claude/ in guest mode (per-repo runtime
    mirroring is also disabled in guest mode, by definition).
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from claude_skills.claude_md import (
    get_tier1,
    get_tier2,
    parse_managed,
    render_managed,
    write_managed,
)
from claude_skills.manifest import compute_manifest_hash, list_skill_units
from claude_skills.registry import load_registry, save_registry
from claude_skills.systems import load_systems


_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DEPLOYMENT_LOG = _REPO_ROOT / "state" / "deployment_log.jsonl"
_DEPLOYMENT_LOG_ENV = "CLAUDE_SKILLS_DEPLOYMENT_LOG_PATH"


def _deployment_log_path() -> Path:
    """Resolve the deployment log path, honoring the env override (used by tests)."""
    override = os.environ.get(_DEPLOYMENT_LOG_ENV)
    if override:
        return Path(override)
    return _DEFAULT_DEPLOYMENT_LOG


# Back-compat: keep the module-level name; tests can override via env var.
_DEPLOYMENT_LOG = _DEFAULT_DEPLOYMENT_LOG


def _expand(path_str: str) -> Path:
    """Expand ~ and resolve an absolute path."""
    return Path(path_str).expanduser().resolve()


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_under(child: Path, parent: Path) -> bool:
    """Return True if child is parent or a descendant of parent."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _filter_subscribed(skills: dict, sys_info: dict) -> dict:
    """Filter the registry to skills this system subscribes to.

    Apply, in order:
      - retired False
      - conflict False
      - scope ∈ subscriptions.scopes
      - subscriptions.domains == ['*'] OR skill.domain ∈ subscriptions.domains
        (only meaningful for domain-scoped skills)
      - if subscriptions.requires_role is set, the system's hardware roles
        must include that role
    """
    subs = sys_info.get("subscriptions", {}) or {}
    sub_scopes = subs.get("scopes", []) or []
    sub_domains = subs.get("domains", []) or []
    requires_role = subs.get("requires_role")

    # If this machine doesn't have the required role, deploy nothing.
    if requires_role:
        hardware = sys_info.get("hardware") or {}
        roles = hardware.get("roles") or []
        if requires_role not in roles:
            return {}

    out = {}
    for key, entry in skills.items():
        if entry.get("retired"):
            continue
        if entry.get("conflict"):
            continue
        scope = entry.get("scope", "")
        if scope not in sub_scopes:
            continue
        if scope == "domain":
            if sub_domains != ["*"]:
                if entry.get("domain") not in sub_domains:
                    continue
        out[key] = entry
    return out


def _build_target_manifest(commands_target: Path) -> dict[str, str]:
    """Walk commands_target and return {skill_key: manifest_hash}.

    Each anchor .md file is treated as a skill unit (the sibling dir is
    handled inside compute_manifest_hash).
    """
    if not commands_target.is_dir():
        return {}
    anchors = list_skill_units(commands_target)
    return {a.stem: compute_manifest_hash(a) for a in anchors}


def _classify_skills(
    subscribed: dict, target_manifest: dict[str, str], registry_skills: dict, sys_name: str
) -> dict:
    """Compute add / update / unchanged / remove sets.

    add        — subscribed but not present at target.
    update     — subscribed and present, hash differs.
    unchanged  — subscribed and present, hash matches.
    remove     — present at target AND registry says we deployed it AND
                 it's no longer subscribed. We never remove files we
                 don't have a deploy record for.
    """
    add: list[str] = []
    update: list[str] = []
    unchanged: list[str] = []
    remove: list[str] = []

    subscribed_keys = set(subscribed.keys())
    target_keys = set(target_manifest.keys())

    for key in sorted(subscribed_keys):
        new_hash = subscribed[key].get("manifest_hash", "")
        if key not in target_keys:
            add.append(key)
        else:
            if target_manifest[key] == new_hash:
                unchanged.append(key)
            else:
                update.append(key)

    # Removal candidates: in target but not subscribed.
    for key in sorted(target_keys - subscribed_keys):
        # Only remove if the registry shows we deployed this skill to this
        # system. Without a deploy record, leave it alone (manual file).
        reg_entry = registry_skills.get(key)
        if reg_entry is None:
            continue
        last_deploy = reg_entry.get("last_deploy", {}) or {}
        if sys_name in last_deploy:
            remove.append(key)

    return {"add": add, "update": update, "unchanged": unchanged, "remove": remove}


def _render_claude_md_plan(target_path: Path, tier1: str, tier2: str) -> dict:
    """Compute the would-be ~/.claude/CLAUDE.md and the action it implies."""
    state = parse_managed(target_path)

    # Render against the existing user_additions if managed; else empty.
    user_additions = state["user_additions"] if state["is_managed"] else ""
    rendered = render_managed(tier1, tier2, user_additions=user_additions)

    # Compute hashes once for the envelope.
    from claude_skills.claude_md import _content_hash
    tier1_hash = _content_hash(tier1.strip("\n"))
    tier2_hash = _content_hash(tier2.strip("\n"))

    # Decide action.
    if state["is_pristine"]:
        action = "init"
        diff_text = ""
        diff_summary = "target file does not exist — would create"
    elif not state["is_managed"]:
        action = "refused"
        diff_text = ""
        missing = ", ".join(state["missing_sentinels"]) or "unknown"
        diff_summary = f"sentinels missing or mangled ({missing}) — pass --init-claude-md"
    else:
        existing_text = target_path.read_text(encoding="utf-8")
        if existing_text == rendered:
            action = "no-change"
        else:
            action = "update"
        diff_text = "".join(
            difflib.unified_diff(
                existing_text.splitlines(keepends=True),
                rendered.splitlines(keepends=True),
                fromfile=str(target_path),
                tofile=str(target_path) + " (new)",
            )
        )
        # Summarize per-tier change.
        t1_changed = (state["tier1_hash"] or "") != tier1_hash
        t2_changed = (state["tier2_hash"] or "") != tier2_hash
        diff_summary = (
            f"tier1: {'changed' if t1_changed else 'unchanged'}, "
            f"tier2: {'changed' if t2_changed else 'unchanged'}"
        )

    return {
        "action": action,
        "tier1_hash": tier1_hash,
        "tier2_hash": tier2_hash,
        "diff_summary": diff_summary,
        "diff": diff_text,
        "rendered": rendered,
        "state": state,
    }


def _copy_skill_unit(home_path: Path, dest_dir: Path) -> None:
    """Copy a skill unit (anchor .md + sibling dir if any) into dest_dir.

    Uses shutil.copy2 for files; for the sibling directory, copies the
    tree recursively, overwriting existing files. Never deletes anything.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Copy the anchor file.
    dest_anchor = dest_dir / home_path.name
    shutil.copy2(home_path, dest_anchor)
    # Copy the sibling dir if present.
    sibling = home_path.parent / home_path.stem
    if sibling.is_dir():
        dest_sibling = dest_dir / sibling.name
        # Per-file recursive copy, overwriting files.
        for src_file in sibling.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(sibling)
            dst_file = dest_sibling / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)


def _remove_skill_unit(commands_target: Path, skill_key: str) -> None:
    """Remove a skill unit from commands_target (anchor + sibling dir).

    Per-file unlink + rmdir of empty leaves. Never rmtree.
    """
    anchor = commands_target / f"{skill_key}.md"
    if anchor.is_file():
        anchor.unlink()
    sibling = commands_target / skill_key
    if sibling.is_dir():
        # Walk bottom-up, unlink files, then rmdir empty dirs.
        for path in sorted(sibling.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    # Non-empty (shouldn't happen after unlinking files); leave it.
                    pass
        try:
            sibling.rmdir()
        except OSError:
            pass


def _append_deployment_log(entry: dict, log_path: Path | None = None) -> None:
    """Append a single JSON object as one line to the deployment log.

    Honors the ``CLAUDE_SKILLS_DEPLOYMENT_LOG_PATH`` env var when ``log_path``
    is not given (used by tests so they don't pollute the real log).
    """
    if log_path is None:
        log_path = _deployment_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, sort_keys=True) + "\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


# ---- per-repo runtime mirroring helpers ----------------------------------


def _build_repo_root_index() -> dict[str, Path]:
    """Return ``{repo_name: repo_root_path}`` for known home repos.

    Mirrors the discovery in ``inventory.py``: ClaudeCommands (this repo)
    and AIAssistant (special-cased) plus every project in
    project_registry.yaml that resolves to a repo_path.
    """
    import yaml

    out: dict[str, Path] = {}
    out["ClaudeCommands"] = _REPO_ROOT
    aia_root = Path.home() / "Dropbox" / "Projects" / "AIAssistant"
    if aia_root.is_dir():
        out["AIAssistant"] = aia_root

    proj_path_env = os.environ.get("CLAUDE_SKILLS_PROJECT_REGISTRY_PATH")
    proj_path = (
        Path(proj_path_env)
        if proj_path_env
        else aia_root / "state" / "project_registry.yaml"
    )
    if not proj_path.is_file():
        return out
    try:
        with open(proj_path) as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return out
    projects = data.get("projects", {}) or {}

    def _resolve(pid: str) -> str | None:
        visited: set[str] = set()
        cur = pid
        while cur and cur not in visited:
            visited.add(cur)
            entry = projects.get(cur, {}) or {}
            rp = entry.get("repo_path")
            if rp:
                return rp
            cur = entry.get("parent")
        return None

    for pid, info in projects.items():
        name = (info or {}).get("name") or pid
        if name in out:
            continue
        rp = _resolve(pid)
        if not rp:
            continue
        path = Path(rp).expanduser()
        if path.is_dir():
            out[name] = path
    return out


def _expand_deploys_targets(
    deploys_to_repos: list[str], repo_index: dict[str, Path]
) -> list[str]:
    """Expand ``["*"]`` to every known repo; pass-through otherwise."""
    if not deploys_to_repos:
        return []
    if "*" in deploys_to_repos:
        return sorted(repo_index.keys())
    seen: set[str] = set()
    out: list[str] = []
    for r in deploys_to_repos:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _runtime_targets_for_skill(
    entry: dict, repo_index: dict[str, Path]
) -> list[tuple[str, Path]]:
    """Return list of (repo_name, runtime_dir) for a single skill entry.

    Each subscribed skill mirrors into:
      - its home_repo's ``.claude/commands/``
      - every repo listed in ``deploys_to_repos`` (after wildcard expansion)
    """
    targets: list[tuple[str, Path]] = []
    home_repo = entry.get("home_repo") or ""
    if home_repo and home_repo in repo_index:
        targets.append((home_repo, repo_index[home_repo] / ".claude" / "commands"))
    drepos = _expand_deploys_targets(
        entry.get("deploys_to_repos") or [], repo_index
    )
    for r in drepos:
        if r == home_repo:
            # Self-clobber — refuse silently in runtime mirroring.
            continue
        if r not in repo_index:
            continue
        targets.append((r, repo_index[r] / ".claude" / "commands"))
    return targets


def _mirror_to_runtime_dirs(
    subscribed: dict,
    registry_skills: dict,
    repo_index: dict[str, Path],
    plan: dict,
) -> dict:
    """Per-repo runtime mirror pass. Returns a dict {repo_name: stats}.

    For each subscribed skill, ensures the home_repo's
    ``.claude/commands/`` (and each declared deploys_to_repos target)
    contains an up-to-date copy. Also removes anchors the registry
    previously deployed to that repo if the skill is no longer subscribed
    or no longer targets that repo.
    """
    runtime_stats: dict[str, dict] = {}

    # Build {repo_name: {skill_key: entry}} for currently-subscribed skills.
    by_repo: dict[str, dict[str, dict]] = {}
    for key, entry in subscribed.items():
        for repo_name, _runtime_dir in _runtime_targets_for_skill(entry, repo_index):
            by_repo.setdefault(repo_name, {})[key] = entry

    # Also track repos that may need REMOVALS (skill was previously
    # deployed via runtime mirror but no longer subscribed/targeted).
    for key, entry in registry_skills.items():
        for repo_name in (entry.get("last_runtime_deploy") or {}).keys():
            by_repo.setdefault(repo_name, {})

    for repo_name in sorted(by_repo.keys()):
        repo_root = repo_index.get(repo_name)
        if repo_root is None:
            continue
        runtime_dir = repo_root / ".claude" / "commands"
        skills_for_repo = by_repo[repo_name]

        # Walk current state of runtime dir.
        target_manifest = _build_target_manifest(runtime_dir)

        add: list[str] = []
        update: list[str] = []
        unchanged: list[str] = []
        remove: list[str] = []

        for key in sorted(skills_for_repo.keys()):
            new_hash = skills_for_repo[key].get("manifest_hash", "")
            if key not in target_manifest:
                add.append(key)
            elif target_manifest[key] == new_hash:
                unchanged.append(key)
            else:
                update.append(key)

        # Removal: registry says we previously runtime-deployed it but
        # this skill no longer targets this repo.
        for key, entry in registry_skills.items():
            last = (entry.get("last_runtime_deploy") or {}).get(repo_name)
            if not last:
                continue
            if key in skills_for_repo:
                continue
            remove.append(key)

        runtime_stats[repo_name] = {
            "repo_path": str(repo_root),
            "add": add,
            "update": update,
            "unchanged": unchanged,
            "remove": sorted(set(remove)),
            "errors": [],
        }

        # ---- APPLY ----
        runtime_dir.mkdir(parents=True, exist_ok=True)
        for key in add + update:
            entry = skills_for_repo[key]
            home_path = Path(entry["home_path"])
            if not home_path.is_file():
                runtime_stats[repo_name]["errors"].append(
                    f"missing home_path for {key}: {home_path}"
                )
                continue
            try:
                _copy_skill_unit(home_path, runtime_dir)
            except Exception as exc:
                runtime_stats[repo_name]["errors"].append(
                    f"copy failed for {key}: {exc}"
                )

        for key in runtime_stats[repo_name]["remove"]:
            try:
                _remove_skill_unit(runtime_dir, key)
            except Exception as exc:
                runtime_stats[repo_name]["errors"].append(
                    f"remove failed for {key}: {exc}"
                )

        # Update last_runtime_deploy.
        now = _now_iso()
        for key in add + update:
            entry = registry_skills.get(key)
            if entry is None:
                continue
            lrd = entry.setdefault("last_runtime_deploy", {})
            lrd[repo_name] = {
                "hash": entry.get("manifest_hash", ""),
                "ts": now,
                "action": "add" if key in add else "update",
            }
        for key in runtime_stats[repo_name]["remove"]:
            entry = registry_skills.get(key)
            if entry is None:
                continue
            lrd = entry.setdefault("last_runtime_deploy", {})
            lrd.pop(repo_name, None)

    return runtime_stats


def _plan_runtime_targets(
    subscribed: dict, registry_skills: dict, repo_index: dict[str, Path]
) -> dict:
    """Dry-run version of ``_mirror_to_runtime_dirs`` (no disk writes)."""
    by_repo: dict[str, dict[str, dict]] = {}
    for key, entry in subscribed.items():
        for repo_name, _ in _runtime_targets_for_skill(entry, repo_index):
            by_repo.setdefault(repo_name, {})[key] = entry
    for key, entry in registry_skills.items():
        for repo_name in (entry.get("last_runtime_deploy") or {}).keys():
            by_repo.setdefault(repo_name, {})

    out: dict[str, dict] = {}
    for repo_name, skills_for_repo in by_repo.items():
        repo_root = repo_index.get(repo_name)
        if repo_root is None:
            continue
        runtime_dir = repo_root / ".claude" / "commands"
        target_manifest = _build_target_manifest(runtime_dir)

        add: list[str] = []
        update: list[str] = []
        unchanged: list[str] = []
        remove: list[str] = []

        for key in sorted(skills_for_repo.keys()):
            new_hash = skills_for_repo[key].get("manifest_hash", "")
            if key not in target_manifest:
                add.append(key)
            elif target_manifest[key] == new_hash:
                unchanged.append(key)
            else:
                update.append(key)

        for key, entry in registry_skills.items():
            last = (entry.get("last_runtime_deploy") or {}).get(repo_name)
            if not last:
                continue
            if key in skills_for_repo:
                continue
            remove.append(key)

        out[repo_name] = {
            "repo_path": str(repo_root),
            "add": add,
            "update": update,
            "unchanged": unchanged,
            "remove": sorted(set(remove)),
            "errors": [],
        }
    return out


def sync(
    system_name: str,
    apply: bool = False,
    init_claude_md: bool = False,
) -> dict:
    """Sync this system's subscribed skills + CLAUDE.md to its targets.

    Returns a plan dict (see module docstring / task spec for shape).
    Setting apply=False (the default) makes this a dry run.
    """
    systems = load_systems()
    if system_name not in systems:
        raise ValueError(f"unknown system: {system_name!r}")

    sys_info = systems[system_name]
    mode = sys_info.get("mode", "owned")

    claude_md_target = _expand(sys_info.get("claude_md_target", "~/.claude/CLAUDE.md"))
    commands_target = _expand(sys_info.get("commands_target", "~/.claude/commands/"))
    tier2_source = sys_info.get("tier2_source")

    # Guest-mode guard: refuse any target outside ~/.claude/.
    if mode == "guest":
        home_claude = (Path.home() / ".claude").resolve()
        for label, target in (
            ("claude_md_target", claude_md_target),
            ("commands_target", commands_target),
        ):
            if not _is_under(target, home_claude):
                raise PermissionError(
                    f"guest mode: {label}={target} resolves outside {home_claude}"
                )

    # Load registry once.
    registry = load_registry()
    registry_skills = registry.get("skills", {}) or {}

    # Filter by subscription.
    subscribed = _filter_subscribed(registry_skills, sys_info)

    # Walk target.
    target_manifest = _build_target_manifest(commands_target)

    # Classify.
    classification = _classify_skills(subscribed, target_manifest, registry_skills, system_name)

    # CLAUDE.md plan.
    tier1 = get_tier1()
    tier2 = get_tier2(system_name, tier2_source=tier2_source)
    cmd_md = _render_claude_md_plan(claude_md_target, tier1, tier2)

    # Per-repo runtime mirror plan (always computed; only applied in
    # owned mode and when apply=True).
    repo_index: dict[str, Path] = {}
    runtime_plan: dict[str, dict] = {}
    if mode != "guest":
        repo_index = _build_repo_root_index()
        runtime_plan = _plan_runtime_targets(subscribed, registry_skills, repo_index)

    plan: dict = {
        "system": system_name,
        "mode": mode,
        "claude_md": {
            "action": cmd_md["action"],
            "tier1_hash": cmd_md["tier1_hash"],
            "tier2_hash": cmd_md["tier2_hash"],
            "diff_summary": cmd_md["diff_summary"],
            "diff": cmd_md["diff"],
        },
        "skills": classification,
        "runtime_repos": runtime_plan,
        "applied": False,
        "errors": [],
    }

    if not apply:
        return plan

    # ---- APPLY PATH ----

    # CLAUDE.md write. If it would refuse and init_claude_md not given,
    # record an error (but still proceed with skill deploy — they're
    # independent).
    cmd_md_action = cmd_md["action"]
    cmd_md_result: dict | None = None
    if cmd_md_action == "refused" and not init_claude_md:
        plan["errors"].append(
            f"CLAUDE.md refused: {cmd_md['diff_summary']}. "
            "Pass --init-claude-md to overwrite."
        )
        plan["claude_md"]["action"] = "refused"
    elif cmd_md_action in ("init", "update", "no-change", "refused"):
        # init covers both pristine and "init=True over mangled".
        cmd_md_result = write_managed(
            claude_md_target,
            tier1,
            tier2,
            init=init_claude_md or cmd_md_action == "init",
            dry_run=False,
        )
        plan["claude_md"]["action"] = cmd_md_result["action"]
        if cmd_md_result["action"] == "refused":
            plan["errors"].append(
                f"CLAUDE.md refused: {cmd_md_result.get('reason', 'unknown')}"
            )

    # Skill deploy: add + update.
    deployed_actions: list[tuple[str, str]] = []  # (action, key) for log
    commands_target.mkdir(parents=True, exist_ok=True)

    for key in classification["add"] + classification["update"]:
        entry = subscribed[key]
        home_path = Path(entry["home_path"])
        if not home_path.is_file():
            plan["errors"].append(f"missing home_path for {key}: {home_path}")
            continue
        try:
            _copy_skill_unit(home_path, commands_target)
        except Exception as exc:
            plan["errors"].append(f"copy failed for {key}: {exc}")
            continue
        action = "add" if key in classification["add"] else "update"
        deployed_actions.append((action, key))

    # Skill removal.
    for key in classification["remove"]:
        try:
            _remove_skill_unit(commands_target, key)
        except Exception as exc:
            plan["errors"].append(f"remove failed for {key}: {exc}")
            continue
        deployed_actions.append(("remove", key))

    # Update last_deploy in registry for everything we touched.
    now = _now_iso()
    for action, key in deployed_actions:
        entry = registry_skills.get(key)
        if entry is None:
            continue
        last_deploy = entry.setdefault("last_deploy", {})
        if action == "remove":
            # Drop the deploy record for this system; the file no longer exists.
            last_deploy.pop(system_name, None)
        else:
            last_deploy[system_name] = {
                "hash": entry.get("manifest_hash", ""),
                "ts": now,
                "action": action,
            }
        # Maintain deploys_to_machines as a deduplicated sorted list.
        machines = set(entry.get("deploys_to_machines") or [])
        if action == "remove":
            machines.discard(system_name)
        else:
            machines.add(system_name)
        entry["deploys_to_machines"] = sorted(machines)

    # ---- Per-repo runtime mirror (Step 1 of convention pivot) ----
    # Mirrors each subscribed skill into its home_repo's runtime
    # ``.claude/commands/`` dir (and into any ``deploys_to_repos``
    # targets). Skipped in guest mode by design.
    runtime_results: dict[str, dict] = {}
    if mode != "guest":
        runtime_results = _mirror_to_runtime_dirs(
            subscribed, registry_skills, repo_index, plan
        )
        plan["runtime_repos"] = {
            name: {k: v for k, v in stats.items() if k != "errors"} | {"errors": stats.get("errors", [])}
            for name, stats in runtime_results.items()
        }
        # Surface runtime errors at the top level too.
        for name, stats in runtime_results.items():
            for err in stats.get("errors") or []:
                plan["errors"].append(f"runtime[{name}]: {err}")

    # Append deployment log.
    log_entry = {
        "ts": now,
        "system": system_name,
        "action": "sync",
        "added": classification["add"],
        "updated": classification["update"],
        "removed": classification["remove"],
        "claude_md_action": plan["claude_md"]["action"],
        "hash_at_deploy": {
            key: registry_skills.get(key, {}).get("manifest_hash", "")
            for key in classification["add"] + classification["update"]
        },
        "runtime_repos": {
            name: {
                "add": stats.get("add") or [],
                "update": stats.get("update") or [],
                "remove": stats.get("remove") or [],
            }
            for name, stats in runtime_results.items()
        },
        "errors": plan["errors"],
    }
    _append_deployment_log(log_entry)

    # Save the registry (atomic).
    save_registry(registry)

    plan["applied"] = True
    return plan


# Compatibility shim: cli.py originally referenced sync_system / diff_system.
def sync_system(system_name: str, *, dry_run: bool = False, apply: bool = False) -> dict:
    """Back-compat entry point used by older callers."""
    if dry_run and apply:
        raise ValueError("sync_system: pass at most one of dry_run/apply")
    return sync(system_name, apply=apply)


def diff_system(system_name: str) -> dict:
    """Return the dry-run plan (with diffs) for a system."""
    return sync(system_name, apply=False)
