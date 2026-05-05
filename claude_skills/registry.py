"""Skill registry — load/save the skill registry state file."""

import json
import os
import tempfile
from pathlib import Path

_DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "state" / "skill_registry.json"


def load_registry(path: Path | None = None) -> dict:
    """Load the skill registry from disk."""
    path = path or _DEFAULT_REGISTRY
    if not path.exists():
        return {"version": 1, "skills": {}, "written_by_machine": None, "written_at": None}
    with open(path) as f:
        return json.load(f)


def save_registry(data: dict, path: Path | None = None) -> None:
    """Save the skill registry to disk atomically.

    Writes to a sibling .tmp file, fsyncs, then os.replace's into the final
    location. Prevents torn writes if the process crashes mid-write or two
    writers race on the Dropbox-synced file.
    """
    path = path or _DEFAULT_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=path.name + ".",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
