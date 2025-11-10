# Claude Commands CLI

A simple command-line tool for managing Claude Code commands across multiple projects.

## Installation

### Option 1: Install from this repository

```bash
cd /path/to/ClaudeCommands
pip install -e .
```

This installs the `claude-commands` command globally on your system.

### Option 2: Run directly without installation

```bash
cd /path/to/ClaudeCommands
python3 claude_commands.py <command> [args]
```

## Usage

### Add a project

Install Claude commands into a project:

```bash
claude-commands addproject ~/my-project
```

This will:
1. Add the project to the tracking list (stored in `data/projects.json`)
2. Create a `.claude` directory in the project (if missing)
3. Copy `SYSTEM-PROMPT.md` to `.claude/CLAUDE.md`
4. Copy all commands from `commands/` to `.claude/commands/`

**Name collision detection:** If you try to add two different projects with the same directory name, you'll get an error. Rename one of the directories to avoid the collision.

### List tracked projects

See all projects currently being tracked:

```bash
claude-commands list
```

This shows:
- Project name (directory name)
- Full path
- Whether the directory still exists (✓ or ✗)

### Update all projects

Update Claude commands in all tracked projects:

```bash
claude-commands update
```

This will:
- Re-copy `SYSTEM-PROMPT.md` and all commands to each tracked project
- Warn if a project directory is missing
- Show progress for each update

Use this command when you've modified the system prompt or commands and want to sync all your projects.

### Remove a project

Remove a project from tracking:

```bash
claude-commands removeproject my-project
```

**Note:** This only removes the project from the tracking list. It does NOT delete the `.claude` directory from your project. Delete that manually if needed.

## Project Tracking

Projects are tracked in `data/projects.json`:

```json
{
  "my-project": "/Users/you/projects/my-project",
  "another-app": "/Users/you/code/another-app"
}
```

**Key points:**
- Project names are the directory names (not full paths)
- Paths are stored as absolute paths
- This file is gitignored (local to your machine)
- The CLI manages this file - don't edit it manually

## Examples

### Typical workflow

```bash
# Install commands in a new project
claude-commands addproject ~/code/my-new-app

# Later, update the system prompt
# Edit SYSTEM-PROMPT.md
vim SYSTEM-PROMPT.md

# Push updates to all projects
claude-commands update

# See what's tracked
claude-commands list

# Remove a project you no longer need
claude-commands removeproject old-project
```

### Managing multiple projects

```bash
# Add several projects
claude-commands addproject ~/work/api-service
claude-commands addproject ~/work/frontend-app
claude-commands addproject ~/personal/blog

# Update them all at once
claude-commands update
```

## File Structure in Projects

After running `addproject`, your project will have:

```
my-project/
├── .claude/
│   ├── CLAUDE.md              # Copy of SYSTEM-PROMPT.md
│   └── commands/              # All command files
│       ├── create-prd.md
│       ├── doc-code-for-dev.md
│       ├── doc-code-usage.md
│       ├── free-agent.md
│       ├── generate-tasks.md
│       └── run_headless.md
└── (your project files)
```

## Troubleshooting

### "Error: Project name already exists"

You're trying to add a project with a directory name that's already tracked. Either:
- Remove the existing project first: `claude-commands removeproject <name>`
- Rename one of the directories to make the names unique

### "Warning: Project not found"

When running `update`, you see this for a project that was moved or deleted. Either:
- Move the project back to its original location, or
- Remove it from tracking: `claude-commands removeproject <name>`

### Permission denied

If you get permission errors when copying files:
- Check that you have write access to the target directory
- Check that `.claude` directory (if it exists) is writable

## Uninstallation

To remove the CLI:

```bash
pip uninstall claude-commands
```

This doesn't affect any `.claude` directories already installed in your projects.
