"""Sentinel-bracketed CLAUDE.md region writer.

The deployed ~/.claude/CLAUDE.md has the structure:

    <BEGIN tier1 sha=...>
    ...tier1 content...
    <END>

    <BEGIN tier2 sha=...>
    ...tier2 content...
    <END>

    <USER MARKER>
    ...arbitrary user additions, preserved verbatim across syncs...

The sentinels carry a 16-hex-char sha256 prefix of the content they
wrap so we can detect drift without re-reading the source files.
"""

import hashlib
import os
import re
import tempfile
import warnings
from pathlib import Path


# Sentinel templates. The {hash} placeholder is filled in at render time.
TIER1_BEGIN_TEMPLATE = "<!-- BEGIN CLAUDE-SKILLS MANAGED — tier1 — sha={hash} — DO NOT EDIT -->"
TIER1_END = "<!-- END CLAUDE-SKILLS MANAGED -->"
TIER2_BEGIN_TEMPLATE = "<!-- BEGIN CLAUDE-SKILLS MANAGED — tier2 — sha={hash} — DO NOT EDIT -->"
TIER2_END = "<!-- END CLAUDE-SKILLS MANAGED -->"
USER_MARKER = "<!-- USER ADDITIONS BELOW THIS LINE — preserved across syncs -->"

# Regexes for parsing existing managed files. Hash group is captured.
_TIER1_BEGIN_RE = re.compile(
    r"<!--\s*BEGIN CLAUDE-SKILLS MANAGED\s*—\s*tier1\s*—\s*sha=([0-9a-f]+)\s*—\s*DO NOT EDIT\s*-->"
)
_TIER2_BEGIN_RE = re.compile(
    r"<!--\s*BEGIN CLAUDE-SKILLS MANAGED\s*—\s*tier2\s*—\s*sha=([0-9a-f]+)\s*—\s*DO NOT EDIT\s*-->"
)
_END_RE = re.compile(r"<!--\s*END CLAUDE-SKILLS MANAGED\s*-->")
_USER_MARKER_RE = re.compile(re.escape(USER_MARKER))


def _content_hash(text: str) -> str:
    """Return first 16 hex chars of sha256(text). Stable, short, sufficient."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def parse_managed(target_path: Path) -> dict:
    """Parse an existing ~/.claude/CLAUDE.md.

    Returns a dict with:
        tier1_content: str | None
        tier1_hash:    str | None     # hash embedded in the BEGIN sentinel
        tier2_content: str | None
        tier2_hash:    str | None
        user_additions: str            # everything after USER_MARKER (verbatim)
                                        # If USER_MARKER is absent in a managed
                                        # file, treat everything after the
                                        # tier2 END as user_additions.
        is_managed: bool               # True iff both tier1 and tier2 sentinel
                                        # blocks were found and complete.
        is_pristine: bool              # True iff target file does not exist.
        missing_sentinels: list[str]   # e.g. ['tier2_end'] if file is mangled.
    """
    result = {
        "tier1_content": None,
        "tier1_hash": None,
        "tier2_content": None,
        "tier2_hash": None,
        "user_additions": "",
        "is_managed": False,
        "is_pristine": False,
        "missing_sentinels": [],
    }

    if not target_path.exists():
        result["is_pristine"] = True
        return result

    text = target_path.read_text(encoding="utf-8")

    # Find tier1 BEGIN
    t1_begin_matches = list(_TIER1_BEGIN_RE.finditer(text))
    t2_begin_matches = list(_TIER2_BEGIN_RE.finditer(text))
    end_matches = list(_END_RE.finditer(text))

    if len(t1_begin_matches) > 1:
        warnings.warn(
            f"{target_path}: multiple tier1 BEGIN sentinels found; using first.",
            stacklevel=2,
        )
    if len(t2_begin_matches) > 1:
        warnings.warn(
            f"{target_path}: multiple tier2 BEGIN sentinels found; using first.",
            stacklevel=2,
        )

    t1_begin = t1_begin_matches[0] if t1_begin_matches else None
    t2_begin = t2_begin_matches[0] if t2_begin_matches else None

    missing: list[str] = []
    if t1_begin is None:
        missing.append("tier1_begin")
    if t2_begin is None:
        missing.append("tier2_begin")

    # Pair each BEGIN with the next END that follows it.
    def _next_end_after(pos: int):
        for m in end_matches:
            if m.start() > pos:
                return m
        return None

    t1_end = _next_end_after(t1_begin.end()) if t1_begin else None
    t2_end = _next_end_after(t2_begin.end()) if t2_begin else None

    # Validate that the tier1 END comes before the tier2 BEGIN (sane ordering).
    if t1_begin and t1_end is None:
        missing.append("tier1_end")
    if t2_begin and t2_end is None:
        missing.append("tier2_end")
    if t1_begin and t2_begin and t1_end and t1_end.start() > t2_begin.start():
        # tier2 BEGIN appears before tier1 END — file is mangled.
        missing.append("tier1_end")

    result["missing_sentinels"] = missing

    # Extract content if both blocks fully bracketed.
    if t1_begin and t1_end:
        result["tier1_hash"] = t1_begin.group(1)
        # Content is between end of BEGIN sentinel and start of END sentinel.
        # Strip the leading + trailing newline so render produces stable output.
        body = text[t1_begin.end():t1_end.start()]
        result["tier1_content"] = body.strip("\n")

    if t2_begin and t2_end:
        result["tier2_hash"] = t2_begin.group(1)
        body = text[t2_begin.end():t2_end.start()]
        result["tier2_content"] = body.strip("\n")

    # is_managed iff all four sentinels present and ordered.
    result["is_managed"] = (
        t1_begin is not None
        and t1_end is not None
        and t2_begin is not None
        and t2_end is not None
        and not missing
    )

    # User additions: everything after USER_MARKER if present, else everything
    # after the tier2 END sentinel.
    user_text = ""
    if result["is_managed"]:
        post_tier2 = text[t2_end.end():]
        marker_match = _USER_MARKER_RE.search(post_tier2)
        if marker_match:
            user_text = post_tier2[marker_match.end():]
        else:
            user_text = post_tier2
        # Strip leading newlines but preserve trailing ones (and the user's
        # body verbatim apart from leading whitespace).
        user_text = user_text.lstrip("\n")

    result["user_additions"] = user_text
    return result


def render_managed(tier1: str, tier2: str, user_additions: str = "") -> str:
    """Build the rendered ~/.claude/CLAUDE.md content with sentinels.

    Computes tier1/tier2 hashes (first 16 hex chars of sha256 over the
    content) and embeds them in the BEGIN sentinels. Adds a trailing
    newline if the result lacks one.
    """
    # Normalize tier content: strip leading/trailing newlines so we control
    # spacing around the sentinels.
    tier1_body = tier1.strip("\n")
    tier2_body = tier2.strip("\n")

    h1 = _content_hash(tier1_body)
    h2 = _content_hash(tier2_body)

    parts = [
        TIER1_BEGIN_TEMPLATE.format(hash=h1),
        tier1_body,
        TIER1_END,
        "",
        TIER2_BEGIN_TEMPLATE.format(hash=h2),
        tier2_body,
        TIER2_END,
        "",
        USER_MARKER,
        "",
    ]
    rendered = "\n".join(parts)

    if user_additions:
        # Preserve the user's text verbatim; ensure a single newline separates
        # marker line from user content.
        rendered = rendered + user_additions.lstrip("\n")

    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def write_managed(
    target_path: Path,
    tier1: str,
    tier2: str,
    init: bool = False,
    dry_run: bool = False,
) -> dict:
    """Write a new ~/.claude/CLAUDE.md.

    Behavior:
      - If target file does NOT exist: write fresh (only if init=True or
        dry_run=True). Returns {'action': 'init', ...}.
      - If target exists and is_managed: replace tier1 and tier2 regions,
        preserve user_additions verbatim. Returns {'action': 'update', ...}.
      - If target exists but is_managed=False (sentinels missing/mangled):
        REFUSE to write unless init=True. Returns {'action': 'refused',
        'reason': 'sentinels missing — pass init=True to overwrite'}.
      - dry_run=True: never writes; returns rendered content for diff.

    Atomic write (write to .tmp, fsync, replace).
    """
    state = parse_managed(target_path)

    # Decide action.
    if state["is_pristine"]:
        if not (init or dry_run):
            return {
                "action": "refused",
                "reason": "target does not exist — pass init=True to create",
                "target_path": str(target_path),
                "rendered": None,
            }
        action = "init"
        user_additions = ""
    elif state["is_managed"]:
        action = "update"
        user_additions = state["user_additions"]
    else:
        if not init:
            missing = ", ".join(state["missing_sentinels"]) or "unknown"
            return {
                "action": "refused",
                "reason": (
                    f"sentinels missing or mangled ({missing}) — "
                    "pass init=True to overwrite"
                ),
                "target_path": str(target_path),
                "missing_sentinels": state["missing_sentinels"],
                "rendered": None,
            }
        action = "init"
        user_additions = ""

    rendered = render_managed(tier1, tier2, user_additions=user_additions)

    # Compute hashes for the result envelope.
    tier1_hash = _content_hash(tier1.strip("\n"))
    tier2_hash = _content_hash(tier2.strip("\n"))

    # Detect no-change for the update case (idempotency).
    if action == "update" and target_path.exists():
        existing_text = target_path.read_text(encoding="utf-8")
        if existing_text == rendered:
            return {
                "action": "no-change",
                "target_path": str(target_path),
                "tier1_hash": tier1_hash,
                "tier2_hash": tier2_hash,
                "rendered": rendered,
            }

    if dry_run:
        return {
            "action": action,
            "target_path": str(target_path),
            "tier1_hash": tier1_hash,
            "tier2_hash": tier2_hash,
            "rendered": rendered,
            "applied": False,
        }

    # Atomic write.
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=target_path.name + ".",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(rendered)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return {
        "action": action,
        "target_path": str(target_path),
        "tier1_hash": tier1_hash,
        "tier2_hash": tier2_hash,
        "rendered": rendered,
        "applied": True,
    }


# Helpers used by the CLI / sync layer.

def get_tier1() -> str:
    """Return the Tier 1 universal CLAUDE.md content."""
    tier1_path = Path(__file__).resolve().parent.parent / "claude_md" / "tier1.md"
    if not tier1_path.exists():
        raise FileNotFoundError(f"Tier 1 content not found at {tier1_path}")
    return tier1_path.read_text(encoding="utf-8")


def get_tier2(system_name: str, tier2_source: str | None = None) -> str:
    """Return the Tier 2 machine-specific CLAUDE.md content.

    If tier2_source is provided (relative to repo root), use that; otherwise
    fall back to systems/<system_name>/CLAUDE.md.
    """
    repo_root = Path(__file__).resolve().parent.parent
    if tier2_source:
        tier2_path = repo_root / tier2_source
    else:
        tier2_path = repo_root / "systems" / system_name / "CLAUDE.md"
    if not tier2_path.exists():
        raise FileNotFoundError(
            f"Tier 2 content not found for system '{system_name}' at {tier2_path}"
        )
    return tier2_path.read_text(encoding="utf-8")
