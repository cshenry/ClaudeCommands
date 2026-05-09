# B1 — ClaudeCommands skill refresh

## Repo
`/Users/chenry/Dropbox/Projects/ClaudeCommands`

## Mandatory reading (before editing anything)
1. **Audit findings:** `/Users/chenry/Dropbox/Projects/ResearchLibrary/agent-io/research/2026-05-06-ai-platform-skill-audit.md`
2. **Canonical conventions:** `/Users/chenry/Dropbox/Projects/ClaudeCommands/agent-io/plans/skill-conventions-2026-05-09.md`

Both files are required. Skill content must conform to the conventions spec.

## Files to refresh
1. `agent-io/skills/claude-commands-expert.md` (315 lines, verdict STALE)
2. `agent-io/skills/envman-expert.md` (313 lines, verdict OK with minor)

## Required changes — claude-commands-expert.md

This skill is the meta-skill about the skill system itself. It is currently teaching the pre-pivot world. Full content rewrite is needed.

1. **CLI surface — replace the entire `claude-commands install/update/addproject/list/removeproject` documentation** with the current `claude-skills` CLI. The current CLI lives at `claude_skills/cli.py`. Verify the actual subcommand list with `python3 -m claude_skills.cli --help` before writing — do not rely on memory. At a minimum cover: `inventory`, `status`, `sync`, `register`, `retire`, `rename`, `system`, `migrate-domain-skills`. Document each with a short example.
2. **Repository Structure section** — must show the post-pivot layout: skills source-of-truth at `<home_repo>/agent-io/skills/<skill>.md` per home repo; ClaudeCommands' own role is the **registry/sync system**, not the skill source. Reference `state/skill_registry.json` and `state/deployment_log.jsonl` as canonical state files.
3. **Knowledge Loading section** — must reference `claude_skills/cli.py`, `claude_skills/registry.py`, `state/skill_registry.json`, plus the three context-dir files: `agent-io/skills/claude-commands-expert/context/architecture.md`, `cli-reference.md`, `skill-development.md`. (Per conventions §4, context files MUST be explicitly listed.)
4. **Deployment Flow diagram** — replace the `commands/ → install / addproject / update` flow with `agent-io/skills/<skill>.md → register → sync <machine> --apply → ~/.claude/commands/`.
5. **Troubleshooting "skill not loading"** — replace the `claude-commands update` advice with `claude-skills sync <machine> --apply`.
6. **Available skills list** — refresh against `state/skill_registry.json`. The current frozen subset is months out of date.
7. **Strike `/create-skill` recommendations** if and only if `/create-skill` is no longer the canonical create flow post-pivot. (B2 is rewriting `create-skill` in parallel; if it survives, keep the reference; otherwise point at the new flow. Coordinate by reading `agent-io/skills/create-skill.md` from the AIAssistant repo at the time you write.)

## Required changes — envman-expert.md

1. **Frontmatter `scope:` field** — currently `universal`. Change to `global` per conventions §2.
2. **Knowledge Loading section** — add explicit references for the three context files: `agent-io/skills/envman-expert/context/cli-reference.md`, `development-guide.md`, `workflows.md`. Per conventions §4.
3. **Verify the helper-function table** at line ~187-194 (`venv_home`, `load_projects`, `save_projects`, `find_python`, `write_activate_sh`, `install_dependencies`) by grepping `venvman.py`. Correct any drift.
4. Otherwise leave content alone — verdict was OK.

## Apply to BOTH files (conventions compliance pass)

Per `skill-conventions-2026-05-09.md`:
- Frontmatter must conform to §1.
- `$ARGUMENTS` placeholder must use the canonical block per §3 (`## User Request\n\n$ARGUMENTS`). Replace any alternate form.
- Section ordering for `-expert` skills must match §5.

## Verification (must pass before declaring done)

```bash
cd /Users/chenry/Dropbox/Projects/ClaudeCommands
python3 -m claude_skills.cli inventory --check
python3 -m claude_skills.cli sync primary-laptop --dry-run
```

Both must succeed without errors.

## Out of scope
- Other skills in this repo (none others in scope per audit).
- Tooling changes to `claude_skills/`.
- Renaming files.

## Deliverables
- Two refreshed skill files.
- One commit per skill (or one combined commit, your call), with descriptive message.
- Verification command output captured in commit message or PR body.
