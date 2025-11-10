# Example Request Files

This directory contains example request files for each command type.

## Available Examples

### create-prd-example.json
Example request for creating a Product Requirements Document (PRD).

**Use case**: Define a new feature with requirements
**Output**: PRD file in `agent-io/PRD/` directory

```bash
./scripts/run-command.sh create-prd examples/create-prd-example.json
```

### generate-tasks-example.json
Example request for generating implementation tasks from a PRD.

**Use case**: Break down a PRD into actionable development tasks
**Output**: Tasks in JSON output

```bash
./scripts/run-command.sh generate-tasks examples/generate-tasks-example.json
```

### doc-code-for-dev-example.json
Example request for documenting code architecture.

**Use case**: Create internal architecture documentation for developers
**Output**: Architecture docs in `agent-io/docs/` directory

```bash
./scripts/run-command.sh doc-code-for-dev examples/doc-code-for-dev-example.json
```

### doc-code-usage-example.json
Example request for documenting public API usage.

**Use case**: Create usage documentation for API consumers
**Output**: Usage docs in `agent-io/docs/` directory

```bash
./scripts/run-command.sh doc-code-usage examples/doc-code-usage-example.json
```

### free-agent-example.json
Example request for executing simple tasks.

**Use case**: Quick tasks like refactoring, file operations, data processing
**Output**: Varies based on task

```bash
./scripts/run-command.sh free-agent examples/free-agent-example.json
```

### user-query-response-example.json
Example of responding to user queries during execution.

**Use case**: Resume a session that paused for user input
**Context**: Use when a command returns status "user_query"

```bash
# First run returns user_query status
./scripts/run-command.sh create-prd examples/create-prd-example.json

# Check what questions need answers
cat claude-output.json | jq '.queries_for_user'

# Create response and resume
./scripts/run-command.sh create-prd examples/user-query-response-example.json
```

## Customizing Examples

1. Copy an example file:
   ```bash
   cp examples/create-prd-example.json my-request.json
   ```

2. Edit the fields:
   - `description`: Brief description of what you want
   - `context`: Specific details and requirements
   - `constraints`: Optional constraints or preferences

3. Run your request:
   ```bash
   ./scripts/run-command.sh create-prd my-request.json
   ```

## Request File Structure

All request files follow this basic structure:

```json
{
  "request_type": "command-name",
  "description": "Brief description",
  "context": {
    "field1": "value1",
    "field2": "value2"
  },
  "constraints": {
    "optional": "constraints"
  }
}
```

See [docs/REQUEST-FORMAT.md](../docs/REQUEST-FORMAT.md) for detailed specifications.

## Tips

- Start with simple examples and add details incrementally
- Use the `description` field to clearly state your goal
- Add context specific to your project in the `context` field
- Check `claude-output.json` after each run for results
- Use `./scripts/validate-output.sh` to validate the output format
