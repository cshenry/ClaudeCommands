#!/bin/bash
#
# Claude Commands Installation Script
#
# This script installs the ClaudeCommands system files to the user's home directory.
# It copies:
#   - SYSTEM-PROMPT.md to ~/.claude/CLAUDE.md
#   - commands/ directory to ~/.claude/commands/
#
# Usage: ./scripts/install.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Define target directories
CLAUDE_DIR="$HOME/.claude"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
COMMANDS_DIR="$CLAUDE_DIR/commands"

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Claude Commands Installation${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Check if source files exist
if [ ! -f "$PROJECT_ROOT/SYSTEM-PROMPT.md" ]; then
    echo -e "${RED}Error: SYSTEM-PROMPT.md not found in $PROJECT_ROOT${NC}"
    exit 1
fi

if [ ! -d "$PROJECT_ROOT/commands" ]; then
    echo -e "${RED}Error: commands/ directory not found in $PROJECT_ROOT${NC}"
    exit 1
fi

# Create ~/.claude directory if it doesn't exist
echo -e "${YELLOW}Creating directory:${NC} $CLAUDE_DIR"
mkdir -p "$CLAUDE_DIR"

# Check if CLAUDE.md already exists
if [ -f "$CLAUDE_MD" ]; then
    echo -e "${YELLOW}Warning: $CLAUDE_MD already exists${NC}"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Skipping CLAUDE.md installation${NC}"
        SKIP_CLAUDE_MD=true
    fi
fi

# Copy SYSTEM-PROMPT.md to ~/.claude/CLAUDE.md
if [ "$SKIP_CLAUDE_MD" != true ]; then
    echo -e "${GREEN}Installing:${NC} SYSTEM-PROMPT.md → $CLAUDE_MD"
    cp "$PROJECT_ROOT/SYSTEM-PROMPT.md" "$CLAUDE_MD"
fi

# Create ~/.claude/commands directory
echo -e "${YELLOW}Creating directory:${NC} $COMMANDS_DIR"
mkdir -p "$COMMANDS_DIR"

# Count existing command files
EXISTING_COUNT=$(find "$COMMANDS_DIR" -name "*.md" 2>/dev/null | wc -l)
if [ "$EXISTING_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}Warning: $COMMANDS_DIR already contains $EXISTING_COUNT command file(s)${NC}"
    read -p "Do you want to overwrite existing commands? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Skipping command files installation${NC}"
        SKIP_COMMANDS=true
    fi
fi

# Copy command files to ~/.claude/commands/
if [ "$SKIP_COMMANDS" != true ]; then
    echo -e "${GREEN}Installing command files to:${NC} $COMMANDS_DIR"

    COPIED_COUNT=0
    for cmd_file in "$PROJECT_ROOT/commands"/*.md; do
        if [ -f "$cmd_file" ]; then
            cmd_name=$(basename "$cmd_file")
            echo -e "  ${BLUE}→${NC} $cmd_name"
            cp "$cmd_file" "$COMMANDS_DIR/$cmd_name"
            COPIED_COUNT=$((COPIED_COUNT + 1))
        fi
    done

    echo -e "${GREEN}Installed $COPIED_COUNT command file(s)${NC}"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Installation Complete${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Installed files:${NC}"
echo -e "  System prompt: ${BLUE}$CLAUDE_MD${NC}"
echo -e "  Commands:      ${BLUE}$COMMANDS_DIR${NC}"
echo ""
echo -e "${YELLOW}Available commands:${NC}"
shopt -s nullglob
for cmd in "$COMMANDS_DIR"/*.md; do
    if [ -f "$cmd" ]; then
        basename "$cmd" .md | sed 's/^/  - /'
    fi
done
shopt -u nullglob
echo ""
echo -e "${YELLOW}Usage:${NC}"
echo -e "  claude code headless \\"
echo -e "    --system-prompt $CLAUDE_MD \\"
echo -e "    --command $COMMANDS_DIR/<command>.md \\"
echo -e "    --request <request>.json \\"
echo -e "    --output <output>.json"
echo ""
