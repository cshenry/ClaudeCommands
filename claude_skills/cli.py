#!/usr/bin/env python3
"""CLI entry point for claude-skills."""

import argparse
import sys

from claude_skills.systems import load_systems


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
    print(f"  Conflicts:        {len(conflicts)}")
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
        print(f"\n  Conflicts (multiple homes):")
        for name in sorted(conflicts):
            print(f"    ! {name}")

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


def cmd_sync(args):
    """Sync skills to a target system."""
    print(f"sync {args.system}: not yet implemented")
    return 0


def cmd_diff(args):
    """Show diff between local and deployed skills for a system."""
    print(f"diff {args.system}: not yet implemented")
    return 0


def cmd_register(args):
    """Register a skill from a home repo."""
    print(f"register {args.home_repo} {args.path}: not yet implemented")
    return 0


def cmd_retire(args):
    """Retire a skill."""
    print(f"retire {args.skill}: not yet implemented")
    return 0


def cmd_rename(args):
    """Rename a skill."""
    print(f"rename {args.old} -> {args.new}: not yet implemented")
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
    systems = load_systems()
    if args.name not in systems:
        print(f"error: unknown system '{args.name}'", file=sys.stderr)
        return 1
    print(f"system render {args.name}: not yet implemented")
    return 0


def cmd_system_add(args):
    """Add a new system."""
    print(f"system add {args.name}: not yet implemented")
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

    # diff
    p_diff = sub.add_parser("diff", help="Diff local vs deployed skills")
    p_diff.add_argument("system", help="Target system name")

    # register
    p_reg = sub.add_parser("register", help="Register a skill")
    p_reg.add_argument("home_repo", help="Home repository for the skill")
    p_reg.add_argument("path", help="Path to the skill within the repo")
    p_reg.add_argument("--update", action="store_true", help="Update if already registered")

    # retire
    p_ret = sub.add_parser("retire", help="Retire a skill")
    p_ret.add_argument("skill", help="Skill name to retire")

    # rename
    p_ren = sub.add_parser("rename", help="Rename a skill")
    p_ren.add_argument("old", help="Current skill name")
    p_ren.add_argument("new", help="New skill name")

    # system (nested subcommands)
    p_sys = sub.add_parser("system", help="System management commands")
    sys_sub = p_sys.add_subparsers(dest="system_command")

    sys_sub.add_parser("list", help="List known systems")

    p_sys_render = sys_sub.add_parser("render", help="Render CLAUDE.md for a system")
    p_sys_render.add_argument("name", help="System name")

    p_sys_add = sys_sub.add_parser("add", help="Add a new system")
    p_sys_add.add_argument("name", help="System name")
    p_sys_add.add_argument("--mode", default="interactive", help="System mode (interactive/headless)")

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
