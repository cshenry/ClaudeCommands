#!/usr/bin/env python3
"""
Claude Commands CLI - Manage Claude Code commands across multiple projects.

This CLI helps you install and update Claude commands in your project repositories.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List


class ClaudeCommandsCLI:
    """CLI for managing Claude commands across projects."""

    def __init__(self):
        """Initialize CLI with paths to repo root and data directory."""
        # Get the directory where this script is located (repo root)
        self.repo_root = Path(__file__).parent.resolve()
        self.data_dir = self.repo_root / "data"
        self.projects_file = self.data_dir / "projects.json"
        self.system_prompt = self.repo_root / "SYSTEM-PROMPT.md"
        self.commands_dir = self.repo_root / "commands"

        # Ensure data directory exists
        self.data_dir.mkdir(exist_ok=True)

        # Initialize projects file if it doesn't exist
        if not self.projects_file.exists():
            self._save_projects({})

    def _load_projects(self) -> Dict[str, str]:
        """Load projects from JSON file.

        Returns:
            Dict mapping project name to full path
        """
        try:
            with open(self.projects_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {self.projects_file} contains invalid JSON")
            sys.exit(1)

    def _save_projects(self, projects: Dict[str, str]) -> None:
        """Save projects to JSON file.

        Args:
            projects: Dict mapping project name to full path
        """
        with open(self.projects_file, 'w') as f:
            json.dump(projects, f, indent=2, sort_keys=True)

    def removeproject(self, project_name: str) -> None:
        """Remove a project from tracking.

        Args:
            project_name: Name of the project (directory name)
        """
        projects = self._load_projects()

        if project_name not in projects:
            print(f"Error: Project '{project_name}' is not tracked.")
            print(f"\nCurrently tracked projects:")
            if projects:
                for name in sorted(projects.keys()):
                    print(f"  - {name}")
            else:
                print("  (none)")
            sys.exit(1)

        project_path = projects[project_name]
        del projects[project_name]
        self._save_projects(projects)

        print(f"✓ Project '{project_name}' removed from tracking")
        print(f"  Path was: {project_path}")
        print(f"\nNote: The .claude directory in the project was NOT deleted.")
        print(f"      Delete it manually if needed.")

    def list(self) -> None:
        """List all tracked projects."""
        projects = self._load_projects()

        if not projects:
            print("No projects are currently tracked.")
            print("Use 'claude-commands addproject <directory>' to add a project.")
            return

        print(f"Tracked projects ({len(projects)}):\n")
        for project_name in sorted(projects.keys()):
            project_path = Path(projects[project_name])
            exists = "✓" if project_path.exists() else "✗"
            print(f"  {exists} {project_name}")
            print(f"      {projects[project_name]}")
            print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage Claude Code commands across multiple projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  claude-commands list
  claude-commands removeproject my-project

Note: The 'install', 'update', and 'addproject' subcommands were removed
on 2026-04-15 because they performed destructive `rmtree` overwrites of
CLAUDE.md and .claude/commands/ across all tracked projects. The project
registry in AIAssistant (state/project_registry.yaml) is now the master
of project tracking. A safe additive sync tool is planned as a
replacement. See agent-io/audits/claude-skills-2026-04-15.md in AIAssistant.
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # removeproject command (reads legacy data/projects.json — kept for cleanup)
    parser_remove = subparsers.add_parser(
        'removeproject',
        help='Remove a project from legacy tracking (data/projects.json)'
    )
    parser_remove.add_argument('project_name', help='Name of project to remove')

    # list command (reads legacy data/projects.json — kept for audit)
    subparsers.add_parser(
        'list',
        help='List legacy tracked projects (data/projects.json)'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize CLI
    cli = ClaudeCommandsCLI()

    # Execute command
    if args.command == 'removeproject':
        cli.removeproject(args.project_name)
    elif args.command == 'list':
        cli.list()


if __name__ == '__main__':
    main()
