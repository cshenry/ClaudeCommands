# System Design Summary

## What I've Created

I've redesigned your Claude Code headless system to be **consistent, unified, and well-documented**. Here's everything I created:

## Core System Files

### 1. **SYSTEM-PROMPT.md** 
- Universal instructions for ALL commands
- Explains the two-file input pattern (command + request)
- Defines the unified JSON output format
- Critical principles (user can't see terminal, document everything)
- **Use this for every Claude Code execution**

### 2. **unified-output-schema.json**
- Single JSON schema for all outputs
- Validates the `claude-output.json` file
- Same structure for all commands (different subsets used)

### 3. **ARCHITECTURE.md**
- Complete system architecture documentation
- How all the pieces fit together
- Design decisions and rationale
- Extension patterns
- Monitoring and observability guidance

### 4. **HEADLESS-EXAMPLES.md**
- Detailed examples for each command
- Complete request files
- Sample command invocations
- Expected outputs with explanations
- Automation scripts

### 5. **request-format.md**
- Standard request file format
- Schemas for each command type
- Examples for different scenarios
- Resumption patterns
- Validation guidelines

## Command Files (Updated)

### 6. **commands/create-prd.md**
- Generate PRD from feature requests
- Save PRDs to `PRDs/[NNNN]-[name].md`
- May ask clarifying questions
- Outputs PRD reference in JSON

### 7. **commands/generate-tasks.md**
- Break PRD into implementation tasks
- Two-phase execution (parent tasks → sub-tasks)
- Tasks stored IN the JSON output
- No separate markdown files
- Links tasks to relevant files

### 8. **commands/doc-code-for-dev.md**
- Document internal architecture
- For developers who will modify code
- Creates comprehensive markdown docs
- Saves to `agent-io/docs/[project]-architecture-documentation.md`

### 9. **commands/doc-code-usage.md**
- Document public APIs and usage
- For external users of the code
- Shows how to USE, not how it works internally
- Saves to `agent-io/docs/[project]-usage-documentation.md`

### 10. **commands/free-agent.md**
- Execute simple tasks from natural language
- Git operations, file operations, data processing
- Autonomous execution with minimal questions
- Documents everything done

## Key Improvements Over Old System

### ✅ Unified Output Format
**Before**: Each command had different JSON format
**After**: Single schema, all commands use same structure

### ✅ Tasks in JSON
**Before**: Tasks in separate markdown files
**After**: Tasks tracked directly in `claude-output.json` with status

### ✅ Consistent Documentation
**Before**: Different patterns per command
**After**: Single system prompt, command-specific files only cover process

### ✅ File Tracking
**Before**: Hard to know what files were created
**After**: Every file operation documented in JSON

### ✅ Stateful Resumption
**Before**: Hard to resume after user input
**After**: Standard pattern with context saving/loading

## How to Use the New System

### Basic Pattern

```bash
# 1. Create a request file
cat > request.json << 'EOF'
{
  "request_type": "create-prd",
  "description": "Create PRD for user profile editing",
  "context": {
    "feature_request": "Add profile editing...",
    ...
  }
}
EOF

# 2. Run the command
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/create-prd.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./my-project

# 3. Check the output
cat claude-output.json | jq '.status'
cat claude-output.json | jq '.artifacts.prd_filename'
```

### What Gets Created

```
my-project/
├── PRDs/                    # From create-prd
│   └── 0001-feature.md
├── docs/                    # From doc-code commands
│   ├── project-architecture-documentation.md
│   └── project-usage-documentation.md
├── src/                     # From implementation
│   └── ...
└── claude-output.json       # Always created
```

### The JSON Output

```json
{
  "command_type": "create-prd",
  "status": "complete",
  "session_id": "session-abc123",
  "parent_session_id": null,
  "session_summary": "Created PRD with 8 requirements",

  "tasks": [                  // Tasks tracked in JSON
    {
      "task_id": "1.0",
      "description": "Generate PRD content",
      "status": "completed"
    }
  ],
  
  "files": {                  // NEW: All files tracked
    "created": [
      {
        "path": "agent-io/prds/0001-feature.md",
        "purpose": "Product Requirements Document",
        "type": "markdown"
      }
    ],
    "modified": [],
    "deleted": []
  },

  "artifacts": {              // Command-specific outputs
    "prd_filename": "agent-io/prds/0001-feature.md"
  },
  
  "comments": [               // Important notes
    "PRD includes 8 functional requirements",
    "Assumed web-only initially"
  ]
}
```

## Migration from Old System

### What Changed

1. **Output Format**: Now unified across all commands
2. **Task Storage**: Tasks go in JSON, not separate files
3. **PRD Location**: Now in `PRDs/` directory (not `/tasks/`)
4. **System Prompt**: Single universal prompt for all commands
5. **Request Format**: Standardized JSON structure

### Migration Steps

1. **Update Scripts**: Use new command invocation pattern
2. **Remove Task Files**: Tasks now in `claude-output.json`
3. **Update Paths**: PRDs go in `PRDs/`, docs in `docs/`
4. **Adopt JSON Output**: Read from `claude-output.json` instead of multiple files
5. **Use System Prompt**: Always include `--system-prompt SYSTEM-PROMPT.md`

## Example Workflows

### Workflow 1: Create PRD and Generate Tasks

```bash
# Step 1: Create PRD
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/create-prd.md \
  --request ./prd-request.json \
  --output ./prd-output.json \
  --working-dir ./project

# Step 2: Extract PRD filename
PRD=$(jq -r '.artifacts.prd_filename' prd-output.json)

# Step 3: Generate tasks
cat > tasks-request.json << EOF
{
  "request_type": "generate-tasks",
  "description": "Generate tasks for PRD",
  "context": {
    "prd_file": "$PRD",
    "codebase_path": "./src"
  }
}
EOF

claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/generate-tasks.md \
  --request ./tasks-request.json \
  --output ./tasks-output.json \
  --working-dir ./project

# Step 4: View tasks
jq '.tasks' tasks-output.json
```

### Workflow 2: Handle User Queries

```bash
# Initial execution
claude code headless ... > output1.json

# Check status
STATUS=$(jq -r '.status' output1.json)

if [ "$STATUS" = "user_query" ]; then
  # Show questions
  jq '.queries_for_user' output1.json
  
  # Create response
  cat > response.json << 'EOF'
  {
    "request_type": "create-prd",
    "previous_context": "...(from output1.json)...",
    "user_responses": {
      "query_1": "answer here"
    }
  }
  EOF
  
  # Resume execution
  claude code headless ... > output2.json
fi
```

## File Organization

```
your-project/
├── SYSTEM-PROMPT.md              # Universal instructions
├── unified-output-schema.json    # Output validation
├── ARCHITECTURE.md               # System design docs
├── HEADLESS-EXAMPLES.md         # Detailed examples
├── request-format.md            # Request file spec
├── commands/                     # Command definitions
│   ├── create-prd.md
│   ├── generate-tasks.md
│   ├── doc-code-for-dev.md
│   ├── doc-code-usage.md
│   └── free-agent.md
└── project-work/                 # Your actual projects
    ├── request.json              # Current request
    ├── claude-output.json        # Latest output
    ├── PRDs/                     # Generated PRDs
    ├── docs/                     # Generated docs
    └── src/                      # Your code
```

## Quick Reference

### Command Types
- `create-prd` - Generate PRD
- `generate-tasks` - Create task list
- `doc-code-for-dev` - Document architecture
- `doc-code-usage` - Document usage/API
- `free-agent` - Execute tasks

### Status Values
- `complete` - Done successfully
- `incomplete` - Partial work, some failed
- `user_query` - Needs user input
- `error` - Failed completely

### Key JSON Fields
- `command_type` - Which command ran
- `status` - Completion status
- `session_summary` - What happened
- `tasks` - Task list with status
- `files` - All file operations
- `artifacts` - Command outputs
- `queries_for_user` - Questions if needed
- `comments` - Important notes
- `context` - For resumption

## Next Steps

1. **Test the System**: Try running each command with the examples
2. **Validate Outputs**: Use the schema to validate JSON outputs
3. **Update Scripts**: Migrate your existing scripts to new format
4. **Create Templates**: Build request templates for common scenarios
5. **Automate**: Build scripts for common workflows

## Documentation to Read

**Start Here**:
1. `SYSTEM-PROMPT.md` - Understand the universal instructions
2. `commands/create-prd.md` - See how a command is structured
3. `HEADLESS-EXAMPLES.md` - See complete examples

**Reference**:
- `ARCHITECTURE.md` - Deep dive on system design
- `request-format.md` - Request file specifications
- `unified-output-schema.json` - Output validation

## Support

All files are well-documented with:
- Clear purpose statements
- Step-by-step processes
- Quality checklists
- Example outputs
- Troubleshooting guides

Each command file is self-contained and references the system prompt for shared concerns.

## Summary

You now have:
- ✅ Single unified output format
- ✅ Consistent system prompt for all commands
- ✅ Tasks tracked in JSON
- ✅ Complete file operation tracking
- ✅ Stateful resumption support
- ✅ Comprehensive documentation
- ✅ Real-world examples
- ✅ Clear migration path

The system is ready to use. Start with the examples in `HEADLESS-EXAMPLES.md`!
