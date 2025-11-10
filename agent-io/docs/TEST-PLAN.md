# Test Plan

## Overview

This document outlines how to test the Claude Code Headless Execution System.

## Pre-Test Validation

### 1. Validate File Structure

```bash
# Check all files exist
ls -la SYSTEM-PROMPT.md
ls -la unified-output-schema.json
ls -la commands/
ls -la docs/
ls -la examples/
ls -la scripts/

# Verify file permissions
ls -la scripts/*.sh
```

**Expected**: All files present, scripts executable

### 2. Validate JSON Files

```bash
# Validate output schema
jq empty unified-output-schema.json
echo "Schema: $?"

# Validate example requests
for f in examples/*.json; do
    echo "Checking $f"
    jq empty "$f"
done
```

**Expected**: All JSON files valid (exit code 0)

### 3. Validate Documentation Links

```bash
# Check that referenced files exist
grep -o '\[.*\](.*\.md)' README.md | \
  sed 's/.*(\(.*\))/\1/' | \
  while read file; do
    [ -f "$file" ] && echo "✓ $file" || echo "✗ $file MISSING"
  done
```

**Expected**: All referenced files exist

## Unit Tests

### Test 1: System Prompt Completeness

**Objective**: Verify system prompt contains all required sections

```bash
grep -q "## Output Format" SYSTEM-PROMPT.md && echo "✓ Has Output Format" || echo "✗ Missing Output Format"
grep -q "## Task Management" SYSTEM-PROMPT.md && echo "✓ Has Task Management" || echo "✗ Missing Task Management"
grep -q "## File Tracking" SYSTEM-PROMPT.md && echo "✓ Has File Tracking" || echo "✗ Missing File Tracking"
```

**Expected**: All sections present

### Test 2: Command File Structure

**Objective**: Verify all commands have required sections

```bash
for cmd in commands/*.md; do
    echo "Testing $cmd"
    grep -q "## Purpose" "$cmd" && echo "  ✓ Has Purpose" || echo "  ✗ Missing Purpose"
    grep -q "## Process" "$cmd" && echo "  ✓ Has Process" || echo "  ✗ Missing Process"
done
```

**Expected**: All commands have required sections

### Test 3: Example Request Validity

**Objective**: Verify example requests match expected schema

```bash
for example in examples/*-example.json; do
    echo "Testing $example"

    # Check has request_type
    jq -e '.request_type' "$example" >/dev/null && \
        echo "  ✓ Has request_type" || echo "  ✗ Missing request_type"

    # Check has description
    jq -e '.description' "$example" >/dev/null && \
        echo "  ✓ Has description" || echo "  ✗ Missing description"

    # Check has context
    jq -e '.context' "$example" >/dev/null && \
        echo "  ✓ Has context" || echo "  ✗ Missing context"
done
```

**Expected**: All examples have required fields

## Integration Tests

### Test 4: Manual Execution Test

**Objective**: Test the system works with manual prompt combination

**Steps**:

1. Create a test workspace:
   ```bash
   mkdir -p test-workspace
   cd test-workspace
   ```

2. Combine the prompts:
   ```bash
   cat ../SYSTEM-PROMPT.md > combined-prompt.txt
   echo -e "\n---\n" >> combined-prompt.txt
   cat ../commands/create-prd.md >> combined-prompt.txt
   echo -e "\n---\n## User Request\n" >> combined-prompt.txt
   cat ../examples/create-prd-example.json >> combined-prompt.txt
   ```

3. Review the combined prompt:
   ```bash
   cat combined-prompt.txt
   ```

4. Start Claude Code interactively:
   ```bash
   claude --system-prompt ../SYSTEM-PROMPT.md
   ```

5. Paste the command and request content

6. Verify output follows the expected format

**Expected**: Output should be JSON matching unified-output-schema.json

### Test 5: Wrapper Script Test

**Objective**: Test the wrapper script execution

**Steps**:

1. Create test workspace:
   ```bash
   mkdir -p test-workspace
   ```

2. Run wrapper script:
   ```bash
   ./scripts/claude-headless.sh \
     --system-prompt ./SYSTEM-PROMPT.md \
     --command ./commands/create-prd.md \
     --request ./examples/create-prd-example.json \
     --output ./test-workspace/output.json \
     --working-dir ./test-workspace
   ```

3. Validate output:
   ```bash
   ./scripts/validate-output.sh ./test-workspace/output.json
   ```

**Expected**:
- Script executes without errors
- Output file created
- Output validates against schema

### Test 6: Run Script Test

**Objective**: Test the run-command.sh automation script

**Steps**:

1. Test with create-prd:
   ```bash
   ./scripts/run-command.sh create-prd examples/create-prd-example.json test-workspace
   ```

2. Check output exists:
   ```bash
   ls -la claude-output.json
   ```

3. Validate output:
   ```bash
   ./scripts/validate-output.sh claude-output.json
   ```

**Expected**:
- Command executes
- Output file created
- Summary displayed

## End-to-End Tests

### Test 7: Complete Workflow Test

**Objective**: Test complete PRD → Tasks workflow

**Steps**:

1. Create PRD:
   ```bash
   ./scripts/run-command.sh create-prd examples/create-prd-example.json
   ```

2. Extract PRD filename:
   ```bash
   PRD_FILE=$(jq -r '.artifacts.prd_filename' claude-output.json)
   echo "PRD: $PRD_FILE"
   ```

3. Verify PRD file exists:
   ```bash
   [ -f "workspace/$PRD_FILE" ] && echo "✓ PRD created" || echo "✗ PRD not found"
   ```

4. Create tasks request:
   ```bash
   cat > tasks-request.json <<EOF
   {
     "request_type": "generate-tasks",
     "description": "Generate tasks for PRD",
     "context": {
       "prd_file": "$PRD_FILE"
     }
   }
   EOF
   ```

5. Generate tasks:
   ```bash
   ./scripts/run-command.sh generate-tasks tasks-request.json
   ```

6. Verify tasks in output:
   ```bash
   jq '.tasks | length' claude-output.json
   ```

**Expected**:
- PRD created successfully
- Tasks generated from PRD
- All tasks have required fields

### Test 8: Error Handling Test

**Objective**: Verify system handles errors gracefully

**Steps**:

1. Test with missing file:
   ```bash
   ./scripts/run-command.sh create-prd nonexistent.json 2>&1 | grep -q "not found" && \
     echo "✓ Handles missing file" || echo "✗ Poor error handling"
   ```

2. Test with invalid JSON:
   ```bash
   echo "invalid json" > bad-request.json
   ./scripts/run-command.sh create-prd bad-request.json 2>&1 | grep -q -i "error\|invalid" && \
     echo "✓ Handles invalid JSON" || echo "✗ Poor error handling"
   rm bad-request.json
   ```

3. Test with unknown command:
   ```bash
   ./scripts/run-command.sh unknown-command examples/create-prd-example.json 2>&1 | \
     grep -q -i "not found" && echo "✓ Handles unknown command" || echo "✗ Poor error handling"
   ```

**Expected**: Clear error messages for all error cases

## Validation Tests

### Test 9: Output Schema Compliance

**Objective**: Verify all example outputs match schema

**Prerequisites**: Install ajv-cli: `npm install -g ajv-cli`

**Steps**:

1. Create sample output (if you have any):
   ```bash
   # If you have test outputs
   for output in test-outputs/*.json; do
       echo "Validating $output"
       ajv validate -s unified-output-schema.json -d "$output"
   done
   ```

**Expected**: All outputs validate successfully

### Test 10: Documentation Consistency

**Objective**: Verify documentation is consistent across files

**Steps**:

1. Check command list consistency:
   ```bash
   # Commands in README
   README_CMDS=$(grep -o '`[a-z-]*`' README.md | grep -E 'create-prd|generate-tasks|doc-code|free-agent' | sort -u)

   # Actual command files
   ACTUAL_CMDS=$(ls commands/*.md | xargs -n1 basename | sed 's/.md$//' | sort)

   echo "README commands: $README_CMDS"
   echo "Actual commands: $ACTUAL_CMDS"
   ```

2. Check status values consistency:
   ```bash
   # Status values in schema
   jq -r '.properties.status.enum[]' unified-output-schema.json | sort

   # Status values mentioned in docs
   grep -oh 'complete\|incomplete\|user_query\|error' docs/*.md | sort -u
   ```

**Expected**: Documentation matches implementation

## Test Results Template

```markdown
## Test Results - [Date]

### Environment
- OS: [OS version]
- Claude CLI: [version]
- jq: [version]

### Results

| Test | Status | Notes |
|------|--------|-------|
| File Structure | ✓/✗ | |
| JSON Validation | ✓/✗ | |
| Documentation Links | ✓/✗ | |
| System Prompt | ✓/✗ | |
| Command Files | ✓/✗ | |
| Example Requests | ✓/✗ | |
| Manual Execution | ✓/✗ | |
| Wrapper Script | ✓/✗ | |
| Run Script | ✓/✗ | |
| Complete Workflow | ✓/✗ | |
| Error Handling | ✓/✗ | |
| Schema Compliance | ✓/✗ | |
| Documentation | ✓/✗ | |

### Issues Found
[List any issues]

### Recommendations
[Any recommendations]
```

## Running All Tests

```bash
# Create test script
cat > run-all-tests.sh <<'EOF'
#!/bin/bash
echo "Running all validation tests..."
echo ""

# Test 1-3: Pre-test validation
echo "=== Pre-Test Validation ==="
./scripts/validate-output.sh unified-output-schema.json 2>/dev/null && echo "✓ Test 1-3 passed" || echo "✗ Validation failed"

# Test 4-6: Command structure
echo ""
echo "=== Command Structure ==="
for cmd in commands/*.md; do
    grep -q "## Purpose" "$cmd" && grep -q "## Process" "$cmd" && echo "✓ $(basename $cmd)" || echo "✗ $(basename $cmd)"
done

# Test 7-9: Example requests
echo ""
echo "=== Example Requests ==="
for ex in examples/*-example.json; do
    jq -e '.request_type and .description and .context' "$ex" >/dev/null 2>&1 && \
        echo "✓ $(basename $ex)" || echo "✗ $(basename $ex)"
done

echo ""
echo "=== Tests Complete ==="
EOF

chmod +x run-all-tests.sh
./run-all-tests.sh
```

**Expected**: All tests pass

## Manual Review Checklist

- [ ] README.md is clear and helpful
- [ ] All commands are documented
- [ ] All examples are realistic
- [ ] Scripts have helpful error messages
- [ ] Documentation is consistent
- [ ] No broken links in docs
- [ ] All JSON files are valid
- [ ] Schema matches documented format
- [ ] Examples cover all command types
- [ ] Error cases are handled

## Next Steps After Testing

1. Document test results
2. Fix any issues found
3. Update documentation based on findings
4. Create additional examples if needed
5. Refine scripts based on usage
6. Consider implementation options from IMPLEMENTATION-NOTES.md
