"""System definitions — joins systems.yaml with machines.json to produce merged system records."""

import json
from pathlib import Path

import yaml

_STATE_DIR = Path(__file__).resolve().parent.parent / "state"
_SYSTEMS_YAML = _STATE_DIR / "systems.yaml"

# machines.json lives in AIAssistant (Dropbox-synced, authoritative for hardware facts)
_MACHINES_JSON_CANDIDATES = [
    Path.home() / "Dropbox" / "Projects" / "AIAssistant" / "state" / "machines.json",
]


def _find_machines_json() -> Path | None:
    """Locate machines.json on this machine, or return None."""
    for candidate in _MACHINES_JSON_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def load_systems() -> dict:
    """Load and join systems.yaml with machines.json.

    Returns a dict keyed by system name, each value a merged dict of:
      - fields from systems.yaml (mode, tier2_path, etc.)
      - hardware/service facts from machines.json (if available)

    If machines.json is not found (e.g. Dropbox not synced), returns
    systems.yaml data only with a '_machines_json': False flag.
    """
    if not _SYSTEMS_YAML.exists():
        return {}

    with open(_SYSTEMS_YAML) as f:
        systems_data = yaml.safe_load(f) or {}

    systems = systems_data.get("systems", {})

    # Try to join with machines.json
    machines_path = _find_machines_json()
    if machines_path is None:
        for name in systems:
            systems[name]["_machines_json"] = False
        return systems

    with open(machines_path) as f:
        machines_data = json.load(f)

    # machines.json is keyed by machine alias
    machines_by_alias = {}
    if isinstance(machines_data, list):
        for m in machines_data:
            alias = m.get("alias") or m.get("name") or m.get("machine_alias")
            if alias:
                machines_by_alias[alias] = m
    elif isinstance(machines_data, dict):
        # Could be directly keyed by alias, or have a "machines" key
        inner = machines_data.get("machines", machines_data)
        if isinstance(inner, dict):
            # Dict keyed by machine name -> facts
            machines_by_alias = inner
        elif isinstance(inner, list):
            for m in inner:
                alias = m.get("alias") or m.get("name") or m.get("machine_alias")
                if alias:
                    machines_by_alias[alias] = m

    # Merge
    for name, sys_info in systems.items():
        machine_alias = sys_info.get("machine_alias", name)
        if machine_alias in machines_by_alias:
            machine_facts = machines_by_alias[machine_alias]
            # machine facts go under a 'hardware' sub-key to avoid collisions
            sys_info["hardware"] = machine_facts
            sys_info["_machines_json"] = True
        else:
            sys_info["_machines_json"] = False

    return systems
