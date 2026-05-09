# B3 — AgentForge skill refresh

## Repo
`/Users/chenry/Dropbox/Projects/AgentForge`

## Mandatory reading (before editing anything)
1. **Audit findings:** `/Users/chenry/Dropbox/Projects/ResearchLibrary/agent-io/research/2026-05-06-ai-platform-skill-audit.md`
2. **Canonical conventions:** `/Users/chenry/Dropbox/Projects/ClaudeCommands/agent-io/plans/skill-conventions-2026-05-09.md`

Both files are required. Skill content must conform to the conventions spec.

## Files to refresh
1. `agent-io/skills/ai-forge.md` (308 lines, verdict NEEDS REFRESH)
2. `agent-io/skills/worker.md` (725 lines, verdict MINOR ISSUES)

## Required changes — ai-forge.md

This skill currently has no frontmatter and uses pre-machine-scoping queue paths.

1. **Add frontmatter** per conventions §1. The file currently starts with `# Command: ai-forge`. Use:
   ```yaml
   ---
   name: AI Forge
   description: <one-sentence canonical description, under 100 chars>
   scope: repo:AgentForge
   ---
   ```
2. **Fix `QUEUE_ROOT` constant (line ~31-37)** — currently `~/Dropbox/Projects/AgentForge/state/workers/queue` (flat). Replace with the machine-scoped layout: `~/Dropbox/Projects/AgentForge/state/workers/{machine}/queue/{inbox,processing,outbox,continuation,control,archive}`. Verify with `ls /Users/chenry/Dropbox/Projects/AgentForge/state/workers/primary-laptop/queue/`. The skill must show how to derive `{machine}` (operator picks; default to `$(hostname-short)` or similar). Reference `ai-forge-ops.md` line ~14-17 for the correct shape.
3. **Queue Directories section (line ~270-279)** — same fix; replace flat layout with machine-scoped.
4. **Lifecycle diagram (line ~247-258)** — add `STALE` state. Per commit `1637613 test: include STALE in terminal and retryable state sets`.
5. **Context-dir path (line ~215)** — currently references `.claude/commands/ai-forge/context/queue-debugging.md`. Fix to `agent-io/skills/ai-forge/context/queue-debugging.md`. Per conventions §4, also add an explicit Knowledge Loading entry pointing at this file.
6. **Add coverage** for missing operations:
   - `agentforge cancel <task-id>` (commit `115e81f`).
   - `agentforge submit --replaces TASK_ID …` flag (commit `3818aee`, atomic cancel-and-resubmit).
   - launchd/systemd auto-restart templates (commit `7cf6f38`).

## Required changes — worker.md

This skill is large (725 lines) and mostly correct. Two specific path fixes:

1. **Smoke test path (line ~631)** — currently `cat ~/Dropbox/Projects/AgentForge/state/workers/workers/worker-1/sidecar.pid` (legacy flat path with double `workers`). Fix to `state/workers/${MACHINE}/workers/${WORKER_ID}/sidecar.pid` to match the machine-scoped convention used elsewhere in the file (line ~161).
2. **Smoke test (line ~696)** — same fix; check the file for any other instances of the legacy flat path and correct them.

Otherwise leave content alone — it's been hardened with hard-won failure modes that should be preserved.

## Apply to BOTH files (conventions compliance pass)

Per `skill-conventions-2026-05-09.md`:
- Frontmatter must conform to §1.
- `scope: repo:AgentForge` for both.
- `$ARGUMENTS` placeholder, where present, must use canonical block per §3 (`## User Request\n\n$ARGUMENTS`). Audit observed inconsistency here — fix.
- `ai-forge.md`'s `context/queue-debugging.md` MUST be explicitly referenced in Knowledge Loading per §4.

## Verification (must pass before declaring done)

```bash
cd /Users/chenry/Dropbox/Projects/AgentForge
python3 -m claude_skills.cli inventory --check
python3 -m claude_skills.cli sync primary-laptop --dry-run

# Verify the queue path actually exists post-fix:
ls /Users/chenry/Dropbox/Projects/AgentForge/state/workers/primary-laptop/queue/
```

All three must succeed.

## Out of scope
- Tooling changes to `agentforge` CLI.
- The `state/forge_last_snapshot.json` Dropbox-conflicted-copy cleanup (separate state-hygiene pass).
- Renaming files.

## Deliverables
- Two refreshed skill files.
- Logical commits per skill or one combined commit, your call.
- Verification command output captured in commit message or PR body.
