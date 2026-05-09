# B2 — AIAssistant skill refresh + ai-audit upgrades

## Repo
`/Users/chenry/Dropbox/Projects/AIAssistant`

## Mandatory reading (before editing anything)
1. **Audit findings:** `/Users/chenry/Dropbox/Projects/ResearchLibrary/agent-io/research/2026-05-06-ai-platform-skill-audit.md`
2. **Canonical conventions:** `/Users/chenry/Dropbox/Projects/ClaudeCommands/agent-io/plans/skill-conventions-2026-05-09.md`

Both files are required. Skill content must conform to the conventions spec.

## Files to refresh (9 skills + 1 audit upgrade)

### 1. `agent-io/skills/create-skill.md` (verdict NEEDS REFRESH)

- **Add frontmatter** per conventions §1. Currently the file has none and starts with `# Command: create-skill`. Use `name: Create Skill`, `description: <one sentence>`, `scope: global`, `type: meta` (or omit `type` if no other meta skill uses it — verify).
- **Phase 3 file location** — replace `/Users/chenry/Dropbox/Projects/ClaudeCommands/commands/` with the post-pivot flow: pick the home repo first (interactively), then write to `<repo>/agent-io/skills/<skill-name>.md`.
- **Phase 4 deployment** — replace `claude-commands update` with `python3 -m claude_skills.cli register <name> --home <repo>` followed by `claude-skills sync <machine> --apply` per target machine. Verify subcommand names with `claude-skills --help`.
- **Update example workflow** to match the new file location and deploy commands.

### 2. `agent-io/skills/ai-forge-ops.md` (verdict MINOR ISSUES)

- **Line ~349** — REMOVE the assertion that "there is no `cancel` subcommand". `agentforge cancel` exists at `src/agentforge/cli.py` (verify with `agentforge --help`). Replace with a usage example.
- **Add `cancel`** to the cheatsheet table at line ~156-167.
- **Add missing CLI subcommands** to the cheatsheet for completeness: `dashboard`, `build-sandbox`, `orchestrator`, `run`. (Verify against `agentforge --help`.)
- **Line ~413** — fix `src/assistant/state/worker_pool.py` reference. The function `get_worker_pool_status` lives in `src/assistant/state/forge.py`. Verify with `grep -n get_worker_pool_status src/assistant/state/forge.py`.
- **Add a one-line note** about `--replaces TASK_ID` flag (atomic cancel-and-resubmit) in the submit section.
- **Mention launchd/systemd auto-restart templates** briefly in operational tips.

### 3. `agent-io/skills/project-status.md` (verdict MINOR ISSUES)

- **Line ~50** — replace `/plan` reference with `/ai-design`. `/plan` was retired; `/ai-design` is its successor.

### 4. `agent-io/skills/ai-design.md` (verdict OK with minor)

- **Line ~183** — `agentforge plan` is not a current subcommand. Either remove the example or replace with the planner-role pattern (`agentforge submit --role planner …`). Verify with `agentforge --help`.

### 5. `agent-io/skills/ai-cowork.md` (verdict MINOR ISSUES)

- **"Cowork Skill Catalog Maintenance" section (line ~288-294)** — replace the "drop a `cw-{name}.md` into `~/.claude/commands/`" guidance with: write to `<repo>/agent-io/skills/cw-{name}.md`, then `claude-skills register cw-{name} --home <repo>`, then `claude-skills sync <machine> --apply` to deploy.

### 6. `agent-io/skills/ai-audit.md` (verdict MINOR ISSUES — INCLUDES STEP C UPGRADE)

This is the most substantive change in B2. Two related upgrades:

**6a. Update audit #9a** ("Cowork Skill Catalog (cw-)"):
- Currently scans `~/Dropbox/Projects/AIAssistant/cowork-skills/*.md`.
- Change to scan: (i) `state/skill_registry.json` for the registered cw-* set, and (ii) the canonical home `<repo>/agent-io/skills/cw-*.md` for each. Drop the legacy `cowork-skills/` directory check entirely (or note it as legacy and warn if any files exist there).

**6b. ADD a new audit type: "Skill Health"** (this is Step C from the design session). It should:
- Walk `state/skill_registry.json` to enumerate all registered skills with their home repo paths.
- For each skill at `<home_repo>/agent-io/skills/<skill>.md`, check:
  - Frontmatter exists and parses (per conventions §1).
  - `scope:` value is one of `repo:<X> | platform | global` (per conventions §2). Flag `universal` or other values.
  - `$ARGUMENTS` placeholder, if present, uses canonical form `## User Request\n\n$ARGUMENTS` (per conventions §3).
  - If a `<skill>/context/` directory exists, the main skill body references the files inside (string-grep for each filename in the body).
- Report per-skill verdict (OK / WARN / FAIL) with specific findings.
- Reference the conventions spec at `~/Dropbox/Projects/ClaudeCommands/agent-io/plans/skill-conventions-2026-05-09.md` as the source of truth.
- This audit type should slot into the audit-types list at the top of the skill, with a number (after audit #20 or wherever fits).

**6c. Audit #2** — drop the redundant `--auto-merge --auto-review` flags from the example, or note that these are role-dependent defaults now. Minor.

### 7. `agent-io/skills/cw-send-to-inbox.md` (verdict OK with minor)

- **Line ~117** — update example invocation: change `email-mac` → `emailmac`. Per machine-name normalization (commit `9fba5b8`).

### 8. `agent-io/skills/cw-create-signed-letter.md` (verdict MINOR ISSUES)

- **Frontmatter block** — drop the blank line between fields per conventions §1 (frontmatter must have no blank lines inside the block).

### 9. `agent-io/skills/ai-skills.md` (verdict OK)

- Add a one-line note in the skill purpose blurb stating the canonical home location: `<repo>/agent-io/skills/<skill>.md`. This helps users who land here from the (formerly) outdated claude-commands-expert.

## Apply to ALL files touched (conventions compliance pass)

Per `skill-conventions-2026-05-09.md`:
- Every refreshed file MUST have valid frontmatter per §1.
- `scope:` field must use canonical values per §2 (no `universal`).
- `$ARGUMENTS` placeholder, where present, must use canonical block per §3.
- For any skill that owns a `context/` sub-dir, the main file MUST explicitly reference each context file in Knowledge Loading per §4. (None of the AIAssistant skills currently own context dirs, but check.)

## Verification (must pass before declaring done)

```bash
cd /Users/chenry/Dropbox/Projects/AIAssistant
python3 -m claude_skills.cli inventory --check
python3 -m claude_skills.cli sync primary-laptop --dry-run

# Smoke-check the new Skill Health audit by running it locally:
PYTHONPATH=src python3 -c "from assistant.state.audit import run_audit; r = run_audit('skill_health'); print(r)"
```

All three must succeed.

## Out of scope
- The other AIAssistant skills not listed above (`ai-tasks`, `ai-registry`, `budget-justification` — verdict OK in audit, no action).
- Tooling in `claude_skills/`.
- Renaming files.

## Deliverables
- Nine refreshed skill files + ai-audit upgrade.
- Logical commits per skill or grouped commits, your call.
- Verification command output captured in commit message or PR body.
