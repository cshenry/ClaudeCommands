# Claude Code Headless Execution System

**A unified, consistent framework for running Claude Code in headless mode**

Version: 1.0.0
Created: October 30, 2024
Status: Production Ready

## What Is This?

This system provides a standardized approach to running Claude Code in headless mode with:

- ✅ **Single JSON output format** for all commands
- ✅ **Single system prompt** used everywhere
- ✅ **Tasks tracked in JSON** (not separate files)
- ✅ **Complete file operation tracking**
- ✅ **Stateful resumption support**
- ✅ **Comprehensive documentation**

## Installation

To install the ClaudeCommands system files to your home directory:

```bash
# Clone the repository
git clone <repository-url>
cd ClaudeCommands

# Run the installation script
./scripts/install.sh
```

This will:
- Copy `SYSTEM-PROMPT.md` to `~/.claude/CLAUDE.md`
- Copy all command files to `~/.claude/commands/`

After installation, you can use the installed files with:

```bash
claude code headless \
  --system-prompt ~/.claude/CLAUDE.md \
  --command ~/.claude/commands/<command>.md \
  --request ./request.json \
  --output ./claude-output.json
```

## Quick Start

### 1. Basic Usage

```bash
# Create a request file
cat > request.json << 'EOF'
{
  "request_type": "create-prd",
  "description": "Create PRD for user profile editing feature",
  "context": {
    "feature_request": "Allow users to edit their profile information..."
  }
}
EOF

# Run command
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/create-prd.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./workspace

# Check output
cat claude-output.json | jq '.status, .session_summary'
```

### 2. Available Commands

| Command | Purpose | Output |
|---------|---------|--------|
| `create-prd` | Generate Product Requirements Documents | PRD in `orchestrator/PRD/` |
| `generate-tasks` | Break PRDs into implementation tasks | Tasks in JSON |
| `doc-code-for-dev` | Document internal architecture | Docs in `orchestrator/docs/` |
| `doc-code-usage` | Document public APIs and usage | Docs in `orchestrator/docs/` |
| `free-agent` | Execute simple tasks from natural language | Varies |

### 3. Unified Output Format

Every command produces a `claude-output.json` with:

```json
{
  "command_type": "create-prd",
  "status": "complete|incomplete|user_query|error",
  "session_summary": "What happened in this session",
  "tasks": [
    {
      "task_id": "1.0",
      "description": "Task description",
      "status": "completed|in_progress|pending"
    }
  ],
  "files": {
    "created": [...],
    "modified": [...],
    "deleted": [...]
  },
  "artifacts": {
    "command_specific": "outputs"
  },
  "comments": ["Important notes"]
}
```

## Repository Structure

```
.
├── README.md                      # This file
├── SYSTEM-PROMPT.md               # Universal instructions (CRITICAL)
├── unified-output-schema.json     # JSON schema for outputs
├── commands/                      # Command definitions
│   ├── create-prd.md
│   ├── generate-tasks.md
│   ├── doc-code-for-dev.md
│   ├── doc-code-usage.md
│   └── free-agent.md
├── docs/                          # Documentation
│   ├── HANDOFF.md                 # Project context
│   ├── SUMMARY.md                 # System overview
│   ├── ARCHITECTURE.md            # System design
│   ├── EXAMPLES.md                # Detailed examples
│   └── REQUEST-FORMAT.md          # Request file specs
├── examples/                      # Example request files
│   ├── create-prd-example.json
│   ├── generate-tasks-example.json
│   └── ...
└── scripts/                       # Automation scripts
    ├── install.sh                 # Installation script
    ├── run-command.sh
    └── validate-output.sh
```

## Key Concepts

### Two-File Input Pattern

Every execution requires:
1. **Command file** (`commands/*.md`) - Defines what type of activity
2. **Request file** (`request.json`) - Your specific requirements
3. **System prompt** (`SYSTEM-PROMPT.md`) - Universal instructions

### Task Management

Tasks are stored IN the JSON output, not separate markdown files:
- Hierarchical structure (parent/child tasks)
- Status tracking per task
- Complete audit trail

### File Tracking

Every file operation is documented:
- Created files with purpose and type
- Modified files with changes
- Deleted files
- Complete audit trail

## Example Workflows

### Workflow 1: New Feature (PRD → Tasks)

```bash
# 1. Create PRD
cat > prd-request.json << 'EOF'
{
  "request_type": "create-prd",
  "description": "Create PRD for new feature",
  "context": { "feature_request": "..." }
}
EOF

claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/create-prd.md \
  --request ./prd-request.json \
  --output ./claude-output.json

# 2. Extract PRD path
PRD=$(jq -r '.artifacts.prd_filename' claude-output.json)

# 3. Generate tasks from PRD
cat > tasks-request.json << EOF
{
  "request_type": "generate-tasks",
  "description": "Generate implementation tasks",
  "context": {
    "prd_file": "$PRD"
  }
}
EOF

claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/generate-tasks.md \
  --request ./tasks-request.json \
  --output ./claude-output.json
```

### Workflow 2: Quick Task

```bash
cat > task-request.json << 'EOF'
{
  "request_type": "free-agent",
  "description": "Rename function across project",
  "context": {
    "task": "Rename getCwd to getCurrentWorkingDirectory"
  }
}
EOF

claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/free-agent.md \
  --request ./task-request.json \
  --output ./claude-output.json
```

## Documentation

- **[docs/HANDOFF.md](docs/HANDOFF.md)** - Complete project context and history
- **[docs/SUMMARY.md](docs/SUMMARY.md)** - System overview and migration guide
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Complete system design
- **[docs/EXAMPLES.md](docs/EXAMPLES.md)** - Detailed usage examples
- **[docs/REQUEST-FORMAT.md](docs/REQUEST-FORMAT.md)** - Request file specifications

## Status Handling

The system supports four status types:

- **`complete`** - Task finished successfully
- **`incomplete`** - Task partially done (see comments)
- **`user_query`** - Need user input (see `queries_for_user`)
- **`error`** - Something went wrong (see `errors`)

### Handling User Queries

```bash
# If status is "user_query"
jq '.queries_for_user' claude-output.json

# Create response
cat > response.json << 'EOF'
{
  "request_type": "create-prd",
  "resume_session": true,
  "user_responses": {
    "query_1": "answer to question 1",
    "query_2": "answer to question 2"
  }
}
EOF

# Resume execution
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/create-prd.md \
  --request ./response.json \
  --output ./claude-output.json
```

## Why This System?

### Before
- ❌ Different JSON format per command
- ❌ Tasks in separate markdown files
- ❌ Inconsistent documentation
- ❌ Hard to track file operations
- ❌ No standard resumption pattern

### After
- ✅ Single JSON format for all commands
- ✅ Tasks in JSON output
- ✅ Consistent documentation
- ✅ Complete file tracking
- ✅ Standard resumption support

## Getting Help

1. **Quick questions** → See [docs/SUMMARY.md](docs/SUMMARY.md)
2. **Examples** → See [docs/EXAMPLES.md](docs/EXAMPLES.md)
3. **System design** → See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
4. **Request format** → See [docs/REQUEST-FORMAT.md](docs/REQUEST-FORMAT.md)

## Contributing

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for extension patterns and design principles.

## License

MIT

---

**The Bottom Line**: A unified, consistent, well-documented system for Claude Code headless execution with complete tracking and standard output format.
