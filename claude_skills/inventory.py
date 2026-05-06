"""Skill inventory operations — walk known skill homes and reconcile with registry.

Skill source-of-truth location (canonical, post-Step-1 pivot):

    <repo>/agent-io/skills/<skill>.md
    <repo>/agent-io/skills/<skill>/    (optional sibling context dir)

Legacy locations still discovered for backwards compatibility (with a
one-line deprecation warning written to stderr per skill):

    <repo>/.claude/commands/<skill>.md   (any home repo)
    <repo>/commands/<skill>.md           (ClaudeCommands universals only)

Discovery order per home repo: ``agent-io/skills/`` wins; if a skill is
found there AND in a legacy location, the legacy copy is ignored (no
warning, since the source-of-truth is already correct). The legacy paths
disappear once ``claude-skills migrate-domain-skills --apply`` runs in
Step 2 of the convention pivot.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from claude_skills.frontmatter import extract_first_heading, parse_frontmatter
from claude_skills.manifest import compute_manifest_hash, list_skill_units
from claude_skills.registry import load_registry, save_registry


# Paths to key data files
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PROJECT_REGISTRY = (
    Path.home() / "Dropbox" / "Projects" / "AIAssistant" / "state" / "project_registry.yaml"
)
_PROJECT_REGISTRY_ENV = "CLAUDE_SKILLS_PROJECT_REGISTRY_PATH"
_AIASSISTANT_ROOT = Path.home() / "Dropbox" / "Projects" / "AIAssistant"
_USER_COMMANDS = Path.home() / ".claude" / "commands"


def _project_registry_path() -> Path:
    """Resolve project_registry.yaml path, honoring the env override."""
    override = os.environ.get(_PROJECT_REGISTRY_ENV)
    if override:
        return Path(override)
    return _DEFAULT_PROJECT_REGISTRY


# Track which (repo, source_kind) pairs we've already warned about so the
# deprecation banner is one-line-per-repo-per-source instead of per-skill.
_DEPRECATION_REPORTED: set[tuple[str, str]] = set()


def _warn_legacy_source(repo_name: str, source_kind: str, source_path: Path) -> None:
    """Emit a one-line deprecation warning to stderr (deduped per repo+kind)."""
    key = (repo_name, source_kind)
    if key in _DEPRECATION_REPORTED:
        return
    _DEPRECATION_REPORTED.add(key)
    print(
        f"  WARNING: {repo_name}: legacy skill source {source_kind} at "
        f"{source_path} — run `claude-skills migrate-domain-skills --apply` "
        f"to relocate to agent-io/skills/.",
        file=sys.stderr,
    )


def _infer_scope_from_home(home_repo: str) -> str:
    """Infer scope from the home repository identifier."""
    if home_repo == "ClaudeCommands":
        return "universal"
    if home_repo == "AIAssistant":
        return "platform"
    return "domain"


def _load_project_registry() -> dict:
    """Load AIAssistant project registry (honors env override for tests)."""
    path = _project_registry_path()
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("projects", {})


def _resolve_repo_path_with_ancestors(project_id: str, projects: dict) -> str | None:
    """Walk parent chain to find inherited ``repo_path``."""
    visited: set[str] = set()
    pid = project_id
    while pid and pid not in visited:
        visited.add(pid)
        entry = projects.get(pid, {}) or {}
        rp = entry.get("repo_path")
        if rp:
            return rp
        pid = entry.get("parent")
    return None


def _candidate_skill_dirs(repo_root: Path, repo_name: str) -> list[tuple[Path, str]]:
    """Return the ordered list of (skills_dir, source_kind) for a home repo.

    ``source_kind`` values:
      - "agent-io/skills"     canonical
      - ".claude/commands"    legacy (any repo)
      - "commands"            legacy (ClaudeCommands universals only)

    Order matters: callers walk these in order and skip a skill_key once
    it's been claimed by an earlier (higher-priority) directory.
    """
    out: list[tuple[Path, str]] = []
    primary = repo_root / "agent-io" / "skills"
    if primary.is_dir():
        out.append((primary, "agent-io/skills"))
    legacy_claude = repo_root / ".claude" / "commands"
    if legacy_claude.is_dir():
        out.append((legacy_claude, ".claude/commands"))
    if repo_name == "ClaudeCommands":
        legacy_top = repo_root / "commands"
        if legacy_top.is_dir():
            out.append((legacy_top, "commands"))
    return out


def _get_home_repos() -> list[tuple[str, Path, str]]:
    """Get all home repos to scan.

    Returns list of (repo_name, repo_root, scope). The actual skill dirs
    are computed per-repo via ``_candidate_skill_dirs``.
    """
    homes: list[tuple[str, Path, str]] = []

    # 1. ClaudeCommands -> universal (the repo this CLI lives in)
    homes.append(("ClaudeCommands", _REPO_ROOT, "universal"))

    # 2. AIAssistant -> platform
    if _AIASSISTANT_ROOT.is_dir():
        homes.append(("AIAssistant", _AIASSISTANT_ROOT, "platform"))

    # 3. Every project in the registry that has a repo_path -> domain.
    projects = _load_project_registry()
    seen_repo_names = {"ClaudeCommands", "AIAssistant"}
    for pid, info in projects.items():
        name = info.get("name") or pid
        if name in seen_repo_names:
            continue
        rp = _resolve_repo_path_with_ancestors(pid, projects)
        if not rp:
            continue
        repo_root = Path(rp).expanduser()
        if not repo_root.is_dir():
            continue
        homes.append((name, repo_root, "domain"))
        seen_repo_names.add(name)

    return homes


def inventory(apply: bool = False, machine: str | None = None) -> dict:
    """Walk known skill homes and reconcile with state/skill_registry.json.

    Walks each home repo in priority order: ``agent-io/skills/`` first,
    then ``.claude/commands/`` (deprecated), then ``commands/`` (deprecated,
    ClaudeCommands only). A skill key claimed by a higher-priority dir is
    not re-discovered from a lower-priority dir in the same repo.

    Returns a dict with keys:
        proposed_skills: dict[name, entry]
        conflicts: list[name]
        scope_drifts: list[(name, registry_scope, frontmatter_scope)]
        new_skills: list[name]
        removed_skills: list[name]
        unchanged: list[name]
        hash_changed: list[name]
        repo_deploys_drifts: list[(name, registry_repos, frontmatter_repos)]
        home_target_warnings: list[(name, home_repo)]
    """
    # Reset deprecation dedupe for each top-level run so back-to-back
    # CLI invocations both surface warnings.
    _DEPRECATION_REPORTED.clear()

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

    for repo_name, repo_root, default_scope in homes:
        # Track which skill keys we've already claimed from a higher-priority
        # source within this repo so we don't double-register from a legacy
        # mirror that hasn't been migrated yet.
        claimed_in_repo: set[str] = set()

        for skills_dir, source_kind in _candidate_skill_dirs(repo_root, repo_name):
            anchors = list_skill_units(skills_dir)
            if anchors and source_kind != "agent-io/skills":
                _warn_legacy_source(repo_name, source_kind, skills_dir)

            for anchor in anchors:
                fm, body = parse_frontmatter(anchor)

                # Determine skill name
                skill_name = fm.get("name", anchor.stem)
                # Normalize to lowercase-kebab for registry key
                skill_key = anchor.stem

                if skill_key in claimed_in_repo:
                    # Already discovered in a higher-priority dir for this repo.
                    continue

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
                description = fm.get("description", "") or extract_first_heading(body) or ""

                # Compute hash
                manifest_hash = compute_manifest_hash(anchor)

                # Determine domain
                domain = None
                if fm_scope == "domain" or default_scope == "domain":
                    domain = _repo_name_to_pid.get(repo_name, repo_name.lower())

                # Parse deploys_to_repos from frontmatter — optional list of
                # repo names (or ["*"] wildcard). Wildcard is preserved
                # verbatim at inventory time and expanded only at sync-repos
                # time.
                fm_drepos = fm.get("deploys_to_repos")
                if fm_drepos is None:
                    deploys_to_repos: list[str] = []
                elif isinstance(fm_drepos, list):
                    deploys_to_repos = [str(x) for x in fm_drepos]
                elif isinstance(fm_drepos, str):
                    # Tolerate scalar form: "AgentForge" or "*"
                    deploys_to_repos = [fm_drepos]
                else:
                    deploys_to_repos = []

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
                    "deploys_to_repos": deploys_to_repos,
                    "last_deploy": {},
                    "last_repo_deploy": {},
                }

                if skill_key not in discovered:
                    discovered[skill_key] = []
                discovered[skill_key].append(entry)
                claimed_in_repo.add(skill_key)

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

    # Preserve deployment state from existing registry. We DO let
    # frontmatter override deploys_to_repos (it's the source of truth for
    # which repos a universal skill travels into) but emit a drift line
    # when registry and frontmatter disagree, so users notice.
    repo_deploys_drifts: list[tuple[str, list[str], list[str]]] = []
    home_target_warnings: list[tuple[str, str]] = []
    for skill_key, entry in proposed_skills.items():
        if skill_key in existing_skills:
            existing = existing_skills[skill_key]
            entry["deploys_to_machines"] = existing.get("deploys_to_machines", [])
            entry["last_deploy"] = existing.get("last_deploy", {})
            entry["last_repo_deploy"] = existing.get("last_repo_deploy", {})
            # deploys_to_repos: frontmatter wins, but record drift if changed.
            existing_drepos = sorted(existing.get("deploys_to_repos") or [])
            new_drepos = sorted(entry.get("deploys_to_repos") or [])
            if existing_drepos != new_drepos:
                repo_deploys_drifts.append((skill_key, existing_drepos, new_drepos))
            # Preserve retired status only if not conflict
            if not entry["conflict"]:
                entry["retired"] = existing.get("retired", False)

        # home_repo == target drift — would clobber the skill's source.
        # Detected here so the user sees the warning before the first sync.
        # Wildcard "*" is fine; only literal home-repo entries are flagged.
        drepos = entry.get("deploys_to_repos") or []
        home = entry.get("home_repo") or ""
        if home and home in drepos:
            home_target_warnings.append((skill_key, home))

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
        "repo_deploys_drifts": repo_deploys_drifts,
        "home_target_warnings": home_target_warnings,
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
