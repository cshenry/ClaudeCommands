"""Skill inventory operations — walk known skill homes and reconcile with registry."""

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import yaml

from claude_skills.manifest import compute_manifest_hash, list_skill_units
from claude_skills.registry import load_registry, save_registry


# Paths to key data files
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_REGISTRY = Path.home() / "Dropbox" / "Projects" / "AIAssistant" / "state" / "project_registry.yaml"
_AIASSISTANT_COMMANDS = Path.home() / "Dropbox" / "Projects" / "AIAssistant" / ".claude" / "commands"
_CLAUDECOMMANDS_DIR = _REPO_ROOT / "commands"
_USER_COMMANDS = Path.home() / ".claude" / "commands"


def _parse_frontmatter(filepath: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a skill .md file.

    Returns (frontmatter_dict, markdown_body).
    If no frontmatter found, returns ({}, full_content).
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


def _extract_first_heading(body: str) -> str | None:
    """Extract the first markdown heading from body text."""
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            # Remove leading # characters and whitespace
            return stripped.lstrip("#").strip()
    return None


def _infer_scope_from_home(home_repo: str) -> str:
    """Infer scope from the home repository identifier."""
    if home_repo == "ClaudeCommands":
        return "universal"
    if home_repo == "AIAssistant":
        return "platform"
    return "domain"


def _load_project_registry() -> dict:
    """Load AIAssistant project registry."""
    if not _PROJECT_REGISTRY.exists():
        return {}
    with open(_PROJECT_REGISTRY) as f:
        data = yaml.safe_load(f) or {}
    return data.get("projects", {})


def _get_home_repos() -> list[tuple[str, Path, str]]:
    """Get all home repos to scan.

    Returns list of (repo_name, commands_dir_path, scope).
    """
    homes = []

    # 1. ClaudeCommands/commands/ -> universal
    if _CLAUDECOMMANDS_DIR.is_dir():
        homes.append(("ClaudeCommands", _CLAUDECOMMANDS_DIR, "universal"))

    # 2. AIAssistant/.claude/commands/ -> platform
    if _AIASSISTANT_COMMANDS.is_dir():
        homes.append(("AIAssistant", _AIASSISTANT_COMMANDS, "platform"))

    # 3. Every project in registry with repo_path -> domain
    projects = _load_project_registry()
    for project_id, info in projects.items():
        repo_path = info.get("repo_path")
        if not repo_path:
            continue
        # Skip ClaudeCommands and AIAssistant (already handled above)
        name = info.get("name", "")
        if name in ("ClaudeCommands", "AIAssistant"):
            continue
        # Expand ~ in path
        rp = Path(repo_path).expanduser()
        commands_dir = rp / ".claude" / "commands"
        if commands_dir.is_dir():
            homes.append((name, commands_dir, "domain"))

    return homes


def inventory(apply: bool = False, machine: str | None = None) -> dict:
    """Walk known skill homes and reconcile with state/skill_registry.json.

    Returns a dict with keys:
        proposed_skills: dict[name, entry]
        conflicts: list[name]
        scope_drifts: list[(name, registry_scope, frontmatter_scope)]
        new_skills: list[name]
        removed_skills: list[name]
        unchanged: list[name]
        hash_changed: list[name]
    """
    current_registry = load_registry()
    existing_skills = current_registry.get("skills", {})

    # Collect all discovered skills
    # Key: skill_name -> list of entries (multiple entries = conflict)
    discovered: dict[str, list[dict]] = {}

    homes = _get_home_repos()

    # Pre-load project registry for domain lookups (avoid repeated YAML parsing)
    projects = _load_project_registry()
    # Build repo_name -> project_id mapping
    _repo_name_to_pid: dict[str, str] = {}
    for pid, pinfo in projects.items():
        pname = pinfo.get("name", "")
        if pname:
            _repo_name_to_pid[pname] = pid

    for repo_name, commands_dir, default_scope in homes:
        anchors = list_skill_units(commands_dir)
        for anchor in anchors:
            fm, body = _parse_frontmatter(anchor)

            # Determine skill name
            skill_name = fm.get("name", anchor.stem)
            # Normalize to lowercase-kebab for registry key
            skill_key = anchor.stem

            # Determine scope from frontmatter
            fm_scope_raw = fm.get("scope", "")
            if fm_scope_raw:
                # Handle legacy "repo:X" frontmatter scope format. Migration map:
                #   repo:AIAssistant     → platform
                #   repo:ClaudeCommands  → universal
                #   repo:<other>         → domain
                if fm_scope_raw.startswith("repo:"):
                    declared_repo = fm_scope_raw.split(":", 1)[1]
                    if declared_repo == "AIAssistant":
                        fm_scope = "platform"
                    elif declared_repo == "ClaudeCommands":
                        fm_scope = "universal"
                    else:
                        fm_scope = "domain"
                    # If found in a repo but declares repo:X for a DIFFERENT repo,
                    # it's a deployed copy — skip it
                    if declared_repo != repo_name:
                        continue
                else:
                    fm_scope = fm_scope_raw
                    # If a skill declares a scope higher than its home's default,
                    # it's a deployed copy — skip it.
                    # E.g. universal skill in a platform/domain repo, or
                    # platform skill in a domain repo.
                    _scope_rank = {"universal": 0, "platform": 1, "domain": 2}
                    declared_rank = _scope_rank.get(fm_scope, 2)
                    home_rank = _scope_rank.get(default_scope, 2)
                    if declared_rank < home_rank:
                        continue
            else:
                fm_scope = default_scope

            # Description
            description = fm.get("description", "") or _extract_first_heading(body) or ""

            # Compute hash
            manifest_hash = compute_manifest_hash(anchor)

            # Determine domain
            domain = None
            if fm_scope == "domain" or default_scope == "domain":
                domain = _repo_name_to_pid.get(repo_name, repo_name.lower())

            entry = {
                "name": skill_name,
                "description": description,
                "home_repo": repo_name,
                "home_path": str(anchor),
                "scope": fm_scope if fm_scope in ("universal", "platform", "domain") else default_scope,
                "domain": domain,
                "manifest_hash": manifest_hash,
                "retired": False,
                "conflict": False,
                "deploys_to_machines": [],
                "deploys_to_repos": [],
                "last_deploy": {},
            }

            if skill_key not in discovered:
                discovered[skill_key] = []
            discovered[skill_key].append(entry)

    # Resolve conflicts and build proposed_skills.
    #
    # When the same skill name appears in multiple homes:
    #   - If all entries have IDENTICAL manifest_hash, they are deployment
    #     duplicates from earlier mass-copy. Pick the most-specific home
    #     (domain > platform > universal). Not a conflict.
    #   - If hashes differ, the skills have forked — that is a real conflict.
    #     Mark all entries with conflict=True and keep the first.
    #
    # Specificity ordering reflects ownership: a skill that exists in a
    # specific repo's .claude/commands/ is most likely owned by that repo;
    # the same name in AIAssistant or ClaudeCommands is a deployed copy.
    _scope_specificity = {"domain": 0, "platform": 1, "universal": 2}

    def _name_match_score(skill_name: str, home_repo: str) -> int:
        """Heuristic: 0 if home_repo name appears as a prefix of skill name,
        1 otherwise. Used as a soft tiebreaker for conflict resolution.
        Example: kbutillib-expert ↔ KBUtilLib → 0; modelseeddb-expert ↔
        ModelSEEDDatabase → 0; claude-commands-expert ↔ ClaudeCommands → 0.
        """
        sn = skill_name.lower().replace("-", "").replace("_", "")
        hr = home_repo.lower().replace("-", "").replace("_", "")
        if hr and (hr in sn or sn.startswith(hr)):
            return 0
        return 1

    proposed_skills: dict[str, dict] = {}
    conflicts: list[str] = []
    deploy_dups: list[str] = []  # informational — same-hash duplicates collapsed

    for skill_key, entries in discovered.items():
        if len(entries) == 1:
            proposed_skills[skill_key] = entries[0]
            continue

        hashes = {e["manifest_hash"] for e in entries}
        if len(hashes) == 1:
            # Pure deployment duplication — pick by name match, then specificity.
            entries_sorted = sorted(
                entries,
                key=lambda e: (
                    _name_match_score(skill_key, e["home_repo"]),
                    _scope_specificity.get(e["scope"], 99),
                    e["home_repo"].lower(),
                ),
            )
            proposed_skills[skill_key] = entries_sorted[0]
            deploy_dups.append(skill_key)
        else:
            # Real conflict: same name, different content in different homes.
            # Stash the alternate homes on the kept entry so the user can
            # investigate without re-running discovery.
            conflicts.append(skill_key)
            # Prefer name-match first, then most-specific scope, then alpha.
            entries_sorted = sorted(
                entries,
                key=lambda e: (
                    _name_match_score(skill_key, e["home_repo"]),
                    _scope_specificity.get(e["scope"], 99),
                    e["home_repo"].lower(),
                ),
            )
            kept = entries_sorted[0]
            kept["conflict"] = True
            kept["conflict_alternates"] = [
                {"home_repo": e["home_repo"], "home_path": e["home_path"], "manifest_hash": e["manifest_hash"]}
                for e in entries_sorted[1:]
            ]
            proposed_skills[skill_key] = kept

    # Preserve deployment state from existing registry
    for skill_key, entry in proposed_skills.items():
        if skill_key in existing_skills:
            existing = existing_skills[skill_key]
            entry["deploys_to_machines"] = existing.get("deploys_to_machines", [])
            entry["deploys_to_repos"] = existing.get("deploys_to_repos", [])
            entry["last_deploy"] = existing.get("last_deploy", {})
            # Preserve retired status only if not conflict
            if not entry["conflict"]:
                entry["retired"] = existing.get("retired", False)

    # Detect scope drift
    scope_drifts: list[tuple[str, str, str]] = []
    for skill_key, entry in proposed_skills.items():
        if skill_key in existing_skills:
            reg_scope = existing_skills[skill_key].get("scope", "")
            new_scope = entry["scope"]
            if reg_scope and reg_scope != new_scope:
                scope_drifts.append((skill_key, reg_scope, new_scope))
                # Do NOT auto-update; keep registry scope
                entry["scope"] = reg_scope

    # Classify changes
    new_skills: list[str] = []
    removed_skills: list[str] = []
    unchanged: list[str] = []
    hash_changed: list[str] = []

    for skill_key in proposed_skills:
        if skill_key not in existing_skills:
            new_skills.append(skill_key)
        else:
            old_hash = existing_skills[skill_key].get("manifest_hash", "")
            new_hash = proposed_skills[skill_key]["manifest_hash"]
            if old_hash == new_hash:
                unchanged.append(skill_key)
            else:
                hash_changed.append(skill_key)

    for skill_key in existing_skills:
        if skill_key not in proposed_skills:
            removed_skills.append(skill_key)

    # If apply, write the registry
    if apply:
        new_registry = {
            "version": 1,
            "skills": proposed_skills,
            "written_by_machine": _detect_machine(),
            "written_at": datetime.now(timezone.utc).isoformat(),
        }
        save_registry(new_registry)

    return {
        "proposed_skills": proposed_skills,
        "conflicts": conflicts,
        "deploy_dups": deploy_dups,
        "scope_drifts": scope_drifts,
        "new_skills": new_skills,
        "removed_skills": removed_skills,
        "unchanged": unchanged,
        "hash_changed": hash_changed,
    }


def _detect_machine() -> str:
    """Detect current machine name from AIAssistant machines.json or hostname."""
    import socket
    machines_json = Path.home() / "Dropbox" / "Projects" / "AIAssistant" / "state" / "machines.json"
    hostname = socket.gethostname().lower()

    if machines_json.exists():
        try:
            with open(machines_json) as f:
                data = json.load(f)
            # Try to match hostname
            machines = data if isinstance(data, dict) else {}
            if "machines" in machines:
                machines = machines["machines"]
            if isinstance(machines, dict):
                for alias, info in machines.items():
                    h = info.get("hostname", "").lower()
                    if h and h in hostname:
                        return alias
            elif isinstance(machines, list):
                for m in machines:
                    h = m.get("hostname", "").lower()
                    if h and h in hostname:
                        return m.get("alias") or m.get("name", "unknown")
        except (json.JSONDecodeError, OSError):
            pass

    return hostname
