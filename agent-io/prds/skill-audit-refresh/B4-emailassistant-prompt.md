# B4 — EmailAssistant skill refresh

## Repo
`/Users/chenry/Dropbox/Projects/EmailAssistant`

## Mandatory reading (before editing anything)
1. **Audit findings:** `/Users/chenry/Dropbox/Projects/ResearchLibrary/agent-io/research/2026-05-06-ai-platform-skill-audit.md`
2. **Canonical conventions:** `/Users/chenry/Dropbox/Projects/ClaudeCommands/agent-io/plans/skill-conventions-2026-05-09.md`

Both files are required. Skill content must conform to the conventions spec.

## Files to refresh
1. `agent-io/skills/emailassistant-expert.md` (194 lines, verdict MINOR ISSUES — but ~50% of code surface is invisible)
2. `agent-io/skills/emailassistant-ops.md` (286 lines, verdict OK)

## Required changes — emailassistant-expert.md

The skill currently documents a Gmail-only single-pipeline view. Real EmailAssistant is multi-backend (Gmail + Outlook) with a Calendar pipeline. Verify file existence with `ls /Users/chenry/Dropbox/Projects/EmailAssistant/` before writing — do not invent file names.

1. **Backends section** — currently lists only `backends/base.py` and `backends/gmail_api.py`. Add:
   - `backends/outlook_applescript.py` — Outlook backend via AppleScript bridge.
   - `outlook_client.py` — Outlook client wrapper.
   - `backend_factory.py` — backend selection logic.
2. **Calendar pipeline** — entirely missing. Add a section covering:
   - `calendar_main.py` — calendar pipeline entry point.
   - `outlook_calendar.py` — Outlook calendar integration.
   - `calendar_dump.py` — calendar export utility.
3. **CLI** — note that there are now two parallel CLIs: legacy `main.py` (argparse) and `cli.py` (click-based, added in commit `9d5ed35`). State when to use each.
4. **Architecture diagram (line ~44-96)** — currently single-pipeline Gmail-only. Update to show Gmail + Outlook + Calendar as parallel pipelines feeding the shared job queue.
5. **Knowledge Loading section** — add explicit reference to the context file: `agent-io/skills/emailassistant-expert/context/architecture.md`. Per conventions §4.
6. **Cron infrastructure** — briefly mention `gmail_cron.sh`, `email_cron.sh`, `cron_setup.sh`, `setup_backfill_cron.sh`, `backfill.sh` in an Operations subsection (or defer to `emailassistant-ops` and just point at it).
7. **Encryption** — `decrypt_job.py` and `encryption.py` interplay should be mentioned briefly if it isn't already.

## Required changes — emailassistant-ops.md

1. **Add a section noting `cli.py` (click-based)** as the modern alternative to `main.py` argparse. Cover:
   - When to use which (`cli.py` for new operational tasks; `main.py` retained for legacy cron paths).
   - At least 2-3 example invocations from `cli.py`.
   - Verify with `python3 cli.py --help` before writing.
2. Otherwise leave content alone — verdict was OK.

## Apply to BOTH files (conventions compliance pass)

Per `skill-conventions-2026-05-09.md`:
- Frontmatter must conform to §1.
- `scope: repo:EmailAssistant` for both.
- `$ARGUMENTS` placeholder, where present, must use canonical block per §3.
- `emailassistant-expert.md`'s context dir file MUST be explicitly referenced per §4.
- Section ordering for `emailassistant-expert.md` must match §5.

## Verification (must pass before declaring done)

```bash
cd /Users/chenry/Dropbox/Projects/EmailAssistant
python3 -m claude_skills.cli inventory --check
python3 -m claude_skills.cli sync primary-laptop --dry-run

# Verify referenced files actually exist:
ls outlook_calendar.py outlook_client.py outlook_applescript.py calendar_main.py cli.py 2>&1
```

The third command should print all five file paths without "No such file" errors.

## Out of scope
- Source code changes (this is a docs-only refresh).
- Outlook AppleScript debugging.
- Renaming files.

## Deliverables
- Two refreshed skill files.
- Logical commits per skill or one combined commit, your call.
- Verification command output captured in commit message or PR body.
