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

Hard rules (do not relax):
  - Never rmtree a directory; always per-file unlink + rmdir empty leaves.
  - Never delete a file the registry doesn't show us having deployed.
  - Never deploy a conflict=True skill (skipped silently from add/update).
  - Never deploy a retired skill.
  - Never write outside ~/.claude/ in guest mode.
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
_DEPLOYMENT_LOG = _REPO_ROOT / "state" / "deployment_log.jsonl"


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


def _append_deployment_log(entry: dict, log_path: Path = _DEPLOYMENT_LOG) -> None:
    """Append a single JSON object as one line to the deployment log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, sort_keys=True) + "\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


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
