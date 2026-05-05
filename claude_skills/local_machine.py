"""Detect this machine's identity by joining systems.yaml with machines.json.

systems.yaml entries carry a ``machine_alias`` that maps to a key in
``AIAssistant/state/machines.json`` (which records hardware facts including
``hostname``). This module's job is to figure out which systems.yaml entry
corresponds to the machine the CLI is currently running on, so cross-machine
sync triggering knows whether to dispatch a cowork-inbox task or run locally.

Matching algorithm:
  1. Read systems.yaml + machines.json.
  2. For each system, look up its ``machine_alias`` in machines.json and
     pull the recorded ``hostname``.
  3. Compare against ``socket.gethostname()`` (case-insensitive substring).
  4. Prefer an exact hostname match if any exists; otherwise return the
     first substring match.
  5. Return the systems.yaml key (e.g. ``"primary-laptop"``), not the
     machine_alias (``"primary-laptop"``) — these can differ
     (``email-mac`` vs ``emailmac``).
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

from claude_skills.systems import load_systems

_MACHINES_JSON = Path.home() / "Dropbox" / "Projects" / "AIAssistant" / "state" / "machines.json"


def _load_machines() -> dict:
    """Load machines.json -> dict[alias, machine_facts]."""
    if not _MACHINES_JSON.exists():
        return {}
    try:
        with open(_MACHINES_JSON) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    inner = data.get("machines", data)
    if isinstance(inner, dict):
        return inner
    if isinstance(inner, list):
        out = {}
        for m in inner:
            alias = m.get("alias") or m.get("name") or m.get("machine_alias")
            if alias:
                out[alias] = m
        return out
    return {}


def detect_local_system() -> str | None:
    """Return the systems.yaml key matching this machine, or None if no match.

    Match is by hostname (case-insensitive substring). Exact match wins over
    substring.
    """
    systems = load_systems()
    if not systems:
        return None

    machines = _load_machines()
    hostname = socket.gethostname().lower()

    exact: list[str] = []
    substring: list[str] = []

    for sys_name, sys_info in systems.items():
        alias = sys_info.get("machine_alias", sys_name)
        machine = machines.get(alias) or {}
        h = (machine.get("hostname") or "").lower()
        if not h:
            continue
        if h == hostname:
            exact.append(sys_name)
        elif h in hostname or hostname in h:
            substring.append(sys_name)

    if exact:
        return exact[0]
    if substring:
        return substring[0]
    return None


def require_local_system() -> str:
    """Like detect_local_system() but raise a ValueError if undetectable."""
    found = detect_local_system()
    if found is None:
        raise ValueError(
            "could not determine local machine: no systems.yaml entry matches "
            f"hostname {socket.gethostname()!r}. "
            "Edit state/systems.yaml or AIAssistant/state/machines.json to "
            "register this machine."
        )
    return found
