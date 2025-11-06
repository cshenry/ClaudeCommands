# Allowed Tools Guide for Claude Code Commands

This document explains the `-AllowedTools` flag permissions needed for each command in this repository.

## Overview

The `-AllowedTools` flag in Claude Code restricts which tools (permissions) Claude can use during execution. This provides better security and control by limiting Claude's capabilities to only what's needed for each specific command.

## Command Permissions Summary

### 1. create-prd

**Purpose:** Generate a comprehensive Product Requirements Document (PRD) from a user's feature request.

**Allowed Tools:**
- `Read` - Read existing PRD files to determine sequence numbering
- `Write` - Create new PRD markdown files in orchestrator/PRD/ directory
- `Bash` - Create directories if they don't exist (mkdir -p)
- `Glob` - Find existing PRD files to determine the next sequence number

**Why these tools:**
- The command needs to check what PRDs already exist (Read, Glob)
- It creates new markdown documentation files (Write)
- It may need to create the PRD directory structure (Bash)

---

### 2. free-agent

**Purpose:** Execute simple, well-defined tasks from natural language requests (file operations, git operations, data processing, etc.)

**Allowed Tools:**
- `Read` - Read files that need to be processed or analyzed
- `Write` - Create new files as requested
- `Edit` - Modify existing files (refactoring, renaming, updating)
- `Bash` - Execute git commands, run scripts, install packages, system operations
- `Glob` - Find files by pattern for batch operations
- `Grep` - Search file contents for text/code patterns

**Why these tools:**
- This is the most versatile command, handling various tasks
- File operations require Read, Write, and Edit
- Git operations and system tasks require Bash
- Finding and searching files requires Glob and Grep

---

### 3. doc-code-for-dev

**Purpose:** Create comprehensive architecture documentation that enables developers to understand, modify, and extend a codebase.

**Allowed Tools:**
- `Read` - Read source code files to understand architecture
- `Write` - Create architecture documentation markdown files
- `Bash` - Generate directory trees, analyze project structure
- `Glob` - Find files to map project structure
- `Grep` - Search for patterns, classes, functions in code
- `Task` - Launch specialized agents for analyzing large codebases

**Why these tools:**
- Must read and analyze source code extensively (Read, Grep)
- Needs to map project structure (Bash, Glob)
- Creates documentation files (Write)
- May delegate complex analysis to specialized agents (Task)

---

### 4. doc-code-usage

**Purpose:** Create comprehensive usage documentation showing developers how to USE a codebase as a library, tool, or API.

**Allowed Tools:**
- `Read` - Read code, README files, examples, and test files
- `Write` - Create usage documentation markdown files
- `Bash` - Test CLI commands, check package metadata
- `Glob` - Find documentation files, examples, test files
- `Grep` - Search for public APIs, docstrings, type definitions
- `Task` - Launch specialized agents for comprehensive API discovery

**Why these tools:**
- Must read various file types (code, docs, examples) - Read
- Searches for public APIs and examples (Grep, Glob)
- May need to test CLI functionality (Bash)
- Creates usage documentation (Write)
- May delegate API discovery to specialized agents (Task)

---

### 5. generate-tasks

**Purpose:** Generate a detailed, hierarchical task list from an existing PRD.

**Allowed Tools:**
- `Read` - Read PRD files and existing codebase files
- `Bash` - Analyze codebase structure if needed
- `Glob` - Find relevant files in the codebase
- `Grep` - Search codebase for existing patterns and components
- `Task` - Launch specialized agents for codebase exploration

**Why these tools:**
- Must read the PRD file (Read)
- Analyzes existing codebase to understand what needs to be created vs modified (Read, Glob, Grep)
- May need to understand project structure (Bash)
- May delegate codebase exploration to specialized agents (Task)
- Note: Does NOT need Write - tasks are output in JSON format, not written to files

---

## Usage Examples

### Using the -AllowedTools flag

When invoking Claude Code with these commands, you can restrict permissions like this:

```bash
# For create-prd command
claude-code -AllowedTools "Read,Write,Bash,Glob" -request create-prd-request.json

# For free-agent command
claude-code -AllowedTools "Read,Write,Edit,Bash,Glob,Grep" -request free-agent-request.json

# For doc-code-for-dev command
claude-code -AllowedTools "Read,Write,Bash,Glob,Grep,Task" -request doc-code-for-dev-request.json

# For doc-code-usage command
claude-code -AllowedTools "Read,Write,Bash,Glob,Grep,Task" -request doc-code-usage-request.json

# For generate-tasks command
claude-code -AllowedTools "Read,Bash,Glob,Grep,Task" -request generate-tasks-request.json
```

## Tool Descriptions

Here's what each tool allows Claude to do:

- **Read** - Read files from the filesystem
- **Write** - Create new files
- **Edit** - Modify existing files
- **Bash** - Execute shell commands (git, mkdir, npm, etc.)
- **Glob** - Find files using glob patterns (e.g., "**/*.js")
- **Grep** - Search file contents using regex patterns
- **Task** - Launch specialized AI agents for complex subtasks

## Security Considerations

1. **Least Privilege:** Each command lists only the minimum tools needed to function
2. **Bash Restrictions:** Commands that include Bash can execute arbitrary shell commands - review these carefully
3. **Task Agent:** Commands with Task can launch sub-agents with their own tool access
4. **Write/Edit vs Read:** Separate write operations from read-only operations where possible

## Customization

You can further restrict permissions based on your security requirements:

- **Read-only analysis:** Remove Write, Edit, and Bash for analysis-only tasks
- **No agent delegation:** Remove Task to prevent sub-agent creation
- **No shell access:** Remove Bash to prevent any command execution

## Example JSON Configuration

Each command's example JSON file now includes the `allowed_tools` field:

```json
{
  "request_type": "create-prd",
  "description": "Create PRD for user profile editing feature",
  "allowed_tools": [
    "Read",
    "Write",
    "Bash",
    "Glob"
  ],
  "context": {
    ...
  }
}
```

This makes it easy to maintain consistent permissions across command invocations.
