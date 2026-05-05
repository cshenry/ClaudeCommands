"""Shared frontmatter helpers for skill .md files.

Originally inlined in inventory.py; extracted here so register/retire/rename
operations can parse skill frontmatter without duplicating the parser.
"""

from pathlib import Path

import yaml


def parse_frontmatter(filepath: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a skill .md file.

    Returns (frontmatter_dict, markdown_body).
    If no frontmatter found, returns ({}, full_content).
    Returns ({}, "") on read errors.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, ""

    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, content

    # Find closing ---
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, content

    yaml_block = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:])

    try:
        fm = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        fm = {}

    return fm, body


def extract_first_heading(body: str) -> str | None:
    """Extract the first markdown heading from body text."""
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return None
