#!/bin/bash
# claude-commands.sh - Wrapper script for claude_commands.py
#
# This script determines its own location and calls the Python CLI
# from the same directory, making it portable across systems.

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Path to the Python CLI
PYTHON_CLI="${SCRIPT_DIR}/claude_commands.py"

# Check if the Python CLI exists
if [[ ! -f "$PYTHON_CLI" ]]; then
    echo "Error: claude_commands.py not found at ${PYTHON_CLI}"
    exit 1
fi

# Check if Python3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH"
    exit 1
fi

# Execute the Python CLI with all passed arguments
exec python3 "$PYTHON_CLI" "$@"
