#!/usr/bin/env python3
"""CLI entry point for claude-skills."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from claude_skills.systems import load_systems


# Cowork-inbox root used for cross-machine sync dispatch. The convention is
# documented in AIAssistant/cowork-inbox/README.md.
_COWORK_INBOX_ROOT = (
    Path.home() / "Dropbox" / "Projects" / "AIAssistant" / "cowork-inbox"
)


def cmd_list(args):
    """List all registered skills."""
    from claude_skills.registry import load_registry

    registry = load_registry()
    skills = registry.get("skills", {})

    if not skills:
        print("No skills in registry. Run 'claude-skills inventory --apply' first.")
        return 0

    # Apply filters
    filtered = {}
    for key, entry in skills.items():
        if args.scope and entry.get("scope") != args.scope:
            continue
        if args.home and entry.get("home_repo") != args.home:
            continue
        filtered[key] = entry

    if not filtered:
        print("No skills match the given filters.")
        return 0

    # Sort by scope then name
    sorted_keys = sorted(filtered.keys(), key=lambda k: (filtered[k].get("scope", ""), k))

    # Print table header
    print(f"{'Name':<30} {'Scope':<10} {'Home':<20} {'Deployed To':<15} {'Hash':<10} {'Status':<10}")
    print("-" * 95)

    for key in sorted_keys:
        entry = filtered[key]
        name = key
        scope = entry.get("scope", "?")
        home = entry.get("home_repo", "?")
        deployed = ", ".join(entry.get("deploys_to_machines", [])) or "-"
        manifest_hash = entry.get("manifest_hash", "")[:8]

        # Determine status
        if entry.get("conflict"):
            status = "conflict"
        elif entry.get("retired"):
            status = "retired"
        else:
            # Check if file still exists
            from pathlib import Path
            home_path = entry.get("home_path", "")
            if home_path and not Path(home_path).exists():
                status = "missing"
            else:
                status = "ok"

        print(f"{name:<30} {scope:<10} {home:<20} {deployed:<15} {manifest_hash:<10} {status:<10}")

    print(f"\nTotal: {len(filtered)} skills")
    return 0


def cmd_inventory(args):
    """Show skill inventory, optionally apply changes."""
    from claude_skills.inventory import inventory

    apply = args.apply
    result = inventory(apply=apply)

    proposed = result["proposed_skills"]
    conflicts = result["conflicts"]
    deploy_dups = result.get("deploy_dups", [])
    scope_drifts = result["scope_drifts"]
    new_skills = result["new_skills"]
    removed = result["removed_skills"]
    unchanged = result["unchanged"]
    hash_changed = result["hash_changed"]

    # Print summary
    print("=== Skill Inventory Report ===\n")
    print(f"  Total discovered: {len(proposed)}")
    print(f"  New:              {len(new_skills)}")
    print(f"  Unchanged:        {len(unchanged)}")
    print(f"  Hash changed:     {len(hash_changed)}")
    print(f"  Removed:          {len(removed)}")
    print(f"  Conflicts:        {len(conflicts)}  (real forks — different content in different homes)")
    print(f"  Deployment dups:  {len(deploy_dups)}  (same content in multiple homes — collapsed to most-specific)")
    print(f"  Scope drifts:     {len(scope_drifts)}")

    # Detailed listings
    if new_skills:
        print(f"\n  New skills:")
        for name in sorted(new_skills):
            entry = proposed[name]
            print(f"    + {name} ({entry['scope']}, {entry['home_repo']})")

    if hash_changed:
        print(f"\n  Changed (hash differs):")
        for name in sorted(hash_changed):
            entry = proposed[name]
            print(f"    ~ {name} ({entry['scope']}, {entry['home_repo']})")

    if removed:
        print(f"\n  Removed (no longer found in any home):")
        for name in sorted(removed):
            print(f"    - {name}")

    if conflicts:
        print(f"\n  Conflicts (different content in different homes — needs investigation):")
        for name in sorted(conflicts):
            entry = proposed[name]
            kept_home = entry["home_repo"]
            alts = entry.get("conflict_alternates", [])
            alt_homes = ", ".join(a["home_repo"] for a in alts) or "(none)"
            print(f"    ! {name}  kept={kept_home}  also_in={alt_homes}")

    if deploy_dups and not apply:
        # Only show deploy_dups in dry-run; with --apply they're collapsed silently.
        print(f"\n  Deployment duplicates (same content, collapsed to most-specific home):")
        for name in sorted(deploy_dups):
            entry = proposed[name]
            print(f"    = {name} → kept in {entry['home_repo']} ({entry['scope']})")

    if scope_drifts:
        print(f"\n  Scope drifts:")
        for name, reg_scope, fm_scope in scope_drifts:
            print(f"    ? {name}: registry={reg_scope}, frontmatter={fm_scope}")

    if apply:
        print(f"\n  Registry written with {len(proposed)} skills.")
    else:
        print(f"\n  Dry run — no changes written. Use --apply to write registry.")

    return 0


def cmd_status(args):
    """Show deployment status."""
    from pathlib import Path
    from claude_skills.registry import load_registry

    registry = load_registry()
    skills = registry.get("skills", {})
    systems = load_systems()

    if not skills:
        print("No skills in registry. Run 'claude-skills inventory --apply' first.")
        return 0

    if not systems:
        print("No systems defined in state/systems.yaml.")
        return 0

    # Filter to specific system if requested
    if args.system:
        if args.system not in systems:
            print(f"error: unknown system '{args.system}'", file=sys.stderr)
            return 1
        systems = {args.system: systems[args.system]}

    for sys_name, sys_info in systems.items():
        subs = sys_info.get("subscriptions", {})
        sub_scopes = subs.get("scopes", [])
        sub_domains = subs.get("domains", [])
        requires_role = subs.get("requires_role")

        # Find subscribed skills
        subscribed = {}
        for skill_key, entry in skills.items():
            skill_scope = entry.get("scope", "")
            skill_domain = entry.get("domain")

            # Check scope match
            if skill_scope not in sub_scopes:
                continue

            # Check domain match (only for domain-scoped skills)
            if skill_scope == "domain":
                if sub_domains != ["*"]:
                    if skill_domain not in sub_domains:
                        continue

            # Skip retired skills
            if entry.get("retired"):
                continue

            subscribed[skill_key] = entry

        # Compute status for each subscribed skill
        up_to_date = 0
        stale = 0
        not_deployed = 0

        print(f"\n{'='*60}")
        print(f"  System: {sys_name}")
        print(f"  Subscriptions: scopes={sub_scopes}, domains={sub_domains}")
        print(f"{'='*60}")

        if not subscribed:
            print("  No subscribed skills.")
            continue

        print(f"  {'Skill':<30} {'Scope':<10} {'Status':<15}")
        print(f"  {'-'*55}")

        for skill_key in sorted(subscribed.keys()):
            entry = subscribed[skill_key]
            last_deploy = entry.get("last_deploy", {})
            deploy_info = last_deploy.get(sys_name, {})
            current_hash = entry.get("manifest_hash", "")

            if not deploy_info:
                status_str = "not-deployed"
                not_deployed += 1
            else:
                deployed_hash = deploy_info.get("hash", "")
                if deployed_hash == current_hash:
                    status_str = "up-to-date"
                    up_to_date += 1
                else:
                    status_str = "stale"
                    stale += 1

            scope = entry.get("scope", "?")
            print(f"  {skill_key:<30} {scope:<10} {status_str:<15}")

        print(f"\n  Summary: {sys_name}: {up_to_date} up-to-date, {stale} stale, {not_deployed} not-deployed")

    return 0


def _write_cowork_sync_task(
    target_system: str,
    *,
    apply: bool,
    init_claude_md: bool,
    source_system: str,
) -> Path:
    """Write a cowork-inbox markdown task that asks <target> to run sync.

    Returns the absolute path of the file written. The cowork inbox is
    keyed by the target's machines.json alias (which can differ from its
    systems.yaml key — e.g. ``email-mac`` -> ``emailmac``).
    """
    systems = load_systems()
    target_info = systems.get(target_system, {}) or {}
    target_alias = target_info.get("machine_alias", target_system)

    inbox_dir = _COWORK_INBOX_ROOT / target_alias
    inbox_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).astimezone()
    timestamp_iso = now.isoformat(timespec="seconds")
    filename_stamp = now.strftime("%Y-%m-%d_%H%M")
    filename = f"{filename_stamp}_claude-skills-sync.md"
    out_path = inbox_dir / filename

    flags: list[str] = []
    if apply:
        flags.append("--apply")
    if init_claude_md:
        flags.append("--init-claude-md")
    cmdline = "claude-skills sync " + target_system
    if flags:
        cmdline += " " + " ".join(flags)

    body = (
        f"---\n"
        f"created: {timestamp_iso}\n"
        f"source_machine: {source_system}\n"
        f"project: claudecommands\n"
        f"priority: medium\n"
        f"---\n"
        f"# claude-skills sync request\n\n"
        f"Triggered from: {source_system} at {timestamp_iso}\n"
        f"Target machine: {target_system}\n"
        f"Apply mode: {'yes' if apply else 'no'}\n"
        f"Init CLAUDE.md: {'yes' if init_claude_md else 'no'}\n\n"
        f"## Action\n\n"
        f"Run on this machine (claude-skills is globally installed; cwd does not matter):\n\n"
        f"    {cmdline}\n\n"
        f"## Why\n\n"
        f"The user on {source_system} requested a deploy refresh on this machine.\n"
        f"A worker or interactive session here picks up this task via /ai-cowork.\n\n"
        f"Submitted by claude-skills CLI cross-machine triggering (Phase 2 feature).\n"
    )
    out_path.write_text(body, encoding="utf-8")
    return out_path


def cmd_sync(args):
    """Sync skills to a target system.

    If the target system is a different machine than the local one, write
    a cowork-inbox task file that asks the target machine to run the sync,
    then exit. Pass ``--local-only`` to bypass that dispatch and attempt
    sync against the local filesystem regardless.
    """
    from claude_skills.local_machine import detect_local_system
    from claude_skills.sync import sync

    target = args.system
    local_only = bool(getattr(args, "local_only", False))

    if not local_only:
        local = detect_local_system()
        if local is None:
            print(
                "error: could not determine local machine; pass --local-only "
                "to bypass cross-machine dispatch.",
                file=sys.stderr,
            )
            return 1
        if target != local:
            try:
                inbox_path = _write_cowork_sync_task(
                    target,
                    apply=bool(getattr(args, "apply", False)),
                    init_claude_md=bool(getattr(args, "init_claude_md", False)),
                    source_system=local,
                )
            except OSError as exc:
                print(f"error: failed to write cowork inbox task: {exc}", file=sys.stderr)
                return 1
            print(
                f"Sync task queued for {target} at {inbox_path}. "
                f"Pick up via /ai-cowork on that machine."
            )
            return 0

    try:
        plan = sync(
            target,
            apply=bool(getattr(args, "apply", False)),
            init_claude_md=bool(getattr(args, "init_claude_md", False)),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except PermissionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return _print_plan(plan, show_diff=False)


def cmd_diff(args):
    """Show diff between local and deployed skills for a system."""
    from claude_skills.sync import sync

    try:
        plan = sync(args.system, apply=False)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except PermissionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return _print_plan(plan, show_diff=True)


def _print_plan(plan: dict, show_diff: bool) -> int:
    """Render a sync/diff plan dict to stdout. Returns exit code."""
    sys_name = plan["system"]
    mode = plan["mode"]
    claude_md = plan["claude_md"]
    skills = plan["skills"]
    errors = plan.get("errors") or []

    print(f"=== sync plan: {sys_name} (mode={mode}) ===\n")

    # CLAUDE.md section
    print(f"  CLAUDE.md: action={claude_md['action']}")
    print(f"    tier1_hash={claude_md['tier1_hash']}")
    print(f"    tier2_hash={claude_md['tier2_hash']}")
    print(f"    {claude_md['diff_summary']}")
    if show_diff and claude_md.get("diff"):
        print("\n  --- CLAUDE.md diff ---")
        for line in claude_md["diff"].splitlines():
            print(f"    {line}")
        print("  --- end diff ---\n")

    # Skills counts + lists
    print(
        f"\n  Skills: add={len(skills['add'])}  "
        f"update={len(skills['update'])}  "
        f"unchanged={len(skills['unchanged'])}  "
        f"remove={len(skills['remove'])}"
    )
    if skills["add"]:
        print("    + add:")
        for k in skills["add"]:
            print(f"        {k}")
    if skills["update"]:
        print("    ~ update:")
        for k in skills["update"]:
            print(f"        {k}")
    if skills["remove"]:
        print("    - remove:")
        for k in skills["remove"]:
            print(f"        {k}")

    if errors:
        print("\n  Errors:")
        for e in errors:
            print(f"    ! {e}")

    if plan.get("applied"):
        print("\n  Applied: yes")
    else:
        print("\n  Dry run — no changes written. Use --apply to write.")

    # Non-zero exit if there were errors.
    return 0 if not errors else 3


_SCOPE_FROM_HOME = {
    "ClaudeCommands": "universal",
    "AIAssistant": "platform",
}


def _load_project_registry() -> dict:
    """Load AIAssistant project_registry.yaml -> dict[project_id, info]."""
    import yaml as _yaml

    path = (
        Path.home()
        / "Dropbox"
        / "Projects"
        / "AIAssistant"
        / "state"
        / "project_registry.yaml"
    )
    if not path.exists():
        return {}
    with open(path) as f:
        data = _yaml.safe_load(f) or {}
    return data.get("projects", {})


def _resolve_home_repo(home_repo: str) -> tuple[Path, str]:
    """Return (repo_path, project_id_or_special).

    home_repo may be:
      - "ClaudeCommands"  -> looked up in project_registry; falls back to the
                             repo this CLI lives in if not registered.
      - "AIAssistant"     -> ~/Dropbox/Projects/AIAssistant
      - any registered project name (matches name field) or project_id
    """
    projects = _load_project_registry()

    if home_repo == "AIAssistant":
        return Path.home() / "Dropbox" / "Projects" / "AIAssistant", "aiassistant"

    # Try project_id first
    if home_repo in projects:
        info = projects[home_repo]
        rp = info.get("repo_path")
        if rp:
            return Path(rp).expanduser(), home_repo
    # Try name match (case-sensitive then case-insensitive)
    for pid, info in projects.items():
        if info.get("name") == home_repo and info.get("repo_path"):
            return Path(info["repo_path"]).expanduser(), pid
    for pid, info in projects.items():
        if (info.get("name") or "").lower() == home_repo.lower() and info.get("repo_path"):
            return Path(info["repo_path"]).expanduser(), pid

    if home_repo == "ClaudeCommands":
        # Fallback: the repo we're running from.
        return Path(__file__).resolve().parent.parent, "claudecommands"

    raise ValueError(
        f"unknown home_repo {home_repo!r}: not 'AIAssistant' and not found "
        "in AIAssistant project_registry.yaml"
    )


def cmd_register(args):
    """Register a skill from a home repo.

    Resolves <home_repo> against AIAssistant's project_registry.yaml (with
    special cases for ClaudeCommands and AIAssistant), reads the skill .md
    file at <home_repo>/<relative_path>, parses frontmatter, and writes a
    new entry to the registry.
    """
    from claude_skills.frontmatter import extract_first_heading, parse_frontmatter
    from claude_skills.manifest import compute_manifest_hash
    from claude_skills.registry import load_registry, save_registry

    try:
        repo_path, project_id = _resolve_home_repo(args.home_repo)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    skill_path = (repo_path / args.path).resolve()
    if not skill_path.is_file():
        print(f"error: skill file not found: {skill_path}", file=sys.stderr)
        return 1

    # Parse frontmatter
    fm, body = parse_frontmatter(skill_path)
    skill_name_field = fm.get("name") or skill_path.stem
    skill_key = args.name or skill_path.stem

    # Determine scope
    if args.scope:
        scope = args.scope
    else:
        fm_scope = fm.get("scope", "")
        if fm_scope and not fm_scope.startswith("repo:") and fm_scope in (
            "universal",
            "platform",
            "domain",
        ):
            scope = fm_scope
        else:
            scope = _SCOPE_FROM_HOME.get(args.home_repo, "domain")

    description = fm.get("description") or extract_first_heading(body) or ""
    manifest_hash = compute_manifest_hash(skill_path)

    domain = None
    if scope == "domain":
        domain = project_id

    entry = {
        "name": skill_name_field,
        "description": description,
        "home_repo": args.home_repo,
        "home_path": str(skill_path),
        "scope": scope,
        "domain": domain,
        "manifest_hash": manifest_hash,
        "retired": False,
        "conflict": False,
        "deploys_to_machines": [],
        "deploys_to_repos": [],
        "last_deploy": {},
    }

    registry = load_registry()
    skills = registry.setdefault("skills", {})

    if skill_key in skills and not args.update:
        print(
            f"error: skill {skill_key!r} already in registry; pass --update to overwrite.",
            file=sys.stderr,
        )
        return 1

    if skill_key in skills and args.update:
        existing = skills[skill_key]
        # Preserve deployment state
        entry["deploys_to_machines"] = existing.get("deploys_to_machines", [])
        entry["deploys_to_repos"] = existing.get("deploys_to_repos", [])
        entry["last_deploy"] = existing.get("last_deploy", {})
        entry["retired"] = existing.get("retired", False)

    print(f"  register: {skill_key}")
    print(f"    name:          {skill_name_field}")
    print(f"    home_repo:     {args.home_repo}")
    print(f"    home_path:     {skill_path}")
    print(f"    scope:         {scope}")
    print(f"    domain:        {domain}")
    print(f"    manifest_hash: {manifest_hash}")

    if args.dry_run:
        print("  Dry run — no changes written.")
        return 0

    skills[skill_key] = entry
    save_registry(registry)
    print(f"  Registry updated ({skill_key}).")
    return 0


def cmd_retire(args):
    """Retire (or unretire) a skill, optionally deleting the source file.

    Default behavior sets ``retired=True`` so subsequent syncs skip the
    skill but its history stays in the registry. ``--unretire`` clears the
    flag. ``--delete-source`` additionally removes the skill file (and the
    sibling skill directory, if any) — refusing if the file falls outside
    its registered home repo.
    """
    from claude_skills.registry import load_registry, save_registry

    skill = args.skill
    registry = load_registry()
    skills = registry.setdefault("skills", {})

    if skill not in skills:
        print(f"error: skill {skill!r} not in registry.", file=sys.stderr)
        return 1

    entry = skills[skill]
    new_retired = not bool(args.unretire)
    old_retired = bool(entry.get("retired", False))

    if old_retired == new_retired and not args.delete_source:
        state = "retired" if new_retired else "active"
        print(f"  {skill}: already {state} — no change.")
        return 0

    entry["retired"] = new_retired
    state = "retired" if new_retired else "active"
    print(f"  {skill}: marked {state}.")

    if args.delete_source:
        if args.unretire:
            print(
                "error: --delete-source is not allowed with --unretire.",
                file=sys.stderr,
            )
            return 1

        home_path = Path(entry.get("home_path", ""))
        home_repo = entry.get("home_repo", "")
        if not home_path.is_file():
            print(
                f"error: home_path missing or not a file: {home_path}; "
                "refusing to delete.",
                file=sys.stderr,
            )
            return 1

        try:
            repo_root, _ = _resolve_home_repo(home_repo)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        try:
            home_path.resolve().relative_to(repo_root.resolve())
        except ValueError:
            print(
                f"error: home_path {home_path} is outside repo root "
                f"{repo_root}; refusing to delete.",
                file=sys.stderr,
            )
            return 1

        sibling = home_path.parent / home_path.stem
        targets = [home_path]
        if sibling.is_dir():
            targets.append(sibling)

        print("  Files to delete:")
        for t in targets:
            print(f"    {t}")
        print("  Confirm? [y/N] ", end="", flush=True)
        try:
            answer = input().strip().lower()
        except EOFError:
            answer = ""
        if answer != "y":
            print("  Cancelled.")
            return 1

        # Delete in safe order: file first, then sibling dir per-file.
        try:
            home_path.unlink()
        except OSError as exc:
            print(f"error: failed to delete {home_path}: {exc}", file=sys.stderr)
            return 1
        if sibling.is_dir():
            for path in sorted(sibling.rglob("*"), reverse=True):
                if path.is_file() or path.is_symlink():
                    try:
                        path.unlink()
                    except OSError as exc:
                        print(f"warning: failed to delete {path}: {exc}", file=sys.stderr)
                elif path.is_dir():
                    try:
                        path.rmdir()
                    except OSError:
                        pass
            try:
                sibling.rmdir()
            except OSError:
                pass

        print(f"  Source files deleted under {home_path.parent}.")

    save_registry(registry)
    return 0


def cmd_rename(args):
    """Rename a skill in the registry, optionally renaming the source file.

    Updates the registry key from ``old`` to ``new`` and, when
    ``--also-rename-file`` is set, renames the .md file (and sibling
    directory, if any) on disk. Uses ``git mv`` if the home repo is a git
    work tree so the rename is tracked.
    """
    import subprocess

    from claude_skills.manifest import compute_manifest_hash
    from claude_skills.registry import load_registry, save_registry

    old = args.old
    new = args.new
    registry = load_registry()
    skills = registry.setdefault("skills", {})

    if old not in skills:
        print(f"error: skill {old!r} not in registry.", file=sys.stderr)
        return 1
    if new in skills:
        print(
            f"error: skill {new!r} already in registry; retire it first if you "
            "want to overwrite.",
            file=sys.stderr,
        )
        return 1

    entry = dict(skills[old])
    if entry.get("conflict") and not args.force:
        print(
            f"error: skill {old!r} is marked conflict=True; pass --force to "
            "rename anyway (you may also need to handle conflict_alternates).",
            file=sys.stderr,
        )
        return 1

    home_path = Path(entry.get("home_path", ""))
    new_home_path = home_path.parent / f"{new}.md"
    sibling_old = home_path.parent / old
    sibling_new = home_path.parent / new

    print(f"  rename: {old} -> {new}")
    print(f"    home_path:       {home_path}")
    if args.also_rename_file:
        print(f"    new home_path:   {new_home_path}")
        if sibling_old.is_dir():
            print(f"    rename sibling:  {sibling_old} -> {sibling_new}")

    if args.dry_run:
        if not args.also_rename_file:
            print("    (file will not be renamed; pass --also-rename-file to do that)")
        print("  Dry run — no changes written.")
        return 0

    # Apply file rename if requested.
    if args.also_rename_file:
        if not home_path.is_file():
            print(f"error: cannot rename: {home_path} missing.", file=sys.stderr)
            return 1
        if new_home_path.exists():
            print(
                f"error: target file already exists: {new_home_path}",
                file=sys.stderr,
            )
            return 1

        # Detect git repo.
        repo_dir = home_path.parent
        try:
            ret = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            in_git = ret.returncode == 0
        except (OSError, FileNotFoundError):
            in_git = False

        try:
            if in_git:
                subprocess.run(
                    ["git", "mv", str(home_path), str(new_home_path)],
                    cwd=repo_dir,
                    check=True,
                )
                if sibling_old.is_dir():
                    subprocess.run(
                        ["git", "mv", str(sibling_old), str(sibling_new)],
                        cwd=repo_dir,
                        check=True,
                    )
            else:
                home_path.rename(new_home_path)
                if sibling_old.is_dir():
                    sibling_old.rename(sibling_new)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"error: file rename failed: {exc}", file=sys.stderr)
            return 1

        # Update home_path + recompute hash.
        entry["home_path"] = str(new_home_path)
        entry["manifest_hash"] = compute_manifest_hash(new_home_path)

    entry["name"] = new
    skills[new] = entry
    del skills[old]
    save_registry(registry)
    print(f"  Registry updated ({old} -> {new}).")
    return 0


# --- system subcommands ---

def cmd_system_list(args):
    """List known systems."""
    systems = load_systems()
    for name, info in systems.items():
        mode = info.get("mode", "unknown")
        print(f"  {name}  (mode={mode})")
    return 0


def cmd_system_render(args):
    """Render the CLAUDE.md for a system."""
    from claude_skills.claude_md import get_tier1, get_tier2, render_managed

    systems = load_systems()
    if args.name not in systems:
        print(f"error: unknown system '{args.name}'", file=sys.stderr)
        return 1

    sys_info = systems[args.name]
    tier2_source = sys_info.get("tier2_source")

    try:
        tier1 = get_tier1()
        tier2 = get_tier2(args.name, tier2_source=tier2_source)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Use a placeholder for user_additions so callers can see where
    # hand-edits will live.
    user_placeholder = (
        "\n# (user additions appear here, preserved verbatim across syncs)\n"
    )
    rendered = render_managed(tier1, tier2, user_additions=user_placeholder)
    sys.stdout.write(rendered)
    return 0


_SYSTEMS_YAML = (
    Path(__file__).resolve().parent.parent / "state" / "systems.yaml"
)
_SYSTEMS_TIER2_TEMPLATE = """# Machine: {name}

## Role
{description}

## Services & Tools
- (TODO: enumerate this machine's installed tools and services)

## Paths
- Projects: ~/Dropbox/Projects/
- (TODO: machine-specific paths)

## Privacy posture
Standard. (TODO: document any tighter or looser privacy expectations.)

## Constraints
- (TODO: list workload constraints, e.g. avoid long-running GPU jobs.)
"""


def cmd_system_add(args):
    """Add a new system to state/systems.yaml.

    Uses ruamel.yaml to preserve comments (the existing kberdl-dev block
    must survive). Creates a starter ``systems/<name>/CLAUDE.md`` if none
    exists. Errors if <name> is already defined.
    """
    import os
    import tempfile

    try:
        from ruamel.yaml import YAML
    except ImportError:
        print(
            "error: ruamel.yaml is required for 'system add' (preserves comments). "
            "Install with: pip install ruamel.yaml",
            file=sys.stderr,
        )
        return 1

    name = args.name
    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    yaml_rt.indent(mapping=2, sequence=4, offset=2)

    if not _SYSTEMS_YAML.exists():
        print(f"error: systems.yaml not found at {_SYSTEMS_YAML}", file=sys.stderr)
        return 1

    with open(_SYSTEMS_YAML) as f:
        doc = yaml_rt.load(f) or {}

    systems = doc.get("systems") or {}
    if name in systems:
        print(f"error: system {name!r} already exists in systems.yaml", file=sys.stderr)
        return 1

    alias = args.alias or name
    platform = args.platform
    description = (
        args.description
        or f"Added by claude-skills system add on {datetime.now().date().isoformat()}"
    )
    scopes = (
        [s.strip() for s in args.scopes.split(",") if s.strip()]
        if args.scopes
        else ["universal"]
    )
    if args.domains is None:
        domains: list[str] = []
    elif args.domains.strip() == "*":
        domains = ["*"]
    else:
        domains = [d.strip() for d in args.domains.split(",") if d.strip()]

    new_entry: dict = {
        "machine_alias": alias,
        "mode": args.mode,
        "platform": platform,
        "description": description,
        "claude_md_target": "~/.claude/CLAUDE.md",
        "commands_target": "~/.claude/commands/",
        "tier2_source": f"systems/{name}/CLAUDE.md",
        "subscriptions": {
            "scopes": scopes,
            "domains": domains,
        },
    }
    if args.requires_role:
        new_entry["subscriptions"]["requires_role"] = args.requires_role

    print(f"  system add: {name}")
    for k, v in new_entry.items():
        print(f"    {k}: {v}")

    if args.dry_run:
        print("  Dry run — systems.yaml not modified, no tier2 stub created.")
        return 0

    # Mutate the document. ruamel preserves the comments outside the
    # ``systems`` mapping (notably the kberdl-dev block, which is a
    # comment block at the bottom of the file — it stays attached to its
    # line position).
    if doc.get("systems") is None:
        doc["systems"] = {}
    doc["systems"][name] = new_entry

    # Atomic write.
    fd, tmp_path = tempfile.mkstemp(
        dir=str(_SYSTEMS_YAML.parent),
        prefix=_SYSTEMS_YAML.name + ".",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            yaml_rt.dump(doc, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, _SYSTEMS_YAML)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # Create tier2 stub if missing.
    tier2_path = _SYSTEMS_YAML.parent.parent / "systems" / name / "CLAUDE.md"
    if not tier2_path.exists():
        tier2_path.parent.mkdir(parents=True, exist_ok=True)
        tier2_path.write_text(
            _SYSTEMS_TIER2_TEMPLATE.format(name=name, description=description),
            encoding="utf-8",
        )
        print(f"  Created tier2 stub at {tier2_path}")
    else:
        print(f"  Tier2 stub already exists at {tier2_path}")

    print(
        f"  Done. Edit {tier2_path} to flesh out machine-specific content "
        "before the first sync."
    )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="claude-skills",
        description="Manage Claude Code skills, CLAUDE.md tiers, and system deployments.",
    )
    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List all registered skills")
    p_list.add_argument("--scope", choices=["universal", "platform", "domain"],
                        help="Filter by scope")
    p_list.add_argument("--home", help="Filter by home repo name")

    # inventory
    p_inv = sub.add_parser("inventory", help="Show skill inventory")
    p_inv.add_argument("--apply", action="store_true", help="Apply inventory changes")
    p_inv.add_argument("--dry-run", action="store_true", help="Dry run (default behavior)")

    # status
    p_status = sub.add_parser("status", help="Show deployment status")
    p_status.add_argument("--system", help="Filter to a specific system")

    # sync
    p_sync = sub.add_parser("sync", help="Sync skills to a target system")
    p_sync.add_argument("system", help="Target system name")
    p_sync.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    p_sync.add_argument("--dry-run", action="store_true", help="Show what would change")
    p_sync.add_argument(
        "--init-claude-md",
        action="store_true",
        help="Required if target ~/.claude/CLAUDE.md lacks managed sentinels.",
    )
    p_sync.add_argument(
        "--local-only",
        action="store_true",
        help="Bypass cross-machine cowork-inbox dispatch and run sync locally "
             "(useful for debugging or when running on the same machine).",
    )

    # diff
    p_diff = sub.add_parser("diff", help="Diff local vs deployed skills")
    p_diff.add_argument("system", help="Target system name")

    # register
    p_reg = sub.add_parser("register", help="Register a skill")
    p_reg.add_argument("home_repo", help="Home repository for the skill")
    p_reg.add_argument("path", help="Path to the skill within the repo")
    p_reg.add_argument("--update", action="store_true", help="Update if already registered")
    p_reg.add_argument("--name", help="Override skill name (defaults to filename stem)")
    p_reg.add_argument(
        "--scope",
        choices=["universal", "platform", "domain"],
        help="Override scope inference",
    )
    p_reg.add_argument("--dry-run", action="store_true", help="Show what would change without writing")

    # retire
    p_ret = sub.add_parser("retire", help="Retire a skill")
    p_ret.add_argument("skill", help="Skill name to retire")
    p_ret.add_argument("--unretire", action="store_true", help="Set retired=False instead")
    p_ret.add_argument(
        "--delete-source",
        action="store_true",
        help="Also delete the source file (and sibling dir) at home_path.",
    )

    # rename
    p_ren = sub.add_parser("rename", help="Rename a skill")
    p_ren.add_argument("old", help="Current skill name")
    p_ren.add_argument("new", help="New skill name")
    p_ren.add_argument(
        "--also-rename-file",
        action="store_true",
        help="Also rename the .md file (and sibling dir) on disk; uses git mv where applicable.",
    )
    p_ren.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    p_ren.add_argument(
        "--force",
        action="store_true",
        help="Allow renaming even when the skill is marked conflict=True.",
    )

    # system (nested subcommands)
    p_sys = sub.add_parser("system", help="System management commands")
    sys_sub = p_sys.add_subparsers(dest="system_command")

    sys_sub.add_parser("list", help="List known systems")

    p_sys_render = sys_sub.add_parser("render", help="Render CLAUDE.md for a system")
    p_sys_render.add_argument("name", help="System name")

    p_sys_add = sys_sub.add_parser("add", help="Add a new system")
    p_sys_add.add_argument("name", help="System name")
    p_sys_add.add_argument(
        "--mode",
        choices=["owned", "guest"],
        required=True,
        help="System mode: owned (full control) or guest (refuses any deploy outside ~/.claude/)",
    )
    p_sys_add.add_argument("--alias", help="machine_alias (defaults to <name>)")
    p_sys_add.add_argument("--platform", choices=["darwin", "linux"], required=True)
    p_sys_add.add_argument("--description", help="One-line role summary for the system.")
    p_sys_add.add_argument(
        "--scopes",
        help="Comma-separated subscription scopes (e.g. 'universal,platform'). "
             "Defaults to 'universal'.",
    )
    p_sys_add.add_argument(
        "--domains",
        help="Comma-separated domain ids, or '*' for all. Defaults to none.",
    )
    p_sys_add.add_argument("--requires-role", help="Optional: only deploy if hardware roles include this.")
    p_sys_add.add_argument("--dry-run", action="store_true", help="Show what would change without writing")

    return parser


DISPATCH = {
    "list": cmd_list,
    "inventory": cmd_inventory,
    "status": cmd_status,
    "sync": cmd_sync,
    "diff": cmd_diff,
    "register": cmd_register,
    "retire": cmd_retire,
    "rename": cmd_rename,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Handle system subcommands
    if args.command == "system":
        if not hasattr(args, "system_command") or args.system_command is None:
            # print system help
            parser.parse_args(["system", "--help"])
            return 0
        sys_dispatch = {
            "list": cmd_system_list,
            "render": cmd_system_render,
            "add": cmd_system_add,
        }
        handler = sys_dispatch.get(args.system_command)
        if handler:
            return handler(args)
        return 1

    handler = DISPATCH.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
