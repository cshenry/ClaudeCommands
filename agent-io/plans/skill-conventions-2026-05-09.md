# Skill Conventions (canonical) — 2026-05-09

This is the canonical convention spec for skill files in any home repo, settled during the 2026-05-09 `/ai-design` session that scoped the audit-driven refresh of the 2026-05-06 audit (`~/Dropbox/Projects/ResearchLibrary/agent-io/research/2026-05-06-ai-platform-skill-audit.md`).

All skill-refresh work performed against this audit must conform to these conventions. They supersede any prior implicit norms.

## 1. Frontmatter (required, no exceptions)

Every skill file at `<home_repo>/agent-io/skills/<skill>.md` MUST begin with a YAML frontmatter block:

```yaml
---
name: <Human-Readable Name>
description: <one-sentence description, under 100 chars>
scope: <universal | platform | domain>
---
```

Optional fields (use only when meaningful):

- `type: cowork` — for `cw-*` cowork skills.
- `home: <RepoName>` — explicit home repo when not derivable from file location (e.g., `home: AgentForge`). Tooling already tracks `home_repo` separately based on the file's source path; this field is informational only.
- `version: <int>` — increment on substantive content refresh.

The `---` opener must be on line 1. No blank line above. No blank lines between fields inside the block. The `---` closer must be immediately followed by a blank line, then the skill body (`# Title`).

## 2. `scope:` value-set (canonical)

The `scope:` field is the **deployment scope** — *who subscribes to this skill*, not where it lives. Where it lives is recorded separately in the registry's `home_repo` field (derived from the skill's file path); do not duplicate it in `scope:`.

Exactly three values are allowed (matches the `claude_skills` tooling enum):

- **`universal`** — Deploys broadly across all subscribed machines and target repos. Cross-cutting platform skills like `claude-commands-expert`, `envman-expert`, `cw-*` cowork skills.
- **`platform`** — Deploys to platform-class machines (those with `subscriptions: ["platform"]` in `state/systems.yaml`). Skills like `ai-audit`, `ai-design`, `ai-forge-ops` that operate on the AI platform itself.
- **`domain`** — Deploys narrowly to its home repo only. Component-expert skills like `agentforge-expert`, `emailassistant-expert`, and ops skills like `worker`, `emailassistant-ops`.

Earlier drafts of this spec used `repo:<X> | platform | global`, conflating "where the skill lives" (home_repo) with "where it deploys" (scope). The tooling's vocabulary is canonical; the conventions spec follows it.

`global`, `repo:<X>`, and any other value are RETIRED in skill frontmatter. The tooling discards unknown values and falls back to a default — silent drift. Convert via the rules:

| Old value | New value |
|---|---|
| `global` | `universal` |
| `repo:<X>` | `domain` (and tooling reads home_repo from file path) |
| `universal` | `universal` (already correct) |
| `platform` | `platform` (already correct) |
| `domain` | `domain` (already correct) |

## 3. `$ARGUMENTS` placeholder (canonical form)

Every skill that accepts user arguments MUST end with this exact block (literal):

```markdown
## User Request

$ARGUMENTS
```

Two newlines between the heading and `$ARGUMENTS`. No other heading text. No other ordering. Skills that don't accept arguments may omit the block entirely; do NOT use any alternate form (`## $ARGUMENTS` alone, etc.).

## 4. Context-dir loading (option a — explicit references)

When a skill ships a `<skill>/context/` sub-directory, the main skill file MUST explicitly reference each context file in its **Knowledge Loading** section under a sub-heading **"Context files"**:

```markdown
## Knowledge Loading

**Always-load primary references:**
- `/abs/path/to/README.md`
- `/abs/path/to/architecture.md`

**Load on demand:**
- `/abs/path/to/source.py` — when answering implementation questions

**Context files** (auto-loaded with the skill):
- `agent-io/skills/<skill>/context/<file>.md` — one-line description of when this loads
```

If a context dir exists but the main file does not reference its files, the audit treats the dir as "dead weight" and flags it. Either reference the files, or delete the dir.

## 5. Section ordering for `-expert` skills (canonical)

`-expert` skills (any skill ending in `-expert.md`) follow this section ordering. Other skills (commands like `ai-*`, ops skills like `*-ops`) may diverge but should still use the frontmatter and `$ARGUMENTS` conventions above.

1. Frontmatter (per §1)
2. `# <Domain> Expert` — title.
3. **Opening declaration:** "You are an expert on <repo>… deep knowledge of: 1) Topic, 2) Topic, …"
4. **Project Location** (or **Repository Purpose**) — absolute path + one-paragraph mission statement.
5. **Related Skills** — sibling ops/expert skills + when to use which.
6. **Knowledge Loading** — split per §4.
7. **Architecture Overview** — diagram or text, max ~60 lines.
8. **Key Classes / Modules** — table.
9. **Quick Reference** — common workflows + common mistakes.
10. **Common Tasks** or **Response Patterns** — how to handle frequent question types.
11. **User Request** — `$ARGUMENTS` placeholder per §3.

Length budget: 200–400 lines for `-expert` skills. If pushing past 400, move detail into `<skill>/context/` files and explicitly reference them per §4.

## 6. Verification commands

After any refresh, the agent MUST run and pass:

```bash
# Frontmatter validity
python3 -m claude_skills.cli inventory --check

# Sync dry-run (no surprises)
python3 -m claude_skills.cli sync $(hostname-short) --dry-run
```

Both must succeed without errors before the agent considers the task complete.
