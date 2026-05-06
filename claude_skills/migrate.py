"""``claude-skills migrate-domain-skills`` — relocate legacy skill sources.

Convention pivot Step 1 of 6: ``.claude/commands/`` is now runtime-only
(gitignored, populated by ``claude-skills sync``); skill source-of-truth
lives at ``<repo>/agent-io/skills/<skill>.md``.

This module is invoked by the CLI (dry-run by default; ``--apply`` to
mutate). It walks the registry, finds skills whose ``home_path`` still
resolves to a legacy location, plans a ``git mv`` per skill into the new
canonical location, ensures each touched repo's ``.gitignore`` carries
the runtime-artifact entries, and produces one migration commit per repo.

Discovery rules (legacy → canonical):

  <repo>/.claude/commands/<skill>.md
    → <repo>/agent-io/skills/<skill>.md

  <repo>/commands/<skill>.md   (ClaudeCommands universals)
    → <repo>/agent-io/skills/<skill>.md

The optional sibling context dir (e.g. ``<skill>/``) is moved alongside
the anchor with the same ``git mv`` strategy.

Hard rules:
  - Use ``git mv`` whenever the home repo is a git work tree, so renames
    preserve history.
  - Idempotent: running twice is a no-op (already-migrated skills are
    classified as ``skipped: already-migrated``).
  - Refuse to move a skill if its registered ``home_path`` doesn't exist
    on disk (logged as an error, surfaces non-zero exit).
  - Refuse if the target ``agent-io/skills/<skill>.md`` already exists
    AND has different content from the legacy source (caller has to
    resolve the conflict manually).
  - One commit per home_repo, only when ``--apply`` and at least one
    file actually moved or ``.gitignore`` changed.
  - Never push.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from claude_skills.manifest import compute_manifest_hash
from claude_skills.registry import load_registry, save_registry


_GITIGNORE_BLOCK = (
    "# claude-skills runtime artifacts (populated by `claude-skills sync`)\n"
    ".claude/commands/\n"
    ".claude/skills/\n"
)
_GITIGNORE_HEADER = "# claude-skills runtime artifacts (populated by `claude-skills sync`)"

_COMMIT_MESSAGE = (
    "chore: migrate skills source to agent-io/skills/\n\n"
    "Convention pivot: .claude/commands/ is now runtime-only (gitignored,\n"
    "populated by `claude-skills sync`). Source-of-truth lives in\n"
    "agent-io/skills/.\n"
)

_DEFAULT_PROJECT_REGISTRY = (
    Path.home() / "Dropbox" / "Projects" / "AIAssistant" / "state" / "project_registry.yaml"
)
_PROJECT_REGISTRY_ENV = "CLAUDE_SKILLS_PROJECT_REGISTRY_PATH"

_LEGACY_KINDS = (".claude/commands", "commands")


def _project_registry_path() -> Path:
    override = os.environ.get(_PROJECT_REGISTRY_ENV)
    if override:
        return Path(override)
    return _DEFAULT_PROJECT_REGISTRY


def _load_projects() -> dict:
    path = _project_registry_path()
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("projects", {}) or {}


def _resolve_repo_path_with_ancestors(project_id: str, projects: dict) -> str | None:
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


def _build_repo_root_index() -> dict[str, Path]:
    """Return ``{repo_name: repo_root_path}`` for known home repos.

    Includes ClaudeCommands (the repo this CLI lives in) and AIAssistant
    (special-cased to ~/Dropbox/Projects/AIAssistant) plus every project
    in the registry that resolves to a repo_path.
    """
    here = Path(__file__).resolve().parent.parent
    out: dict[str, Path] = {}
    out["ClaudeCommands"] = here
    aia = Path.home() / "Dropbox" / "Projects" / "AIAssistant"
    if aia.is_dir():
        out["AIAssistant"] = aia
    projects = _load_projects()
    for pid, info in projects.items():
        name = info.get("name") or pid
        if name in out:
            continue
        rp = _resolve_repo_path_with_ancestors(pid, projects)
        if not rp:
            continue
        path = Path(rp).expanduser()
        if path.is_dir():
            out[name] = path
    return out


def _classify_legacy(home_path: Path, repo_root: Path) -> str | None:
    """Return the legacy ``source_kind`` for a path, or None if canonical.

    A path counts as canonical if it lives directly under
    ``<some_root>/agent-io/skills/``. Otherwise we check the legacy
    locations (``.claude/commands/`` or top-level ``commands/``) and
    return the first match.

    We classify by examining the path *suffix* rather than computing
    ``relative_to(repo_root)``. That keeps the classifier robust when
    the registered ``home_path`` was written from a different working
    tree (e.g. the canonical Dropbox checkout) than the one the CLI is
    executing from now (e.g. an AgentForge worktree). The repo_root is
    still passed for symmetry / future use but is only consulted for
    canonical checks.
    """
    parts = home_path.parts
    # Canonical: anywhere under .../agent-io/skills/<file>
    for i in range(len(parts) - 2):
        if parts[i] == "agent-io" and parts[i + 1] == "skills":
            return None
    # Legacy: .../<repo>/.claude/commands/<file>
    for i in range(len(parts) - 2):
        if parts[i] == ".claude" and parts[i + 1] == "commands":
            return ".claude/commands"
    # Legacy ClaudeCommands universals: .../<ClaudeCommands>/commands/<file>
    # We require the parent dir's parent to look like a repo root (i.e.
    # exists), which is the case in normal use; in a worktree we just
    # accept any "commands/<file>" that isn't under .claude/.
    if len(parts) >= 2 and parts[-2] == "commands":
        return "commands"
    return None


def _git_run(
    repo_root: Path, args: list[str], *, check: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=check,
    )


def _is_git_worktree(repo_root: Path) -> bool:
    try:
        ret = _git_run(repo_root, ["rev-parse", "--show-toplevel"], check=False)
    except (OSError, FileNotFoundError):
        return False
    if ret.returncode != 0:
        return False
    return Path(ret.stdout.strip()).resolve() == repo_root.resolve()


def _gitignore_needs_block(repo_root: Path) -> bool:
    """Return True if ``.gitignore`` is missing the runtime-artifact block.

    Checks for the literal entries ``.claude/commands/`` and
    ``.claude/skills/`` (anywhere in the file). Comments are independent;
    we only require the directory entries themselves to be present.
    """
    gi = repo_root / ".gitignore"
    if not gi.is_file():
        return True
    text = gi.read_text(encoding="utf-8")
    needed = (".claude/commands/", ".claude/skills/")
    have = {
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    return not all(entry in have for entry in needed)


def _append_gitignore_block(repo_root: Path) -> Path:
    """Append the runtime-artifact block to .gitignore (or create it).

    Returns the gitignore path. Idempotent: only appends entries that
    aren't already present (header comment is added if any entry is
    being appended).
    """
    gi = repo_root / ".gitignore"
    existing = ""
    if gi.is_file():
        existing = gi.read_text(encoding="utf-8")

    have = {
        line.strip()
        for line in existing.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    needed = [".claude/commands/", ".claude/skills/"]
    missing = [n for n in needed if n not in have]

    if not missing:
        return gi

    addition_lines: list[str] = []
    if _GITIGNORE_HEADER not in existing:
        addition_lines.append(_GITIGNORE_HEADER)
    for n in missing:
        addition_lines.append(n)
    addition = "\n".join(addition_lines) + "\n"

    if existing and not existing.endswith("\n"):
        existing += "\n"
    if existing and not existing.endswith("\n\n"):
        existing += "\n"

    gi.write_text(existing + addition, encoding="utf-8")
    return gi


def _move_skill_unit(
    repo_root: Path,
    home_path: Path,
    new_anchor: Path,
    *,
    use_git: bool,
) -> tuple[list[Path], list[str]]:
    """Move ``home_path`` (+ optional sibling dir) to ``new_anchor``.

    Returns (paths_after_move, errors).
    """
    errors: list[str] = []
    new_anchor.parent.mkdir(parents=True, exist_ok=True)

    moved: list[Path] = []
    sibling_old = home_path.parent / home_path.stem
    sibling_new = new_anchor.parent / new_anchor.stem

    if use_git:
        try:
            _git_run(
                repo_root,
                [
                    "mv",
                    str(home_path.relative_to(repo_root)),
                    str(new_anchor.relative_to(repo_root)),
                ],
            )
            moved.append(new_anchor)
        except subprocess.CalledProcessError as exc:
            errors.append(
                f"git mv {home_path} -> {new_anchor} failed: "
                f"{(exc.stderr or exc.stdout or '').strip()}"
            )
            return moved, errors

        if sibling_old.is_dir():
            try:
                _git_run(
                    repo_root,
                    [
                        "mv",
                        str(sibling_old.relative_to(repo_root)),
                        str(sibling_new.relative_to(repo_root)),
                    ],
                )
                moved.append(sibling_new)
            except subprocess.CalledProcessError as exc:
                errors.append(
                    f"git mv {sibling_old} -> {sibling_new} failed: "
                    f"{(exc.stderr or exc.stdout or '').strip()}"
                )
    else:
        try:
            home_path.rename(new_anchor)
            moved.append(new_anchor)
            if sibling_old.is_dir():
                sibling_old.rename(sibling_new)
                moved.append(sibling_new)
        except OSError as exc:
            errors.append(
                f"rename {home_path} -> {new_anchor} failed: {exc}"
            )

    return moved, errors


def migrate_domain_skills(
    *,
    apply: bool = False,
    repo: str | None = None,
    skill: str | None = None,
) -> dict:
    """Plan (and optionally apply) the legacy → agent-io/skills/ migration.

    ``repo`` and ``skill`` filters narrow the plan but don't affect the
    discovery rule itself (only entries that are actually legacy are
    migrated).

    Returns a plan dict::

        {
            "mode": "apply" | "dry-run",
            "repos": {
                <repo_name>: {
                    "repo_path": str,
                    "moves": [
                        { "skill": "...", "old": "...", "new": "...",
                          "kind": ".claude/commands"|"commands" }
                    ],
                    "skipped_already_migrated": [skill_keys],
                    "gitignore_updated": bool,
                    "commit": str | None,
                    "errors": [...],
                }
            },
            "errors": [...],
            "registry_updated": bool,
        }
    """
    plan: dict = {
        "mode": "apply" if apply else "dry-run",
        "repos": {},
        "errors": [],
        "registry_updated": False,
    }

    registry = load_registry()
    skills_reg = registry.get("skills", {}) or {}

    repo_index = _build_repo_root_index()

    # Group skills by their resolved home_repo. Build the move plan per repo.
    by_repo: dict[str, dict] = {}

    for skill_key, entry in skills_reg.items():
        if skill and skill_key != skill:
            continue
        home_repo_name = entry.get("home_repo") or ""
        if repo and home_repo_name != repo:
            continue
        if not home_repo_name:
            continue

        repo_root = repo_index.get(home_repo_name)
        if repo_root is None:
            plan["errors"].append(
                f"unknown home_repo {home_repo_name!r} for skill {skill_key!r} — "
                "no entry in project_registry.yaml."
            )
            continue

        rp = by_repo.setdefault(
            home_repo_name,
            {
                "repo_path": str(repo_root),
                "moves": [],
                "skipped_already_migrated": [],
                "gitignore_updated": False,
                "commit": None,
                "errors": [],
                "_home_paths": {},  # internal: skill -> resolved path
            },
        )

        home_path_str = entry.get("home_path") or ""
        if not home_path_str:
            rp["errors"].append(
                f"skill {skill_key!r}: empty home_path in registry."
            )
            continue
        home_path = Path(home_path_str)

        kind = _classify_legacy(home_path, repo_root)
        if kind is None:
            rp["skipped_already_migrated"].append(skill_key)
            continue

        if not home_path.is_file():
            rp["errors"].append(
                f"skill {skill_key!r}: home_path {home_path} does not exist."
            )
            continue

        # Sanity guard: if the on-disk home_path is NOT under the
        # resolved repo_root (e.g. the registry was written from a
        # canonical checkout but the CLI is running from a worktree
        # against a different copy of the repo), refuse to move. The
        # user must run migrate-domain-skills from the same checkout
        # that owns the files.
        try:
            home_path.resolve().relative_to(repo_root.resolve())
        except ValueError:
            rp["errors"].append(
                f"skill {skill_key!r}: home_path {home_path} is outside the "
                f"resolved repo_root {repo_root}. Run "
                "`claude-skills migrate-domain-skills` from the canonical "
                "checkout (where claude_skills/ lives) so git mv operates "
                "on the right files."
            )
            continue

        new_anchor = repo_root / "agent-io" / "skills" / f"{skill_key}.md"

        # Sanity: don't clobber a different file at the canonical path.
        if new_anchor.exists():
            try:
                if compute_manifest_hash(home_path) != compute_manifest_hash(new_anchor):
                    rp["errors"].append(
                        f"skill {skill_key!r}: target {new_anchor} already exists "
                        "with different content. Resolve manually."
                    )
                    continue
                else:
                    # Identical content already at canonical path — treat as
                    # already-migrated; we'll still update home_path below.
                    rp["skipped_already_migrated"].append(skill_key)
                    rp["_home_paths"][skill_key] = new_anchor
                    continue
            except OSError as exc:
                rp["errors"].append(
                    f"skill {skill_key!r}: could not compare hashes: {exc}"
                )
                continue

        rp["moves"].append(
            {
                "skill": skill_key,
                "old": str(home_path),
                "new": str(new_anchor),
                "kind": kind,
            }
        )
        rp["_home_paths"][skill_key] = new_anchor

    # Decide gitignore touch per repo (only if there are moves OR the
    # block is missing — we update gitignore even on no-move repos when
    # the user runs --apply, so that subsequent ``claude-skills sync``
    # doesn't pollute the working tree).
    for repo_name, rp in by_repo.items():
        repo_root = Path(rp["repo_path"])
        rp["gitignore_needs_update"] = _gitignore_needs_block(repo_root)
        if rp["gitignore_needs_update"]:
            rp["gitignore_updated"] = True  # will be true after --apply

    if not apply:
        # Strip internal helpers before returning the dry-run plan.
        for rp in by_repo.values():
            rp.pop("_home_paths", None)
            rp.pop("gitignore_needs_update", None)
        plan["repos"] = by_repo
        return plan

    # ---- APPLY ----
    registry_dirty = False
    for repo_name in sorted(by_repo.keys()):
        rp = by_repo[repo_name]
        repo_root = Path(rp["repo_path"])
        is_git = _is_git_worktree(repo_root)

        # Per-skill moves first (so .gitignore staging picks up sibling files).
        actually_moved_paths: list[Path] = []
        for move in list(rp["moves"]):
            home_path = Path(move["old"])
            new_anchor = Path(move["new"])
            moved, errs = _move_skill_unit(
                repo_root, home_path, new_anchor, use_git=is_git
            )
            if errs:
                rp["errors"].extend(errs)
                # Don't update registry for failed moves.
                rp["_home_paths"].pop(move["skill"], None)
                continue
            actually_moved_paths.extend(moved)

        # Update registry home_path for moved + already-migrated entries.
        for skill_key, new_path in rp.get("_home_paths", {}).items():
            entry = skills_reg.get(skill_key)
            if entry is None:
                continue
            new_str = str(new_path)
            if entry.get("home_path") != new_str:
                entry["home_path"] = new_str
                registry_dirty = True

        # Gitignore.
        gitignore_changed = False
        if rp.get("gitignore_needs_update"):
            try:
                _append_gitignore_block(repo_root)
                gitignore_changed = True
            except OSError as exc:
                rp["errors"].append(f"failed to update .gitignore: {exc}")
        rp["gitignore_updated"] = gitignore_changed

        # Stage + commit per repo.
        if is_git and (actually_moved_paths or gitignore_changed):
            try:
                # The git mv calls above already staged the renames; only
                # the .gitignore write needs explicit staging.
                if gitignore_changed:
                    _git_run(repo_root, ["add", ".gitignore"])
                # Sanity: anything actually staged?
                ret = _git_run(
                    repo_root, ["diff", "--cached", "--name-only"], check=False
                )
                staged = [
                    ln for ln in (ret.stdout or "").splitlines() if ln.strip()
                ]
                if staged:
                    _git_run(repo_root, ["commit", "-m", _COMMIT_MESSAGE])
                    sha = _git_run(
                        repo_root, ["rev-parse", "--short", "HEAD"], check=False
                    )
                    rp["commit"] = sha.stdout.strip() if sha.returncode == 0 else None
            except subprocess.CalledProcessError as exc:
                rp["errors"].append(
                    f"git commit failed: {(exc.stderr or exc.stdout or str(exc)).strip()}"
                )

        # Strip internal helpers from the returned plan.
        rp.pop("_home_paths", None)
        rp.pop("gitignore_needs_update", None)

    if registry_dirty:
        save_registry(registry)
        plan["registry_updated"] = True

    plan["repos"] = by_repo
    return plan


def render_migrate_plan(plan: dict) -> int:
    """Print a migrate-domain-skills plan to stdout. Returns exit code."""
    mode = plan.get("mode", "dry-run")
    print(f"=== migrate-domain-skills plan (mode={mode}) ===\n")

    repos = plan.get("repos") or {}
    if not repos:
        print("  Nothing to migrate — no skills resolve to a legacy location.")
        if plan.get("errors"):
            for e in plan["errors"]:
                print(f"    ! {e}")
            return 1
        return 0

    any_errors = False
    total_moves = 0

    for repo_name in sorted(repos.keys()):
        rp = repos[repo_name]
        moves = rp.get("moves") or []
        skipped = rp.get("skipped_already_migrated") or []
        print(f"  Repo: {repo_name}")
        print(f"    path: {rp.get('repo_path')}")
        print(
            f"    moves={len(moves)}  already_migrated={len(skipped)}  "
            f"errors={len(rp.get('errors') or [])}"
        )
        for m in moves:
            print(
                f"      {m['kind']}: {m['skill']}\n"
                f"        from: {m['old']}\n"
                f"        to:   {m['new']}"
            )
            total_moves += 1
        if rp.get("gitignore_updated"):
            print(f"    .gitignore: appended runtime-artifact block")
        if rp.get("commit"):
            print(f"    commit: {rp['commit']}")
        if rp.get("errors"):
            any_errors = True
            for e in rp["errors"]:
                print(f"    ! {e}")
        print()

    if plan.get("errors"):
        any_errors = True
        print("  Global errors:")
        for e in plan["errors"]:
            print(f"    ! {e}")

    if mode == "apply":
        if plan.get("registry_updated"):
            print("\n  Registry updated: yes")
        print(f"\n  Applied: {total_moves} move(s) across {len(repos)} repo(s).")
    else:
        print(
            f"\n  Dry run — no changes written. Use --apply to perform "
            f"{total_moves} move(s) and update .gitignore."
        )

    return 3 if any_errors else 0
