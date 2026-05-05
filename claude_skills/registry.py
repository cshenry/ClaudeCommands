"""Skill registry — load/save the skill registry state file."""

import json
from pathlib import Path

_DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "state" / "skill_registry.json"


def load_registry(path: Path | None = None) -> dict:
    """Load the skill registry from disk."""
    path = path or _DEFAULT_REGISTRY
    if not path.exists():
        return {"version": 1, "skills": {}}
    with open(path) as f:
        return json.load(f)


def save_registry(data: dict, path: Path | None = None) -> None:
    """Save the skill registry to disk."""
    path = path or _DEFAULT_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
