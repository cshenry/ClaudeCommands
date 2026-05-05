# CLAUDE.md Tier 1 + Tier 2 Drafts (Authorized 2026-05-04)

**Status:** Authorized drafts — not yet deployed. Phase 1 of the [ClaudeCommands reboot plan](../../../../.claude/plans/note-home-mac-should-reflective-willow.md) will move these to their final paths (`claude_md/tier1.md`, `systems/<machine>/CLAUDE.md`).

**Source basis:**

- Tier 1 changes derived from [agent-io/research/claude-md-best-practices-2026-05-03.md](../research/claude-md-best-practices-2026-05-03.md)
- Tier 2 facts pulled from [AIAssistant/state/machines.json](../../../AIAssistant/state/machines.json) plus user fact-checks on 2026-05-04 (worker counts, h100 paths, cross-machine architecture)

---

## Tier 1 — Universal CLAUDE.md (deployed to every machine + every repo)

````markdown
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

## Cross-machine architecture

Three machines participate (primary-laptop, email-mac, h100). Tasks and data move between them via:

- **Cowork inbox** — interactive cross-machine work. Write a task file to `~/Dropbox/Projects/AIAssistant/cowork-inbox/<target>/`; the target machine's `/ai-cowork` watcher picks it up and executes.
- **AgentForge** — headless cross-machine work. Dispatch via `agentforge submit --machine <target> ...` to land in the target's worker pool.
- **Courier** — SQS message bus for cross-machine service calls (e.g. remote DocDB queries from primary-laptop or h100 to email-mac).
- **Dropbox** — `~/Dropbox/Projects/`, `~/Dropbox/MeetingAIAssistant/`, and `~/Dropbox/Jobs/` are synced across all three machines.

Per-machine specifics (which machine has GPU, which hosts DocDB, which has email access) are in the machine-specific section below.
````

**Changes from current SYSTEM-PROMPT.md:**

- ADDED to Core behavior: Be clear, Reason from evidence, Verify your work, Stay focused, Ask rather than guess
- COLLAPSED "Working with repo state" paragraph from 3 sentences to 1 actionable bullet
- ADDED "Cross-machine architecture" section (lifted from duplicate Interactions sections in per-machine Tier 2)
- REMOVED trailing "Repo-specific conventions" placeholder block (deployment scaffolding, not instruction)
- Final size: ~36 content lines. Within community optimum (30–80) and well under official limit (200).

---

## Tier 2 — Machine-specific CLAUDE.md (concatenated with Tier 1 to form ~/.claude/CLAUDE.md)

### `systems/primary-laptop/CLAUDE.md`

```markdown
# Machine: primary-laptop

## Role
Primary interactive development. Human is typically present and responsive. This is the orchestrator — direct work, design sessions, and dispatch of tasks to email-mac and h100 happen here.

## Services & Tools
- AgentForge: 1 worker, daemon active
- Redis 8.6.1 (Homebrew, port 6379)
- Docker 29.0.2 (Homebrew)
- Python 3.11.14 via pyenv shims
- node, gh, git, claude, venvman

## Paths
- Projects: ~/Dropbox/Projects/
- AgentForge tasks: ~/Dropbox/Jobs/agentforge/tasks
- Virtual environments: ~/VirtualEnvironments/
- Cowork inbox: ~/Dropbox/Projects/AIAssistant/cowork-inbox/primary-laptop/

## Privacy posture
Standard. DocDB queries (via Courier to email-mac) are permitted; results stay on this machine. Never send sensitive content (email, grant proposals, NDA-covered work) to external services, pastebins, or diagram renderers.

## Constraints
- This is a laptop — avoid long-running GPU workloads or heavy parallel builds. Delegate compute-heavy tasks to h100 (GPU) or email-mac (general-purpose) via AgentForge.
```

### `systems/email-mac/CLAUDE.md`

```markdown
# Machine: email-mac

## Role
Dedicated ANL email capture (Outlook AppleScript — only machine with ANL email access), private DocDB host (other machines query via Courier), and AgentForge worker pool. Primarily headless — human interaction is infrequent.

## Services & Tools
- AgentForge: 3 workers
- DocDB: PostgreSQL+pgvector running locally; queryable directly via local API (fill in URL/port)
- EmailAssistant capture daemon (active, do not interfere)
- Redis 8.6.2 (port 6379)
- Docker 29.3.1 via Colima (no Docker Desktop due to licensing)
- Python 3.12.13
- Outlook in legacy Exchange mode

## Paths
- Projects: ~/Dropbox/Projects/
- AgentForge tasks: ~/Dropbox/Jobs/agentforge/tasks
- Virtual environments:
  - AgentForge: /Users/chenry/VirtualEnvironments/AgentForge-py3.12
  - EmailAssistant: /Users/chenry/VirtualEnvironments/EmailAssistant-py3.12
- Cowork inbox: ~/Dropbox/Projects/AIAssistant/cowork-inbox/email-mac/

## Privacy posture
**STRICT.** This machine holds grant proposals, HR correspondence, NDA-covered content, and ANL email.

- NEVER send email content, DocDB results, attachment text, or database dumps to external services, third-party APIs, diagram renderers, or pastebins.
- NEVER include document content in git commits, PRs, or task outputs.
- Local-only LLM analysis only — do not call external APIs from worker prompts when handling sensitive content.
- When uncertain whether content is sensitive, treat it as sensitive.

## Constraints
- Do not restart or interfere with the EmailAssistant capture daemon.
- Colima is used for Docker; if Docker commands fail, check `colima status`.
```

### `systems/h100/CLAUDE.md`

```markdown
# Machine: h100

## Role
GPU compute server (poplar.cels.anl.gov, NVIDIA H100), AgentForge worker, embedding host. Fully headless — no human interactive sessions. Receives GPU dispatch from primary-laptop and email-mac via AgentForge.

## Services & Tools
- AgentForge: 1 worker
- NVIDIA H100 GPU
- Docker installed
- Python 3.12 (system)
- Linux (no macOS-specific tools — no AppleScript, no Outlook, no homebrew paths)

## Paths
- Projects: /home/chenry/Dropbox/Projects (Dropbox is synced on this machine)
- AgentForge tasks: /home/chenry/Dropbox/jobs/agentforge/tasks
- AgentForge config: ~/.agentforge/config.yaml (machine_alias=h100)
- Cowork inbox: /home/chenry/Dropbox/Projects/AIAssistant/cowork-inbox/h100/

## Privacy posture
No sensitive documents on this machine. Standard code privacy: don't leak API keys or credentials in outputs.

## Constraints
- This is a shared compute host (poplar.cels.anl.gov) shared with other users — be considerate of GPU memory and disk. Avoid loading multiple large GPU models simultaneously.
- No interactive `/ai-*` sessions here. Those run on primary-laptop and dispatch tasks via AgentForge or cowork-inbox.
- No sudo access — this is a devops-managed machine and we are unprivileged users.
- Persist outputs to Dropbox-synced directories (`/home/chenry/Dropbox/...`) so they reach other machines. Treat `/scratch` and `/tmp` as ephemeral.
- No human watching — when uncertain about a task, fail loudly with a clear error rather than guessing. Do not invent paths or capabilities not verified against this machine's actual environment.
- Linux paths only (no `~/Library/...`, no `/Applications/...`).
```

---

## Verification checklist before deploying

Before Phase 1 sync writes these to `~/.claude/CLAUDE.md` on each machine:

- Tier 1 reads correctly when concatenated with each Tier 2
- Combined Tier 1 + Tier 2 stays under ~60 lines (community optimum)
- No facts contradicted by `state/machines.json`
- No paths referenced that don't exist on the target machine
- Privacy posture wording matches your actual operational policy
- DocDB local API URL/port filled in on email-mac
- User reviews and signs off on each Tier 2 before sync writes it

## Notes for Phase 1 implementation

- Sentinel-bracketed managed regions (per the plan), not `@path` imports — preserves "warn before clobber" guarantee.
- Add `## Things That Will Bite You` as an optional standard section header for Tier 3 files (per 2026-05-04 design decision). Each repo's existing Tier 3 can add this section as it organically accumulates gotchas.
- Tier 1's "Cross-machine architecture" section assumes 3 machines today. When kberdl-dev or future machines are added, update this list (and add their Tier 2 file under `systems/`).
