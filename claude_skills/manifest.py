"""Skill manifest operations — hashing and unit discovery."""

import hashlib
from pathlib import Path

# Standard ignore patterns for manifest computation
_IGNORE_PATTERNS = {".DS_Store", "__pycache__", ".git"}
_IGNORE_SUFFIXES = {".pyc"}
_SKIP_MD_PREFIXES = ("_",)
_SKIP_MD_NAMES = {"README.md"}


def _should_ignore(path: Path) -> bool:
    """Return True if path should be excluded from manifest computation."""
    name = path.name
    if name in _IGNORE_PATTERNS:
        return True
    if name.startswith("."):
        return True
    if path.suffix in _IGNORE_SUFFIXES:
        return True
    # Check if any parent component is in ignore set
    for part in path.parts:
        if part in _IGNORE_PATTERNS or part.startswith("."):
            return True
    return False


def _sha256_file(filepath: Path) -> str:
    """Return sha256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_manifest_hash(skill_path: Path) -> str:
    """Compute deterministic manifest hash for a skill.

    Treats a skill as the union of:
      - skill_path (the .md file itself), and
      - skill_path's sibling directory of the same stem (e.g. for
        envman-expert.md, the directory envman-expert/) if it exists,
        recursively.

    Algorithm:
      1. Build a sorted list of (relative_path_from_skill_parent, sha256_hex)
         pairs for every file in the unit.
      2. Concatenate "{rel_path}:{sha256_hex}\n" lines.
      3. Return sha256 of that concatenation.

    Returns 64-char hex string. Stable across machines for the same file
    contents.
    """
    parent = skill_path.parent
    stem = skill_path.stem
    sibling_dir = parent / stem

    # Collect all files in the skill unit
    file_hashes: list[tuple[str, str]] = []

    # The .md file itself
    if skill_path.exists():
        rel = skill_path.name
        file_hashes.append((rel, _sha256_file(skill_path)))

    # The sibling directory (recursively)
    if sibling_dir.is_dir():
        for filepath in sorted(sibling_dir.rglob("*")):
            if not filepath.is_file():
                continue
            rel_from_parent = filepath.relative_to(parent)
            if _should_ignore(rel_from_parent):
                continue
            file_hashes.append((str(rel_from_parent), _sha256_file(filepath)))

    # Sort by relative path for determinism
    file_hashes.sort(key=lambda x: x[0])

    # Build manifest string and hash it
    manifest_str = "".join(f"{rel}:{h}\n" for rel, h in file_hashes)
    return hashlib.sha256(manifest_str.encode("utf-8")).hexdigest()


def list_skill_units(commands_dir: Path) -> list[Path]:
    """List skill unit anchor paths in a commands directory.

    Given a directory like ~/.claude/commands/ or <repo>/.claude/commands/
    or ClaudeCommands/commands/, return a list of skill unit "anchor paths"
    (one per skill). Each anchor is the .md file path. The sibling directory
    (if any) is part of the unit but NOT a separate entry.

    Skips:
      - Hidden files (starting with .)
      - _*.md (private)
      - README.md
      - Non-.md files at the top level
    """
    if not commands_dir.is_dir():
        return []

    anchors = []
    for item in sorted(commands_dir.iterdir()):
        if not item.is_file():
            continue
        if item.suffix != ".md":
            continue
        name = item.name
        # Skip hidden files
        if name.startswith("."):
            continue
        # Skip private files
        if name.startswith("_"):
            continue
        # Skip README
        if name in _SKIP_MD_NAMES:
            continue
        anchors.append(item)

    return anchors
