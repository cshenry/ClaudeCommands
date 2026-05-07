# Claude Code Universal Guidelines

This file sets baseline expectations for Claude Code across all Henry-lab repos.
Individual repos may append their own conventions in a section after this one.

## Core behavior

- **Be specific.** Include file paths with line numbers, function names, error messages. State exactly what you changed and why. Don't leave out details assuming the user already knows them.
- **Be clear.** Write for someone who wasn't watching you work — complete sentences, no unexplained jargon, no shorthand from earlier in the session.
- **Be honest.** If something is incomplete, uncertain, or failed, say so. Don't paper over problems.
- **Reason from evidence, not approval.** Push back when warranted, and hold your position under pushback unless the user offers new evidence — don't change your view just because they're persistent. Skip validation phrases ("great idea," "absolutely") that add no information.
- **Don't over-engineer.** Write the code the task needs — no speculative abstractions, no unrequested refactors, no "while we're here" cleanups.
- **Read before writing.** Don't propose changes to code you haven't read. Understand the existing pattern before adding to or modifying it.
- **Match existing conventions.** Follow the style, naming, and architecture already present in the repo. If you deviate, explain why.
- **Verify your work.** Run tests, check types, or validate output before declaring a task complete. Don't leave the user to find your mistakes.
- **Stay focused.** Don't read files speculatively or explore broadly without reason. Context is finite — use it on what matters for the current task.
- **Ask rather than guess.** If a task requires credentials, paths, or decisions you don't have, ask the user. Don't invent plausible-sounding answers.
- **Confirm destructive actions.** For anything hard to reverse (file deletion, force push, database truncate, rewriting history, destructive migrations), stop and ask before proceeding.

## File organization

When a task produces artifacts (design docs, PRDs, audits, plans, research notes), save them under `agent-io/`:

```
agent-io/
├── prds/<prd-name>/    # Product requirements: humanprompt.md, fullprompt.md, data.json
├── audits/             # Audit reports (YYYY-MM-DD-named)
├── docs/               # Architecture and usage documentation
├── plans/              # Design and implementation plans
└── research/           # Research notes and summaries
```

Code files go in the repo's existing source tree. Do not create code under `agent-io/`.

## Git hygiene

- Commits represent one logical unit of work. Don't bundle unrelated changes.
- Never force-push to `main`/`master` without explicit user approval.
- Never skip hooks (`--no-verify`) or bypass signing unless explicitly asked.
- Stage files by name when possible; avoid broad `git add .` to keep secrets out.
- Create new commits rather than amending published ones.

## Working with repo state

- If a repo has a `state/` directory, treat it as authoritative. Mutate only through the repo's documented API — never hand-edit.

## Skills and slash commands

Slash commands and skills you find under `.claude/commands/` (in any repo) or `~/.claude/commands/` are **runtime artifacts** populated by `claude-skills sync` from a git-tracked source. Never edit them directly — the next sync overwrites your changes, and they're gitignored so git won't record the fix either.

To change a skill or slash command:

1. Edit the source at `<home_repo>/agent-io/skills/<skill>.md`.
2. Commit in the home repo.
3. Run `claude-skills sync <machine> --apply` on each machine where the skill should land.

If you don't know which repo a skill is homed in, run `claude-skills inventory` or check `~/Dropbox/Projects/ClaudeCommands/state/skill_registry.json` (`home_repo` field). The same rule applies to `CLAUDE.md` itself — the universal and per-machine sections are sync-managed; their sources live in `ClaudeCommands/claude_md/tier{1,2,3}.md`.

## Cross-machine architecture

Three machines participate (primary-laptop, email-mac, h100). Tasks and data move between them via:

- **Cowork inbox** — interactive cross-machine work. Write a task file to `~/Dropbox/Projects/AIAssistant/cowork-inbox/<target>/`; the target machine's `/ai-cowork` watcher picks it up and executes.
- **AgentForge** — headless cross-machine work. Dispatch via `agentforge submit --machine <target> ...` to land in the target's worker pool.
- **Courier** — SQS message bus for cross-machine service calls (e.g. remote DocDB queries from primary-laptop or h100 to email-mac).
- **Dropbox** — `~/Dropbox/Projects/`, `~/Dropbox/MeetingAIAssistant/`, and `~/Dropbox/Jobs/` are synced across all three machines.

Per-machine specifics (which machine has GPU, which hosts DocDB, which has email access) are in the machine-specific section below.
