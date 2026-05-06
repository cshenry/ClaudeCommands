"""Three-pass deploy loop for ``claude-skills sync-repos``.

Companion to ``claude_skills.sync`` (which deploys to a machine's
``~/.claude/commands/`` and to per-repo ``.claude/commands/`` runtime
dirs). This module deploys universal/cross-cutting skills *into* target
repositories' ``.claude/commands/`` directories whose ``deploys_to_repos``
frontmatter explicitly lists them. Use cases: claude-web branch snapshots,
guest-mode utility libraries, narrow cross-repo sharing.

The three passes are:

  1. Plan: load registry, expand any ``deploys_to_repos == ["*"]``
     wildcards against ``project_registry.yaml``, group skills by target
     repo. Walk each target's ``.claude/commands/`` and classify per
     skill: add / update / unchanged / remove.
  2. Render: when ``--apply`` is not set, return the plan dict and
     return without touching disk.
  3. Apply: per-repo three-pass writes (copy add/update, per-file unlink
     remove), update ``last_repo_deploy[repo]``. Commit only when the
     caller passes ``commit=True`` (CLI ``--commit``); otherwise leave
     the working tree dirty for the user to handle.

Hard rules (mirrored from ``sync.py``):
  - Never rmtree a directory; always per-file unlink + rmdir empty leaves.
  - Never delete a file the registry doesn't show us having deployed.
  - Never deploy a conflict=True skill (skipped silently).
  - Never deploy a retired skill (it goes through the removal path).
  - Refuse if ``home_repo == target_repo`` (self-clobber).
  - Refuse if target repo has uncommitted changes outside
    ``.claude/commands/`` (downgraded to warning when ``--force``).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from claude_skills.manifest import compute_manifest_hash, list_skill_units
from claude_skills.registry import load_registry, save_registry


# Where to look for AIAssistant's project_registry.yaml. Same convention
# as inventory.py. Tests can override via the env var below.
_DEFAULT_PROJECT_REGISTRY = (
    Path.home() / "Dropbox" / "Projects" / "AIAssistant" / "state" / "project_registry.yaml"
)
_PROJECT_REGISTRY_ENV = "CLAUDE_SKILLS_PROJECT_REGISTRY_PATH"


def _project_registry_path() -> Path:
    """Return the path to project_registry.yaml, honoring the env override."""
    override = os.environ.get(_PROJECT_REGISTRY_ENV)
    if override:
        return Path(override)
    return _DEFAULT_PROJECT_REGISTRY


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_projects() -> dict:
    """Return projects dict from AIAssistant project_registry.yaml.

    Each entry has at minimum ``name`` and (optionally) ``repo_path``.
    """
    path = _project_registry_path()
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("projects", {}) or {}


def _resolve_repo_path_with_ancestors(project_id: str, projects: dict) -> str | None:
    """Walk parent chain to find inherited ``repo_path`` (mirrors AIAssistant)."""
    visited: set[str] = set()
    pid = project_id
    while pid and pid not in visited:
        visited.add(pid)
        entry = projects.get(pid, {}) or {}
        rp = entry.get("repo_path")
        if rp:
            return rp
        pid = entry.get("parent")
    return None


def _build_repo_index(projects: dict) -> dict[str, Path]:
    """Build {repo_name: Path} map for projects that resolve to a repo_path.

    Keys are the human-readable ``name`` field (e.g. ``AgentForge``) since
    that is what skills put in their frontmatter ``deploys_to_repos``.
    Falls back to the project_id when ``name`` is missing.
    """
    index: dict[str, Path] = {}
    for pid, info in (projects or {}).items():
        rp = _resolve_repo_path_with_ancestors(pid, projects)
        if not rp:
            continue
        repo_name = (info or {}).get("name") or pid
        index.setdefault(repo_name, Path(rp).expanduser())
    return index


def _expand_targets(
    deploys_to_repos: list[str], repo_index: dict[str, Path]
) -> list[str]:
    """Expand ``["*"]`` to all known repo names; pass-through otherwise.

    Wildcard preserves explicit list semantics: a skill with
    ``["*", "Foo"]`` resolves to every repo (Foo is implied).
    """
    if not deploys_to_repos:
        return []
    if "*" in deploys_to_repos:
        return sorted(repo_index.keys())
    # Preserve declared order, dedupe.
    seen: set[str] = set()
    out: list[str] = []
    for r in deploys_to_repos:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _git_run(
    repo_root: Path, args: list[str], *, check: bool = True
) -> subprocess.CompletedProcess:
    """Run ``git <args>`` inside ``repo_root``."""
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=check,
    )


def _is_git_worktree(repo_root: Path) -> bool:
    """Return True if ``repo_root`` is the top of a git working tree."""
    try:
        ret = _git_run(repo_root, ["rev-parse", "--show-toplevel"], check=False)
    except (OSError, FileNotFoundError):
        return False
    if ret.returncode != 0:
        return False
    return Path(ret.stdout.strip()).resolve() == repo_root.resolve()


def _has_uncommitted_outside(repo_root: Path, allowed_prefix: str) -> list[str]:
    """Return paths that are dirty in ``repo_root`` and live outside ``allowed_prefix``.

    Uses ``git status --porcelain`` and filters out untracked-ignored
    paths (lines starting with ``!!``). The ``allowed_prefix`` is
    repo-relative (e.g. ``.claude/commands/``).
    """
    if not _is_git_worktree(repo_root):
        return []
    ret = _git_run(repo_root, ["status", "--porcelain"], check=False)
    if ret.returncode != 0:
        return []
    out: list[str] = []
    for line in ret.stdout.splitlines():
        if not line:
            continue
        # Format: "XY <path>" (XY is two status chars, then space).
        # Ignored entries start with "!!"; we never see them without -i.
        path = line[3:].strip()
        # Handle rename: "old -> new" — flag both sides.
        candidates = [path]
        if " -> " in path:
            candidates = path.split(" -> ", 1)
        for cand in candidates:
            cand = cand.strip().strip('"')
            if not cand.startswith(allowed_prefix):
                out.append(cand)
                break
    return out


def _build_target_manifest(commands_dir: Path) -> dict[str, str]:
    """Walk a target ``.claude/commands/`` and return ``{skill_key: hash}``."""
    if not commands_dir.is_dir():
        return {}
    anchors = list_skill_units(commands_dir)
    return {a.stem: compute_manifest_hash(a) for a in anchors}


def _copy_skill_unit(home_path: Path, dest_dir: Path) -> list[Path]:
    """Copy a skill unit (anchor + sibling dir) into ``dest_dir``.

    Returns the list of destination file paths written/overwritten so the
    caller can stage them in git.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    # Anchor.
    dest_anchor = dest_dir / home_path.name
    shutil.copy2(home_path, dest_anchor)
    written.append(dest_anchor)
    # Sibling dir if present.
    sibling = home_path.parent / home_path.stem
    if sibling.is_dir():
        dest_sibling = dest_dir / sibling.name
        for src_file in sibling.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(sibling)
            dst_file = dest_sibling / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            written.append(dst_file)
    return written


def _remove_skill_unit(commands_dir: Path, skill_key: str) -> list[Path]:
    """Remove a skill unit. Returns paths that were removed (for git rm).

    Per-file unlink + rmdir of empty leaves. Never rmtree.
    """
    removed: list[Path] = []
    anchor = commands_dir / f"{skill_key}.md"
    if anchor.is_file():
        anchor.unlink()
        removed.append(anchor)
    sibling = commands_dir / skill_key
    if sibling.is_dir():
        for path in sorted(sibling.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                try:
                    path.unlink()
                    removed.append(path)
                except OSError:
                    pass
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            sibling.rmdir()
        except OSError:
            pass
    return removed


def _short_sha(repo_root: Path) -> str:
    """Return short HEAD sha of ``repo_root`` or empty string on failure."""
    try:
        ret = _git_run(repo_root, ["rev-parse", "--short", "HEAD"], check=False)
    except (OSError, FileNotFoundError):
        return ""
    if ret.returncode != 0:
        return ""
    return ret.stdout.strip()


def _source_repo_short_sha() -> str:
    """Return short SHA of the ClaudeCommands repo we're running from."""
    repo_root = Path(__file__).resolve().parent.parent
    return _short_sha(repo_root)


def _format_commit_message(
    added: list[str],
    updated: list[tuple[str, str, str]],  # (key, old_short, new_short)
    removed: list[str],
    source_sha: str,
) -> str:
    """Render the per-repo deploy commit message."""
    parts = ["chore: claude-skills repo deploy", ""]
    if added:
        parts.append("Added: " + ", ".join(added))
    if updated:
        upd_strs = [f"{k} ({old} -> {new})" for k, old, new in updated]
        parts.append("Updated: " + ", ".join(upd_strs))
    if removed:
        parts.append("Removed: " + ", ".join(removed))
    if source_sha:
        parts.append("")
        parts.append(f"Source: ClaudeCommands master {source_sha}")
    parts.append("")
    parts.append("Co-Authored-By: AgentForge Worker <noreply@agentforge.local>")
    return "\n".join(parts) + "\n"


def _classify_repo(
    skills_for_repo: dict[str, dict],
    target_manifest: dict[str, str],
    registry_skills: dict,
    repo_name: str,
    *,
    skill_filter: str | None = None,
) -> dict:
    """Compute add / update / unchanged / remove for one target repo.

    ``skills_for_repo`` is the subset of registry skills that target this
    repo (after wildcard expansion + retired/conflict filtering already
    applied for the *deploy* set; retired/dropped skills come in via the
    registry ``last_repo_deploy`` keys for the *remove* set).

    ``skill_filter`` (optional): when set, restricts the removal scan to
    just that one skill key. Without this, ``--skill foo`` would cause
    every other previously-deployed skill to be classified for removal.
    """
    add: list[str] = []
    update: list[str] = []
    unchanged: list[str] = []
    remove: list[str] = []

    deploy_keys = set(skills_for_repo.keys())
    target_keys = set(target_manifest.keys())

    for key in sorted(deploy_keys):
        new_hash = skills_for_repo[key].get("manifest_hash", "")
        if key not in target_keys:
            add.append(key)
        else:
            if target_manifest[key] == new_hash:
                unchanged.append(key)
            else:
                update.append(key)

    # Removal candidates: registry says we deployed it AND skill no longer
    # targets this repo (or was retired). We never remove files we don't
    # have a deploy record for — those are manual/unrelated.
    for key, entry in registry_skills.items():
        if skill_filter and key != skill_filter:
            continue
        last_repo = (entry.get("last_repo_deploy") or {}).get(repo_name)
        if not last_repo:
            continue
        if key in deploy_keys:
            continue
        # We previously deployed; we're not deploying now -> remove.
        remove.append(key)

    return {
        "add": add,
        "update": update,
        "unchanged": unchanged,
        "remove": sorted(remove),
    }


def sync_repos(
    *,
    apply: bool = False,
    repo: str | None = None,
    skill: str | None = None,
    force: bool = False,
    commit: bool = False,
) -> dict:
    """Plan (and optionally apply) a sync of skills into target repos.

    Default behavior writes files only — no git activity in the target
    repo. Pass ``commit=True`` (CLI: ``--commit``) to additionally stage
    + commit the changes. The commit-less path matches the convention
    pivot: ``.claude/commands/`` is gitignored after Step 2 migration so
    the staged-and-commit path becomes a no-op anyway.

    Returns a plan dict:

        {
            "mode": "apply" | "dry-run",
            "commit": bool,
            "repos": {
                <repo_name>: {
                    "repo_path": str | None,
                    "skipped": bool,
                    "reason": str | None,
                    "add": [...], "update": [...], "unchanged": [...], "remove": [...],
                    "errors": [...],
                    "commit": "<short-sha>" | None,
                }
            },
            "errors": [...],          # global errors (e.g. unknown repo)
        }
    """
    registry = load_registry()
    registry_skills: dict = registry.get("skills", {}) or {}

    projects = _load_projects()
    repo_index = _build_repo_index(projects)

    plan: dict = {
        "mode": "apply" if apply else "dry-run",
        "commit": bool(commit),
        "repos": {},
        "errors": [],
        "warnings": [],
    }

    # Determine the target repo set. Expand wildcards per-skill and union.
    # Build {repo_name: {skill_key: entry}} for all *active* deploys.
    by_repo: dict[str, dict[str, dict]] = {}
    # Track skills with any history of repo deploys so we can compute
    # removals even if the skill is no longer registered to any repo.
    all_relevant_skills: set[str] = set()

    for key, entry in registry_skills.items():
        if skill and key != skill:
            continue
        # Retired/conflict skills do not get newly deployed, but if the
        # registry shows we previously deployed them, they enter the
        # remove path through last_repo_deploy below.
        retired = bool(entry.get("retired"))
        conflict = bool(entry.get("conflict"))

        targets = _expand_targets(entry.get("deploys_to_repos") or [], repo_index)
        if not retired and not conflict:
            for t in targets:
                if repo and t != repo:
                    continue
                by_repo.setdefault(t, {})[key] = entry
                all_relevant_skills.add(key)
        # Always consider previous repo deploys for removal candidates.
        for r in (entry.get("last_repo_deploy") or {}).keys():
            if repo and r != repo:
                continue
            by_repo.setdefault(r, {})  # ensure repo present in plan
            all_relevant_skills.add(key)

    if not by_repo:
        if repo:
            plan["errors"].append(f"no skills target repo {repo!r}")
        elif skill:
            plan["errors"].append(
                f"skill {skill!r} has no deploys_to_repos targets and no prior repo deploys"
            )
        return plan

    # Process each repo independently.
    source_sha = _source_repo_short_sha()
    now = _now_iso()

    for repo_name in sorted(by_repo.keys()):
        repo_plan: dict = {
            "repo_path": None,
            "skipped": False,
            "reason": None,
            "add": [],
            "update": [],
            "unchanged": [],
            "remove": [],
            "errors": [],
            "warnings": [],
            "commit": None,
        }
        plan["repos"][repo_name] = repo_plan

        repo_path = repo_index.get(repo_name)
        if repo_path is None:
            repo_plan["skipped"] = True
            repo_plan["reason"] = (
                f"no repo_path for {repo_name!r} in project_registry.yaml — "
                "add a repo_path or update the skill's deploys_to_repos."
            )
            continue
        repo_plan["repo_path"] = str(repo_path)

        if not _is_git_worktree(repo_path):
            repo_plan["skipped"] = True
            repo_plan["reason"] = f"{repo_path} is not a git working tree."
            continue

        # Self-clobber guard: skill home_repo == this target.
        skills_for_repo = dict(by_repo[repo_name])
        for key in list(skills_for_repo.keys()):
            entry = skills_for_repo[key]
            if entry.get("home_repo") == repo_name:
                repo_plan["errors"].append(
                    f"refused: skill {key!r} has home_repo={repo_name!r}; "
                    "would clobber its own source. Edit the skill's "
                    "frontmatter (drop this repo from deploys_to_repos) "
                    "and run `claude-skills register --update`."
                )
                # Remove from active deploy set; do NOT classify as remove
                # either (we never had a clean deploy record for it).
                del skills_for_repo[key]

        # Dirty-tree guard. Only meaningful when --commit is requested,
        # since otherwise we're not modifying git state. Without --commit
        # we still skip if the repo is dirty — leaving extra unstaged
        # files in someone's working tree without telling them is rude.
        dirty = _has_uncommitted_outside(repo_path, ".claude/commands/")
        if dirty:
            if force:
                repo_plan["warnings"].append(
                    f"--force in effect; {len(dirty)} uncommitted path(s) "
                    f"outside .claude/commands/ ignored (first: {dirty[0]})."
                )
            else:
                repo_plan["skipped"] = True
                repo_plan["reason"] = (
                    f"{len(dirty)} uncommitted path(s) outside "
                    f".claude/commands/ in {repo_path} (first: {dirty[0]}). "
                    "Pass --force to override."
                )
                continue

        # Classify.
        commands_dir = repo_path / ".claude" / "commands"
        target_manifest = _build_target_manifest(commands_dir)
        cls = _classify_repo(
            skills_for_repo,
            target_manifest,
            registry_skills,
            repo_name,
            skill_filter=skill,
        )
        repo_plan["add"] = cls["add"]
        repo_plan["update"] = cls["update"]
        repo_plan["unchanged"] = cls["unchanged"]
        repo_plan["remove"] = cls["remove"]

        if not apply:
            continue

        # ---- APPLY ----

        # Track old hashes for the update entries so the commit message
        # can show "old7 -> new7".
        update_pairs: list[tuple[str, str, str]] = []
        for key in cls["update"]:
            old_hash = target_manifest.get(key, "")[:7]
            new_hash = skills_for_repo[key].get("manifest_hash", "")[:7]
            update_pairs.append((key, old_hash, new_hash))

        # Pass 1: copy adds + updates.
        all_written: list[Path] = []
        for key in cls["add"] + cls["update"]:
            entry = skills_for_repo[key]
            home_path = Path(entry["home_path"])
            if not home_path.is_file():
                repo_plan["errors"].append(
                    f"missing home_path for {key}: {home_path}"
                )
                continue
            try:
                written = _copy_skill_unit(home_path, commands_dir)
                all_written.extend(written)
            except OSError as exc:
                repo_plan["errors"].append(f"copy failed for {key}: {exc}")

        # Pass 2: removals.
        all_removed: list[Path] = []
        for key in cls["remove"]:
            try:
                removed = _remove_skill_unit(commands_dir, key)
                all_removed.extend(removed)
            except OSError as exc:
                repo_plan["errors"].append(f"remove failed for {key}: {exc}")

        # Pass 3: stage + commit only when --commit was requested.
        diff_nonempty = bool(all_written or all_removed)
        if commit and diff_nonempty:
            try:
                for p in all_written:
                    _git_run(repo_path, ["add", "--", str(p)])
                for p in all_removed:
                    rel = p.relative_to(repo_path)
                    ret = _git_run(
                        repo_path,
                        ["rm", "--cached", "--ignore-unmatch", "--", str(rel)],
                        check=False,
                    )
                    _ = ret  # We rely on pass 2 having unlinked from disk.

                # Detect whether anything is actually staged.
                ret_status = _git_run(
                    repo_path, ["diff", "--cached", "--name-only"], check=False
                )
                staged = [
                    ln
                    for ln in (ret_status.stdout or "").splitlines()
                    if ln.strip()
                ]
                if staged:
                    msg = _format_commit_message(
                        cls["add"], update_pairs, cls["remove"], source_sha
                    )
                    _git_run(repo_path, ["commit", "-m", msg])
                    repo_plan["commit"] = _short_sha(repo_path)
                # else: nothing staged (e.g. files identical / gitignored
                # in the post-pivot world); skip commit silently.
            except subprocess.CalledProcessError as exc:
                repo_plan["errors"].append(
                    f"git stage/commit failed: {exc.stderr or exc.stdout or exc}"
                )
                continue

        # Update last_repo_deploy entries on the registry copy.
        commit_short = repo_plan["commit"] or ""
        for key in cls["add"] + cls["update"]:
            entry = registry_skills.get(key)
            if entry is None:
                continue
            lrd = entry.setdefault("last_repo_deploy", {})
            lrd[repo_name] = {
                "hash": entry.get("manifest_hash", ""),
                "ts": now,
                "action": "add" if key in cls["add"] else "update",
                "commit": commit_short,
            }
        for key in cls["remove"]:
            entry = registry_skills.get(key)
            if entry is None:
                continue
            lrd = entry.setdefault("last_repo_deploy", {})
            lrd.pop(repo_name, None)

    # Persist registry once at the end if we applied anything.
    if apply and any(
        rp.get("commit") or rp.get("add") or rp.get("update") or rp.get("remove")
        for rp in plan["repos"].values()
    ):
        save_registry(registry)

    return plan


def render_repo_plan(plan: dict) -> int:
    """Print a sync-repos plan dict to stdout. Returns exit code."""
    mode = plan.get("mode", "dry-run")
    commit_flag = plan.get("commit", False)
    suffix = " --commit" if commit_flag else ""
    print(f"=== sync-repos plan (mode={mode}{suffix}) ===\n")

    repos = plan.get("repos") or {}
    if not repos:
        print("  No matching repos / skills.")
        if plan.get("errors"):
            for e in plan["errors"]:
                print(f"    ! {e}")
            return 1
        return 0

    any_errors = False
    any_skipped = False

    for repo_name in sorted(repos.keys()):
        rp = repos[repo_name]
        print(f"  Repo: {repo_name}")
        print(f"    path: {rp.get('repo_path') or '(unresolved)'}")
        if rp.get("skipped"):
            print(f"    SKIPPED: {rp.get('reason')}")
            any_skipped = True
            continue
        print(
            f"    add={len(rp['add'])} update={len(rp['update'])} "
            f"unchanged={len(rp['unchanged'])} remove={len(rp['remove'])}"
        )
        for k in rp["add"]:
            print(f"      + {k}")
        for k in rp["update"]:
            print(f"      ~ {k}")
        for k in rp["remove"]:
            print(f"      - {k}")
        if rp.get("commit"):
            print(f"    commit: {rp['commit']}")
        for w in rp.get("warnings") or []:
            print(f"    (warning) {w}")
        if rp.get("errors"):
            any_errors = True
            for e in rp["errors"]:
                print(f"    ! {e}")
        print()

    if plan.get("errors"):
        any_errors = True
        print("\n  Global errors:")
        for e in plan["errors"]:
            print(f"    ! {e}")

    if mode == "apply":
        if commit_flag:
            print("\n  Applied: yes (with commits where files changed)")
        else:
            print("\n  Applied: yes (files written, no commits — pass --commit "
                  "to also stage + commit)")
    else:
        if commit_flag:
            print("\n  Dry run — no changes written. Use --apply to write + commit.")
        else:
            print("\n  Dry run — no changes written. Use --apply to write files; "
                  "add --commit to also stage + commit.")

    if any_errors:
        return 3
    if any_skipped:
        return 0  # skipping is informational; not an error
    return 0
