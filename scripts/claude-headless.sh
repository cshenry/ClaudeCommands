#!/bin/bash
#
# Claude Code Headless Wrapper
#
# This script implements the designed headless interface by wrapping
# the actual Claude Code CLI to provide the unified execution pattern.
#
# Usage: ./scripts/claude-headless.sh --system-prompt SYSTEM-PROMPT.md \
#          --command commands/create-prd.md \
#          --request request.json \
#          --output claude-output.json \
#          --working-dir ./workspace
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --system-prompt)
            SYSTEM_PROMPT="$2"
            shift 2
            ;;
        --command)
            COMMAND_FILE="$2"
            shift 2
            ;;
        --request)
            REQUEST_FILE="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --working-dir)
            WORKING_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$SYSTEM_PROMPT" ] || [ -z "$COMMAND_FILE" ] || [ -z "$REQUEST_FILE" ]; then
    echo -e "${RED}Error: Missing required arguments${NC}"
    echo ""
    echo "Usage: $0 \\"
    echo "  --system-prompt SYSTEM-PROMPT.md \\"
    echo "  --command commands/create-prd.md \\"
    echo "  --request request.json \\"
    echo "  --output claude-output.json \\"
    echo "  --working-dir ./workspace"
    exit 1
fi

# Set defaults
OUTPUT_FILE="${OUTPUT_FILE:-claude-output.json}"
WORKING_DIR="${WORKING_DIR:-.}"

# Validate files exist
for file in "$SYSTEM_PROMPT" "$COMMAND_FILE" "$REQUEST_FILE"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}Error: File not found: $file${NC}"
        exit 1
    fi
done

# Create working directory
mkdir -p "$WORKING_DIR"

# Build the combined prompt
echo -e "${BLUE}Building execution context...${NC}"

# Read the files
SYSTEM_PROMPT_CONTENT=$(cat "$SYSTEM_PROMPT")
COMMAND_CONTENT=$(cat "$COMMAND_FILE")
REQUEST_CONTENT=$(cat "$REQUEST_FILE")

# Create combined prompt
COMBINED_PROMPT=$(cat <<EOF
# EXECUTION CONTEXT

You are being run in headless mode to execute a specific command with structured output.

## System Instructions

$SYSTEM_PROMPT_CONTENT

## Command to Execute

$COMMAND_CONTENT

## User Request

\`\`\`json
$REQUEST_CONTENT
\`\`\`

## IMPORTANT

1. Follow the system prompt instructions exactly
2. Execute the command as specified
3. Produce output in the exact JSON format specified in the system prompt
4. Save the JSON output to a file (you'll be told where)
5. Perform all file operations relative to the working directory

Working directory: $WORKING_DIR
Output file: $OUTPUT_FILE

BEGIN EXECUTION NOW.
EOF
)

# Run Claude Code in print mode with JSON output
echo -e "${BLUE}Executing Claude Code...${NC}"
echo ""

cd "$WORKING_DIR"

# Run claude with the combined prompt
echo "$COMBINED_PROMPT" | claude --print \
    --output-format json \
    --dangerously-skip-permissions 2>&1 | tee /tmp/claude-raw-output.json

# Extract the response
if [ -f "/tmp/claude-raw-output.json" ]; then
    # The output format from --output-format json wraps the response
    # We need to extract the actual response content

    # Try to extract JSON from the response
    # This is a placeholder - actual extraction depends on Claude's JSON format
    jq -r '.response // .content // .' /tmp/claude-raw-output.json > "$OUTPUT_FILE" 2>/dev/null || {
        echo -e "${YELLOW}Warning: Could not parse JSON output, saving raw output${NC}"
        cat /tmp/claude-raw-output.json > "$OUTPUT_FILE"
    }

    rm /tmp/claude-raw-output.json
fi

echo ""
echo -e "${GREEN}Execution complete${NC}"
echo -e "${YELLOW}Output:${NC} $OUTPUT_FILE"

# Validate output if possible
if [ -f "$OUTPUT_FILE" ] && command -v jq &> /dev/null; then
    if jq empty "$OUTPUT_FILE" 2>/dev/null; then
        STATUS=$(jq -r '.status // "unknown"' "$OUTPUT_FILE")
        echo -e "${YELLOW}Status:${NC} $STATUS"
    fi
fi
