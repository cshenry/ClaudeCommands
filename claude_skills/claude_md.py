"""CLAUDE.md rendering and management — stub."""

from pathlib import Path


def render_claude_md(system_name: str) -> str:
    """Render the full CLAUDE.md for a system (Tier 1 + Tier 2)."""
    raise NotImplementedError("claude_md.render_claude_md is a stub")


def get_tier1() -> str:
    """Return the Tier 1 universal CLAUDE.md content."""
    tier1_path = Path(__file__).resolve().parent.parent / "claude_md" / "tier1.md"
    if not tier1_path.exists():
        raise FileNotFoundError(f"Tier 1 content not found at {tier1_path}")
    return tier1_path.read_text()


def get_tier2(system_name: str) -> str:
    """Return the Tier 2 machine-specific CLAUDE.md content."""
    tier2_path = (
        Path(__file__).resolve().parent.parent / "systems" / system_name / "CLAUDE.md"
    )
    if not tier2_path.exists():
        raise FileNotFoundError(f"Tier 2 content not found for system '{system_name}'")
    return tier2_path.read_text()
