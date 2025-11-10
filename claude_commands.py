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

    def _copy_files_to_project(self, project_path: Path) -> None:
        """Copy SYSTEM-PROMPT.md and commands to project's .claude directory.

        Args:
            project_path: Path to the project directory
        """
        claude_dir = project_path / ".claude"
        claude_dir.mkdir(exist_ok=True)

        # Copy SYSTEM-PROMPT.md to .claude/CLAUDE.md
        target_prompt = claude_dir / "CLAUDE.md"
        shutil.copy2(self.system_prompt, target_prompt)
        print(f"  ✓ Copied SYSTEM-PROMPT.md to {target_prompt.relative_to(project_path)}")

        # Copy commands directory
        target_commands = claude_dir / "commands"
        if target_commands.exists():
            shutil.rmtree(target_commands)
        shutil.copytree(self.commands_dir, target_commands)

        # Count the number of commands copied
        command_files = list(target_commands.glob("*.md"))
        print(f"  ✓ Copied {len(command_files)} commands to {target_commands.relative_to(project_path)}")

    def addproject(self, directory: str) -> None:
        """Add a project directory to the tracking list.

        Args:
            directory: Path to the project directory
        """
        # Convert to absolute path
        project_path = Path(directory).resolve()

        # Check if directory exists
        if not project_path.exists():
            print(f"Error: Directory does not exist: {directory}")
            sys.exit(1)

        if not project_path.is_dir():
            print(f"Error: Not a directory: {directory}")
            sys.exit(1)

        # Get project name (directory name)
        project_name = project_path.name

        # Load existing projects
        projects = self._load_projects()

        # Check for name collision
        if project_name in projects:
            existing_path = projects[project_name]
            if existing_path != str(project_path):
                print(f"Error: Project name '{project_name}' already exists with path:")
                print(f"  Existing: {existing_path}")
                print(f"  New:      {project_path}")
                print(f"Please rename one of the directories to avoid collision.")
                sys.exit(1)
            else:
                print(f"Project '{project_name}' is already tracked at this path.")
                print(f"Updating files...")

        # Add project to tracking
        projects[project_name] = str(project_path)
        self._save_projects(projects)

        # Copy files
        print(f"\nAdding project '{project_name}':")
        print(f"  Path: {project_path}")
        self._copy_files_to_project(project_path)

        print(f"\n✓ Project '{project_name}' added successfully")

    def update(self) -> None:
        """Update all tracked projects with latest commands."""
        projects = self._load_projects()

        if not projects:
            print("No projects are currently tracked.")
            print("Use 'claude-commands addproject <directory>' to add a project.")
            return

        print(f"Updating {len(projects)} project(s)...\n")

        updated_count = 0
        missing_count = 0

        for project_name, project_path_str in sorted(projects.items()):
            project_path = Path(project_path_str)

            if not project_path.exists():
                print(f"⚠ Warning: Project '{project_name}' not found at {project_path}")
                missing_count += 1
                continue

            print(f"Updating '{project_name}':")
            print(f"  Path: {project_path}")
            self._copy_files_to_project(project_path)
            print()
            updated_count += 1

        print(f"✓ Updated {updated_count} project(s)")
        if missing_count > 0:
            print(f"⚠ {missing_count} project(s) not found (consider removing them)")

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
  claude-commands addproject ~/my-project
  claude-commands update
  claude-commands list
  claude-commands removeproject my-project
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # addproject command
    parser_add = subparsers.add_parser(
        'addproject',
        help='Add a project directory to tracking and install Claude commands'
    )
    parser_add.add_argument('directory', help='Path to project directory')

    # update command
    subparsers.add_parser(
        'update',
        help='Update all tracked projects with latest Claude commands'
    )

    # removeproject command
    parser_remove = subparsers.add_parser(
        'removeproject',
        help='Remove a project from tracking'
    )
    parser_remove.add_argument('project_name', help='Name of project to remove')

    # list command
    subparsers.add_parser(
        'list',
        help='List all tracked projects'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize CLI
    cli = ClaudeCommandsCLI()

    # Execute command
    if args.command == 'addproject':
        cli.addproject(args.directory)
    elif args.command == 'update':
        cli.update()
    elif args.command == 'removeproject':
        cli.removeproject(args.project_name)
    elif args.command == 'list':
        cli.list()


if __name__ == '__main__':
    main()
