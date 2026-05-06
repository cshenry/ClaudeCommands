"""Skill registry — load/save the skill registry state file.

Per-skill schema (state/skill_registry.json -> skills[<key>]):

    name                 str    Human-readable name (frontmatter ``name``).
    description          str    One-line description (frontmatter ``description``).
    home_repo            str    Repo this skill is owned by.
    home_path            str    Absolute path of the anchor .md file.

                                Canonical layout (post-pivot, Step 1 of the
                                skill convention pivot):
                                  <repo>/agent-io/skills/<skill>.md
                                with an optional sibling context dir at
                                  <repo>/agent-io/skills/<skill>/

                                Legacy locations (still discovered by the
                                inventory walker, with a deprecation warning,
                                until ``migrate-domain-skills --apply``
                                relocates them):
                                  <repo>/.claude/commands/<skill>.md
                                  <repo>/commands/<skill>.md   (universals only)

    scope                str    universal | platform | domain.
    domain               str?   Project id (only for domain-scoped skills).
    manifest_hash        str    sha256 over the skill unit (anchor + sibling dir).
    retired              bool   If True, skipped by all sync loops.
    conflict             bool   If True, the same skill name appears in
                                multiple homes with different content.
    conflict_alternates  list   Optional. Other homes when conflict=True.
    deploys_to_machines  list   Cumulative list of machines this skill has
                                been deployed to (kept sorted).
    deploys_to_repos     list   Frontmatter-driven list of target repos for
                                ``sync-repos``. ``["*"]`` is a wildcard that
                                expands to every project with a repo_path.
                                Escape-hatch for narrow cross-repo sharing —
                                most universals do NOT use this.
    last_deploy          dict   { <machine_name>: { hash, ts, action } }
                                Per-machine deploy history (sync command).
    last_repo_deploy     dict   { <repo_name>: { hash, ts, action, commit? } }
                                Per-repo deploy history (sync-repos command).
                                ``commit`` is the short SHA of the auto-commit
                                that landed the skill into the target repo;
                                empty string when sync-repos ran without
                                ``--commit`` (the new default).
    last_runtime_deploy  dict   { <repo_name>: { hash, ts, action } }
                                Per-repo runtime mirror history (regular
                                ``sync`` command). Tracks which repos this
                                skill has been mirrored into via the per-repo
                                runtime pass. Always commit-less (the runtime
                                ``.claude/commands/`` dirs are gitignored
                                after Step 2 of the convention pivot).

The three ``last_*`` maps stay separate by design:
  - ``sync`` writes to the user-global ``commands_target`` and updates
    ``last_deploy`` per machine.
  - ``sync`` (same loop) also mirrors each subscribed skill into
    ``<home_repo>/.claude/commands/`` (and any ``deploys_to_repos``
    targets) and updates ``last_runtime_deploy`` per repo. No commits.
  - ``sync-repos`` is a separate, opt-in command that writes into target
    repos' ``.claude/commands/`` and only produces commits when
    ``--commit`` is passed (claude-web snapshots, etc).
"""

import json
import os
import tempfile
from pathlib import Path

_DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "state" / "skill_registry.json"
_REGISTRY_ENV = "CLAUDE_SKILLS_REGISTRY_PATH"


def _registry_path() -> Path:
    """Resolve the registry path, honoring the env override (used by tests)."""
    override = os.environ.get(_REGISTRY_ENV)
    if override:
        return Path(override)
    return _DEFAULT_REGISTRY_PATH


def load_registry(path: Path | None = None) -> dict:
    """Load the skill registry from disk."""
    path = path or _registry_path()
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
    path = path or _registry_path()
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
