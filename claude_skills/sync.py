"""Sync skills to target systems — stub."""


def sync_system(system_name: str, *, dry_run: bool = False, apply: bool = False):
    """Sync skills to a target system."""
    raise NotImplementedError("sync.sync_system is a stub")


def diff_system(system_name: str) -> str:
    """Return a diff of local vs deployed state for a system."""
    raise NotImplementedError("sync.diff_system is a stub")
