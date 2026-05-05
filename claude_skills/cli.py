#!/usr/bin/env python3
"""CLI entry point for claude-skills."""

import argparse
import sys

from claude_skills.systems import load_systems


def cmd_list(args):
    """List all registered skills."""
    print("skill list: not yet implemented")
    return 0


def cmd_inventory(args):
    """Show skill inventory, optionally apply changes."""
    print("inventory: not yet implemented")
    return 0


def cmd_status(args):
    """Show deployment status."""
    print("status: not yet implemented")
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
    sub.add_parser("list", help="List all registered skills")

    # inventory
    p_inv = sub.add_parser("inventory", help="Show skill inventory")
    p_inv.add_argument("--apply", action="store_true", help="Apply inventory changes")

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
