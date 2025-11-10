# Claude Code Headless System Architecture

## Overview

This document describes the complete architecture of the Claude Code headless execution system - a framework for running Claude autonomously with structured input/output and comprehensive documentation.

## Design Philosophy

### Core Principles

1. **Single Source of Truth**: One system prompt, one output schema for all commands
2. **Complete Documentation**: User never sees terminal - everything goes in JSON output
3. **Stateful Resumption**: Can pause for user input and resume exactly where left off
4. **Task Visibility**: All tasks tracked in JSON, not external files
5. **File Transparency**: Every file operation is documented
6. **Autonomous Execution**: Claude works independently, asks questions only when necessary

## System Components

### 1. System Prompt (`SYSTEM-PROMPT.md`)

**Purpose**: Universal instructions that apply to ALL command executions

**Contents**:
- How the system works (two-file input pattern)
- Output format requirements (unified JSON schema)
- Critical principles (user can't see terminal, document everything)
- Best practices for execution
- Error handling guidelines

**Key Feature**: This file is the same for every command - command-specific instructions go in separate command files.

### 2. Command Files (`commands/*.md`)

**Purpose**: Define WHAT to do for specific command types

**Current Commands**:
- `create-prd.md` - Generate Product Requirements Documents
- `generate-tasks.md` - Break PRDs into implementation tasks
- `doc-code-for-dev.md` - Document internal architecture
- `doc-code-usage.md` - Document public APIs and usage
- `free-agent.md` - Execute simple tasks from natural language

**Structure**:
```markdown
# Command: [name]
## Purpose
## Command Type
## Input (what's expected in request file)
## Process (step-by-step what to do)
## Output Requirements
## Quality Checklist
```

**Key Feature**: Commands reference the system prompt for output format - they don't duplicate that information.

### 3. Request Files (`request.json`)

**Purpose**: Contain user's specific requirements for this execution

**Standard Schema**:
```json
{
  "request_type": "command-name",
  "description": "what user wants",
  "context": {
    // command-specific context
  },
  "constraints": {
    // optional preferences
  },
  "previous_context": "for resumption",
  "user_responses": {
    // answers to queries
  }
}
```

**Key Feature**: Structured but flexible - each command type can define its own context fields.

### 4. Output File (`claude-output.json`)

**Purpose**: Complete record of execution - the ONLY way user sees results

**Unified Schema**:
```json
{
  "command_type": "string",
  "status": "complete|incomplete|user_query|error",
  "session_summary": "what happened",
  "tasks": [...],          // hierarchical task tracking
  "files": {...},          // all file operations
  "artifacts": {...},      // command-specific outputs
  "queries_for_user": [...], // questions if needed
  "comments": [...],       // important notes
  "context": "...",        // for resumption
  "metrics": {...},        // optional stats
  "errors": [...]          // error details
}
```

**Key Feature**: Same structure for all commands - different commands use different subsets of fields.

### 5. Output Artifacts

**Purpose**: The actual deliverables (PRDs, documentation, code, etc.)

**Locations**:
- PRDs: `agent-io/prds/[NNNN]-[name].md`
- Documentation: `agent-io/docs/[name]-documentation.md`
- Code: Project-appropriate locations
- Tests: Alongside code files

**Key Feature**: Real files are created, but their locations and purposes are documented in the JSON output.

## Information Flow

### Standard Execution Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Claude Code CLI                       │
│                                                          │
│  Reads:                                                  │
│  ├─ SYSTEM-PROMPT.md      (universal instructions)      │
│  ├─ commands/[cmd].md     (command-specific process)    │
│  └─ request.json          (user's specific request)     │
│                                                          │
│  Executes:                                               │
│  ├─ Analyzes request                                     │
│  ├─ Follows command process                              │
│  ├─ Creates artifacts                                    │
│  ├─ Tracks everything                                    │
│  └─ Handles errors gracefully                            │
│                                                          │
│  Writes:                                                 │
│  ├─ claude-output.json    (complete execution record)   │
│  └─ [artifacts]           (PRDs, docs, code, etc.)      │
└─────────────────────────────────────────────────────────┘
```

### Resumption Flow (After user_query)

```
┌─────────────────────────────────────────────────────────┐
│              Execution Paused for User Input             │
│                    (Session abc123)                      │
│                                                          │
│  Previous Output:                                        │
│  {                                                       │
│    "status": "user_query",                               │
│    "session_id": "session-abc123",                       │
│    "parent_session_id": null,                            │
│    "queries_for_user": [...questions...]                 │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────┐
│                   User Provides Answers                  │
│              (New Session xyz789 created)                │
│                                                          │
│  New request.json:                                       │
│  {                                                       │
│    "request_type": "create-prd",                         │
│    "user_responses": {                                   │
│      "query_1": "answer",                                │
│      "query_2": {"choice_id": "..."}                     │
│    }                                                     │
│  }                                                       │
│                                                          │
│  Note: parent_session_id automatically set to abc123     │
└─────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────┐
│                 Claude Resumes Execution                 │
│                    (Session xyz789)                      │
│                                                          │
│  ├─ Loads context from parent session abc123             │
│  ├─ Incorporates user responses                          │
│  ├─ Continues from where it left off                     │
│  └─ Completes execution or asks more questions           │
│                                                          │
│  Output includes:                                        │
│  {                                                       │
│    "session_id": "session-xyz789",                       │
│    "parent_session_id": "session-abc123",                │
│    "status": "complete"                                  │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
```

## Task Management Architecture

### Traditional Approach (Old System)
```
PRD (markdown) → Tasks (separate markdown) → Implementation
                       ↓
                Tasks hard to track
                No status visibility
                Implementation separate from tracking
```

### New Approach
```
PRD (markdown) → Tasks (in JSON output) → Implementation updates JSON
                       ↓
                Tasks in structured format
                Status always visible
                Implementation progress tracked
```

### Task Structure

```json
{
  "tasks": [
    {
      "task_id": "1.0",           // Parent task
      "description": "High-level milestone",
      "status": "pending",
      "parent_task_id": null,
      "notes": ""
    },
    {
      "task_id": "1.1",           // Sub-task
      "description": "Specific action",
      "status": "completed",
      "parent_task_id": "1.0",
      "notes": "Completed without issues"
    },
    {
      "task_id": "1.2",           // Sub-task
      "description": "Another action",
      "status": "in_progress",
      "parent_task_id": "1.0",
      "notes": "Blocked on dependency"
    }
  ]
}
```

**Benefits**:
- Hierarchical structure (parent/child relationships)
- Status tracking per task
- Notes for context and issues
- Easy to parse and analyze
- No separate markdown files to maintain

## File Tracking Architecture

### Every File Operation is Documented

```json
{
  "files": {
    "created": [
      {
        "path": "agent-io/prds/0001-feature.md",
        "purpose": "Product Requirements Document",
        "type": "markdown"
      },
      {
        "path": "src/components/Feature.tsx",
        "purpose": "Main feature component",
        "type": "code"
      }
    ],
    "modified": [
      {
        "path": "src/App.tsx",
        "changes": "Added route for new feature"
      }
    ],
    "deleted": [
      {
        "path": "temp/draft.md",
        "reason": "Replaced by final PRD"
      }
    ]
  }
}
```

**Benefits**:
- Complete audit trail
- Easy to review what changed
- Clear purpose for each file
- Can validate execution
- Supports rollback if needed

## Command-Specific Patterns

### Pattern 1: Simple Execution (doc-code, free-agent)

```
Input → Execute → Output
```

Single-phase execution:
1. Read request
2. Perform work
3. Document in JSON
4. Status: complete or error

### Pattern 2: Interactive Execution (create-prd)

```
Input → May Need Clarification → Execute → Output
```

Conditional user interaction:
1. Read request
2. Determine if questions needed
3. If yes: status user_query, wait for response
4. If no: execute immediately
5. Document in JSON

### Pattern 3: Multi-Phase Execution (generate-tasks)

```
Input → Phase 1 → User Confirm → Phase 2 → Output
```

Explicit phases:
1. Read request
2. Execute Phase 1 (parent tasks)
3. Status: user_query, wait for "Go"
4. Execute Phase 2 (sub-tasks)
5. Status: complete

## Error Handling Strategy

### Error Classification

**1. Fatal Errors** (status: "error")
- Cannot proceed at all
- No work completed
- Example: File not found, invalid syntax

**2. Partial Failures** (status: "incomplete")
- Some work succeeded
- Some work failed
- Example: Processed 3 of 5 files

**3. Need Input** (status: "user_query")
- Not an error - need information
- Work can resume after response
- Example: Ambiguous request

### Error Documentation

```json
{
  "status": "incomplete",
  "errors": [
    {
      "message": "Permission denied",
      "type": "PermissionError",
      "fatal": false,
      "context": "Could not write to /protected/dir"
    }
  ],
  "comments": [
    "Completed 80% of work before error",
    "Try running with elevated permissions",
    "Alternative: use different output directory"
  ]
}
```

## Extension Points

### Adding New Commands

1. **Create Command File**: `commands/new-command.md`
   - Define purpose
   - Specify input format
   - Document process
   - List output requirements

2. **Update Schema**: Add to `command_type` enum
   ```json
   "command_type": {
     "enum": [...existing..., "new-command"]
   }
   ```

3. **Create Examples**: Add to `HEADLESS-EXAMPLES.md`

4. **Test**: Run with sample request

**No need to**:
- Modify system prompt
- Change output schema (use existing fields)
- Update other commands

### Adding New Output Fields

Only add new fields if existing ones don't cover the use case:

```json
{
  "artifacts": {
    "prd_filename": "...",           // existing
    "documentation_filename": "...",  // existing
    "your_new_field": "..."          // new
  }
}
```

Document new fields in schema and examples.

## Implementation Guidelines

### For Command Developers

**DO**:
- Follow the command file template
- Reference system prompt principles
- Use standard output fields
- Document expected request format
- Include quality checklist

**DON'T**:
- Duplicate system prompt content
- Create custom output formats
- Assume user sees terminal
- Skip error handling

### For System Users

**DO**:
- Read command documentation first
- Provide complete request context
- Check output status before assuming success
- Save output JSON for records
- Handle user_query status properly

**DON'T**:
- Assume silent execution means success
- Ignore the comments array
- Skip validation of artifacts
- Lose context when resuming

## Deployment Patterns

### Local Development
```bash
# Single execution
./run-claude-command.sh create-prd

# Review output
cat claude-output.json | jq
```

### CI/CD Pipeline
```yaml
- name: Generate PRD
  run: |
    claude code headless \
      --system-prompt ./SYSTEM-PROMPT.md \
      --command ./commands/create-prd.md \
      --request ./request.json \
      --output ./output.json
    
- name: Check Status
  run: |
    STATUS=$(jq -r '.status' output.json)
    if [ "$STATUS" != "complete" ]; then
      exit 1
    fi
```

### Batch Processing
```bash
# Process multiple requests
for request in requests/*.json; do
    echo "Processing $request"
    ./run-claude-command.sh create-prd $request
done
```

### Web Service
```python
@app.post("/execute")
def execute_command(request: CommandRequest):
    # Write request to file
    with open("request.json", "w") as f:
        json.dump(request.dict(), f)
    
    # Execute command
    result = subprocess.run([
        "claude", "code", "headless",
        "--system-prompt", "SYSTEM-PROMPT.md",
        "--command", f"commands/{request.command_type}.md",
        "--request", "request.json",
        "--output", "output.json"
    ])
    
    # Return output
    with open("output.json") as f:
        return json.load(f)
```

## Monitoring and Observability

### Key Metrics to Track

1. **Execution Metrics**
   - Success rate by command type
   - Average execution time
   - User query rate
   - Error rate and types

2. **Output Metrics**
   - Files created per execution
   - Task completion rates
   - Comments per execution (complexity indicator)
   - Context size (for resumption)

3. **Quality Metrics**
   - Artifact validation pass rate
   - User satisfaction with outputs
   - Resumption success rate

### Sample Monitoring

```python
# Parse output for metrics
with open("claude-output.json") as f:
    output = json.load(f)

metrics = {
    "command_type": output["command_type"],
    "status": output["status"],
    "files_created": len(output["files"]["created"]),
    "tasks_total": len(output.get("tasks", [])),
    "tasks_completed": sum(
        1 for t in output.get("tasks", [])
        if t["status"] == "completed"
    ),
    "had_errors": len(output.get("errors", [])) > 0,
    "needed_user_input": output["status"] == "user_query"
}

# Send to monitoring system
log_metrics(metrics)
```

## Best Practices Summary

### System Design
- âœ… Single source of truth for instructions
- âœ… Consistent output format across all commands
- âœ… Complete documentation in JSON (user can't see terminal)
- âœ… Stateful resumption support
- âœ… Clear error handling

### Command Implementation
- âœ… Follow command file template
- âœ… Use standard output fields
- âœ… Track all file operations
- âœ… Provide quality checklist
- âœ… Document expected inputs

### Execution
- âœ… Validate request before execution
- âœ… Check output status before proceeding
- âœ… Save context for resumption
- âœ… Log execution for debugging
- âœ… Handle all status types

### Extension
- âœ… New commands use existing patterns
- âœ… Reuse output fields when possible
- âœ… Document new features completely
- âœ… Test thoroughly before deployment
- âœ… Update examples

## Troubleshooting Guide

### Issue: Status is "user_query" but no questions visible
**Solution**: Check `queries_for_user` array in output JSON

### Issue: Artifacts not created
**Solution**: Check `errors` array for file system issues

### Issue: Resumption fails
**Solution**: Verify `previous_context` is passed correctly in new request

### Issue: Tasks not tracked
**Solution**: Ensure command file includes task generation in process

### Issue: Output JSON invalid
**Solution**: Validate against unified schema, check for syntax errors

## Future Enhancements

### Potential Additions

1. **Streaming Output**: Real-time progress updates
2. **Partial Artifacts**: Save intermediate work
3. **Parallel Execution**: Multiple commands simultaneously
4. **Smart Resumption**: Auto-detect where to resume
5. **Output Validation**: Automatic artifact verification
6. **Dependency Management**: Track inter-command dependencies

### Backward Compatibility

When enhancing:
- Keep existing output fields
- Add new fields as optional
- Maintain existing command files
- Document breaking changes
- Provide migration guides

## Conclusion

This architecture provides:
- **Consistency**: Single system, unified output
- **Transparency**: Complete documentation of actions
- **Flexibility**: Easy to add new commands
- **Reliability**: Structured error handling
- **Maintainability**: Clear separation of concerns
- **Scalability**: Supports automation and integration

The key insight: By separating universal principles (system prompt), command logic (command files), and specific requests (request files), we create a clean, extensible system that's easy to understand and maintain.
