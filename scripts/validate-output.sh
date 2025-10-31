#!/bin/bash
#
# Validate Claude Code output against schema
#
# Usage: ./scripts/validate-output.sh [output-file]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

OUTPUT_FILE="${1:-./claude-output.json}"
SCHEMA_FILE="$PROJECT_ROOT/unified-output-schema.json"

# Check if output file exists
if [ ! -f "$OUTPUT_FILE" ]; then
    echo -e "${RED}Error: Output file not found: $OUTPUT_FILE${NC}"
    exit 1
fi

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo -e "${RED}Error: Schema file not found: $SCHEMA_FILE${NC}"
    exit 1
fi

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Output Validation${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Output:${NC} $OUTPUT_FILE"
echo -e "${YELLOW}Schema:${NC} $SCHEMA_FILE"
echo ""

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: 'jq' is required for validation${NC}"
    echo "Install with: sudo apt-get install jq"
    exit 1
fi

# Validate JSON syntax
echo -e "${YELLOW}Checking JSON syntax...${NC}"
if jq empty "$OUTPUT_FILE" 2>/dev/null; then
    echo -e "${GREEN}✓ Valid JSON${NC}"
else
    echo -e "${RED}✗ Invalid JSON syntax${NC}"
    exit 1
fi

# Check required fields
echo ""
echo -e "${YELLOW}Checking required fields...${NC}"

REQUIRED_FIELDS=(
    "command_type"
    "status"
    "session_summary"
    "tasks"
    "files"
    "artifacts"
)

ALL_VALID=true
for field in "${REQUIRED_FIELDS[@]}"; do
    if jq -e ".$field" "$OUTPUT_FILE" >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $field"
    else
        echo -e "${RED}✗${NC} $field (missing)"
        ALL_VALID=false
    fi
done

# Validate status value
echo ""
echo -e "${YELLOW}Checking status value...${NC}"
STATUS=$(jq -r '.status' "$OUTPUT_FILE")
VALID_STATUSES=("complete" "incomplete" "user_query" "error")

if [[ " ${VALID_STATUSES[@]} " =~ " ${STATUS} " ]]; then
    echo -e "${GREEN}✓${NC} Status: $STATUS"
else
    echo -e "${RED}✗${NC} Invalid status: $STATUS"
    echo "   Valid values: ${VALID_STATUSES[*]}"
    ALL_VALID=false
fi

# Check files structure
echo ""
echo -e "${YELLOW}Checking files structure...${NC}"
FILES_CREATED=$(jq -r '.files.created // [] | length' "$OUTPUT_FILE")
FILES_MODIFIED=$(jq -r '.files.modified // [] | length' "$OUTPUT_FILE")
FILES_DELETED=$(jq -r '.files.deleted // [] | length' "$OUTPUT_FILE")

echo -e "${GREEN}✓${NC} Files created: $FILES_CREATED"
echo -e "${GREEN}✓${NC} Files modified: $FILES_MODIFIED"
echo -e "${GREEN}✓${NC} Files deleted: $FILES_DELETED"

# Check tasks structure
echo ""
echo -e "${YELLOW}Checking tasks structure...${NC}"
TASKS_COUNT=$(jq -r '.tasks // [] | length' "$OUTPUT_FILE")
echo -e "${GREEN}✓${NC} Tasks: $TASKS_COUNT"

if [ "$TASKS_COUNT" -gt 0 ]; then
    # Validate each task has required fields
    TASK_FIELDS=("task_id" "description" "status")
    INVALID_TASKS=0

    for i in $(seq 0 $((TASKS_COUNT - 1))); do
        for field in "${TASK_FIELDS[@]}"; do
            if ! jq -e ".tasks[$i].$field" "$OUTPUT_FILE" >/dev/null 2>&1; then
                echo -e "${RED}✗${NC} Task $i missing field: $field"
                INVALID_TASKS=$((INVALID_TASKS + 1))
                ALL_VALID=false
            fi
        done
    done

    if [ "$INVALID_TASKS" -eq 0 ]; then
        echo -e "${GREEN}✓${NC} All tasks have required fields"
    fi
fi

# Use ajv if available for full schema validation
if command -v ajv &> /dev/null; then
    echo ""
    echo -e "${YELLOW}Running full schema validation...${NC}"
    if ajv validate -s "$SCHEMA_FILE" -d "$OUTPUT_FILE" 2>&1; then
        echo -e "${GREEN}✓ Schema validation passed${NC}"
    else
        echo -e "${RED}✗ Schema validation failed${NC}"
        ALL_VALID=false
    fi
else
    echo ""
    echo -e "${BLUE}Note: Install 'ajv-cli' for full schema validation${NC}"
    echo "  npm install -g ajv-cli"
fi

# Final result
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"

if [ "$ALL_VALID" = true ]; then
    echo -e "${GREEN}✓ Validation PASSED${NC}"
    exit 0
else
    echo -e "${RED}✗ Validation FAILED${NC}"
    exit 1
fi
