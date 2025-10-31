#!/bin/bash
#
# Claude Code Headless Command Runner
#
# Usage: ./scripts/run-command.sh <command-name> <request-file> [working-dir]
#
# Example:
#   ./scripts/run-command.sh create-prd examples/create-prd-example.json ./workspace
#

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse arguments
COMMAND_NAME="${1:-}"
REQUEST_FILE="${2:-}"
WORKING_DIR="${3:-./workspace}"
OUTPUT_FILE="${4:-./claude-output.json}"

# Validate arguments
if [ -z "$COMMAND_NAME" ] || [ -z "$REQUEST_FILE" ]; then
    echo -e "${RED}Error: Missing required arguments${NC}"
    echo ""
    echo "Usage: $0 <command-name> <request-file> [working-dir] [output-file]"
    echo ""
    echo "Examples:"
    echo "  $0 create-prd examples/create-prd-example.json"
    echo "  $0 generate-tasks examples/generate-tasks-example.json ./workspace"
    echo ""
    echo "Available commands:"
    for cmd in "$PROJECT_ROOT"/commands/*.md; do
        basename "$cmd" .md | sed 's/^/  - /'
    done
    exit 1
fi

# Build paths
SYSTEM_PROMPT="$PROJECT_ROOT/SYSTEM-PROMPT.md"
COMMAND_FILE="$PROJECT_ROOT/commands/${COMMAND_NAME}.md"

# Validate files exist
if [ ! -f "$SYSTEM_PROMPT" ]; then
    echo -e "${RED}Error: System prompt not found: $SYSTEM_PROMPT${NC}"
    exit 1
fi

if [ ! -f "$COMMAND_FILE" ]; then
    echo -e "${RED}Error: Command file not found: $COMMAND_FILE${NC}"
    echo "Available commands:"
    for cmd in "$PROJECT_ROOT"/commands/*.md; do
        basename "$cmd" .md | sed 's/^/  - /'
    done
    exit 1
fi

if [ ! -f "$REQUEST_FILE" ]; then
    echo -e "${RED}Error: Request file not found: $REQUEST_FILE${NC}"
    exit 1
fi

# Create working directory if it doesn't exist
mkdir -p "$WORKING_DIR"

# Print execution info
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Claude Code Headless Execution${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Command:${NC}       $COMMAND_NAME"
echo -e "${YELLOW}Request:${NC}       $REQUEST_FILE"
echo -e "${YELLOW}Working Dir:${NC}   $WORKING_DIR"
echo -e "${YELLOW}Output:${NC}        $OUTPUT_FILE"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Check if claude command exists
if ! command -v claude &> /dev/null; then
    echo -e "${RED}Error: 'claude' command not found${NC}"
    echo "Please install Claude Code CLI first"
    exit 1
fi

# Run the command
echo -e "${GREEN}Running Claude Code...${NC}"
echo ""

claude code headless \
  --system-prompt "$SYSTEM_PROMPT" \
  --command "$COMMAND_FILE" \
  --request "$REQUEST_FILE" \
  --output "$OUTPUT_FILE" \
  --working-dir "$WORKING_DIR"

CLAUDE_EXIT_CODE=$?

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"

# Check if command succeeded
if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
    echo -e "${RED}Command failed with exit code $CLAUDE_EXIT_CODE${NC}"
    exit $CLAUDE_EXIT_CODE
fi

# Check if output file was created
if [ ! -f "$OUTPUT_FILE" ]; then
    echo -e "${RED}Error: Output file not created: $OUTPUT_FILE${NC}"
    exit 1
fi

# Parse and display output summary
if command -v jq &> /dev/null; then
    STATUS=$(jq -r '.status // "unknown"' "$OUTPUT_FILE")
    SUMMARY=$(jq -r '.session_summary // "No summary available"' "$OUTPUT_FILE")

    echo -e "${YELLOW}Status:${NC} $STATUS"
    echo -e "${YELLOW}Summary:${NC} $SUMMARY"
    echo ""

    # Show files created/modified
    FILES_CREATED=$(jq -r '.files.created // [] | length' "$OUTPUT_FILE")
    FILES_MODIFIED=$(jq -r '.files.modified // [] | length' "$OUTPUT_FILE")
    FILES_DELETED=$(jq -r '.files.deleted // [] | length' "$OUTPUT_FILE")

    if [ "$FILES_CREATED" -gt 0 ] || [ "$FILES_MODIFIED" -gt 0 ] || [ "$FILES_DELETED" -gt 0 ]; then
        echo -e "${YELLOW}File Operations:${NC}"
        [ "$FILES_CREATED" -gt 0 ] && echo -e "  ${GREEN}Created:${NC}  $FILES_CREATED file(s)"
        [ "$FILES_MODIFIED" -gt 0 ] && echo -e "  ${BLUE}Modified:${NC} $FILES_MODIFIED file(s)"
        [ "$FILES_DELETED" -gt 0 ] && echo -e "  ${RED}Deleted:${NC}  $FILES_DELETED file(s)"
        echo ""
    fi

    # Check for user queries
    if [ "$STATUS" = "user_query" ]; then
        echo -e "${YELLOW}⚠ User input required!${NC}"
        echo "Queries:"
        jq -r '.queries_for_user // {} | to_entries[] | "  \(.key): \(.value)"' "$OUTPUT_FILE"
        echo ""
        echo "To respond, create a new request with:"
        echo "  \"resume_session\": true"
        echo "  \"user_responses\": { ... }"
    fi

    # Check for errors
    ERRORS=$(jq -r '.errors // [] | length' "$OUTPUT_FILE")
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}Errors encountered:${NC}"
        jq -r '.errors[] // empty' "$OUTPUT_FILE" | sed 's/^/  /'
        echo ""
    fi

    # Check for comments
    COMMENTS=$(jq -r '.comments // [] | length' "$OUTPUT_FILE")
    if [ "$COMMENTS" -gt 0 ]; then
        echo -e "${YELLOW}Comments:${NC}"
        jq -r '.comments[] // empty' "$OUTPUT_FILE" | sed 's/^/  /'
        echo ""
    fi
else
    echo -e "${YELLOW}Install 'jq' for formatted output summary${NC}"
    echo "Output saved to: $OUTPUT_FILE"
fi

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Complete${NC}"
echo ""
echo "View full output: cat $OUTPUT_FILE | jq"
