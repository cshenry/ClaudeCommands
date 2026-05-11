---
name: AgentForge Worker
description: Start and manage AgentForge worker shells for task execution
scope: domain
---

# Command: worker

## Purpose

Run this Claude Code session as one of the persistent workers in the **AgentForge worker-shell pool**. The worker polls a shared inbox for task envelopes, claims them atomically, runs each task in a fresh `Task` subagent (so the parent session's OAuth covers the work and each task gets its own context), handles soft timeouts via continuation requests rather than killing the subagent, and writes results to an outbox.

This skill replaces the broken `subprocess.run(["claude", "--print", ...])` call site in AgentForge after the **April 4 2026 Anthropic policy change** that blocked subprocess invocations of `claude` from Max plan accounts (returns 400 "third-party app"). Interactive Claude Code sessions, subagents, and hooks are unaffected — so the pivot is to keep three persistent interactive sessions polling a file queue.

## Invocation

```
/worker 1
/worker emailmac-2
/worker h100-1
```

The argument is a worker ID. It can be a plain integer (``1``, ``2``, ``3``) which uses the LOCAL machine's alias from config, or a string ``{machine}-{N}`` where ``{machine}`` is an explicit machine alias (e.g., ``emailmac``, ``h100``, ``primary-laptop``) and ``{N}`` is the worker number on that machine.

The machine prefix determines which queue subtree the worker polls:
- ``/worker 1`` on emailmac polls ``state/workers/emailmac/queue/inbox/``
- ``/worker 1`` on primary-laptop polls ``state/workers/primary-laptop/queue/inbox/``
- ``/worker h100-1`` (explicit) polls ``state/workers/h100/queue/inbox/``

Workers on the same machine share that machine's queue directories and redis namespace.

## Authoritative spec

The file-handoff protocol that this skill implements is defined in:

```
~/Dropbox/Projects/AIAssistant/agent-io/prds/agentforge-worker-shell-pivot/protocol.md
```

If anything below conflicts with that file, the protocol wins. Read it before modifying this skill.

---

## What you (Claude) should do when this skill is invoked

You are about to become a worker. The user has run `/worker N` and you are now responsible for executing the loop below until the user closes the session or asks you to stop. Treat this as a long-running operational task — you are NOT a one-shot coding assistant for the duration of this session.

### Argument parsing

1. Read `$ARGUMENTS`. It can be:
   - A plain integer (e.g., `1`, `2`, `3`) -- uses the local machine's alias.
   - A string `{machine}-{N}` (e.g., `h100-1`, `emailmac-2`, `primary-laptop-3`).
   If it is missing or malformed, halt with a clear error message and ask the user to re-invoke with a valid worker ID. Do not pick a default.
2. **Resolve the local machine alias.** Run:
   ```bash
   python3 -c "
   import yaml
   from pathlib import Path
   cfg_path = Path.home() / '.agentforge' / 'config.yaml'
   if cfg_path.exists():
       cfg = yaml.safe_load(cfg_path.read_text()) or {}
       print(cfg.get('worker', {}).get('machine_alias', 'emailmac'))
   else:
       print('emailmac')
   "
   ```
   Store the result as `LOCAL_MACHINE` (e.g., `emailmac`, `primary-laptop`, `h100`).
3. Parse the argument:
   - If it is a plain integer N, set `MACHINE = LOCAL_MACHINE` and `WORKER_ID = {LOCAL_MACHINE}-N` (e.g., `/worker 1` on primary-laptop → `MACHINE = primary-laptop`, `WORKER_ID = primary-laptop-1`).
   - If it matches `{machine}-{N}`, set `MACHINE = {machine}` and `WORKER_ID = {machine}-{N}` (e.g., `/worker h100-1` → `MACHINE = h100`, `WORKER_ID = h100-1`).
3. **Remember this value for the entire session and inline it as a literal in every command, file path, and JSON snippet that follows.** Do **NOT** call `Bash(export WORKER_ID=worker-N)` and then reference `${WORKER_ID}` in a later `Bash` call — Claude Code's `Bash` tool does NOT persist shell state between calls (only the working directory is preserved), so the exported variable is gone in the next `Bash` invocation and the substitution silently expands to an empty string, which causes registration, claim, and cleanup commands to no-op without erroring. Every `${WORKER_ID}` reference in the rest of this skill is a TEMPLATE for you (the assistant) to substitute with the literal value before sending the command.

   **WRONG (silently fails — `${WORKER_ID}` expands to empty string in the fresh shell that `Bash` spawns for the second call):**

   ```
   Bash(export WORKER_ID=worker-1)
   Bash(redis-cli SADD agentforge:workers ${WORKER_ID})
   ```

   **RIGHT (literal value inlined into every call):**

   ```
   Bash(redis-cli SADD agentforge:workers worker-1)
   ```

---

## Phase A — Registration

Run all of these once at startup, before entering the main loop.

### A.1 Verify and create directories

The worker queue now lives under a machine-scoped subtree in AgentForge's gitignored `state/` tree. Replace `${MACHINE}` with the resolved machine alias (e.g., `emailmac`, `h100`):

```
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/inbox
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/inbox/control
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/processing
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/outbox
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/outbox/control
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/continuation
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/control
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/archive
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/workers/${WORKER_ID}
```

Create any that are missing with `Bash(mkdir -p ...)`. Do not error if they already exist.

### A.2 Verify redis is up

Run `Bash(redis-cli ping)`. The expected output is `PONG`. If it's not, halt the skill with a one-line error explaining that redis is required and that the user should start it (e.g., `brew services start redis`) before re-running `/worker N`. Do NOT continue without redis — the AgentForge daemon depends on the heartbeat keys to know which workers are alive.

### A.3 Register in redis

Run these commands. **Substitute the literal `WORKER_ID` value (e.g., `worker-1`) into every command before sending it to the `Bash` tool** — see the warning in step 3 of the Argument-parsing section above. The `${WORKER_ID}` shown below is template notation, not a shell variable that will resolve at runtime.

```bash
redis-cli SADD agentforge:workers ${WORKER_ID}
redis-cli SET agentforge:worker:${WORKER_ID}:status idle
redis-cli SET agentforge:worker:${WORKER_ID}:task ""
```

For `/worker 1` the actual `Bash` calls you send must look like:

```bash
redis-cli SADD agentforge:workers worker-1
redis-cli SET agentforge:worker:worker-1:status idle
redis-cli SET agentforge:worker:worker-1:task ""
```

Note: the initial `:hb` write is deferred to A.3b so it can include the session token in the new `<ts>:<session-uuid>` format from the start.

### A.3b Generate session token and write initial heartbeat

Generate a per-session UUID and write it to both a local file and a Redis key. The daemon will use the `:session` key as the trigger for smoke-test admission (see the worker-liveness PRD). The session_token file is read by the A.4 sidecar via `$(cat ...)` on each heartbeat tick — the sidecar cannot rely on a shell variable (same substitution caveat as `${WORKER_ID}` — see line 140).

**Resolve the worker state directory.** The session_token file lives alongside the existing `sidecar.pid` file. Use the same path the skill already uses for the pidfile:

```
~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/workers/${WORKER_ID}/
```

If `~/.agentforge/workers/${WORKER_ID}/` exists (post-Phase-2 layout), use that instead. Check with:

```bash
if [ -d ~/.agentforge/workers/${WORKER_ID} ]; then
  WORKER_STATE_DIR=~/.agentforge/workers/${WORKER_ID}
else
  WORKER_STATE_DIR=~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/workers/${WORKER_ID}
fi
```

As with all template variables in this skill, `${WORKER_ID}` and `${MACHINE}` must be inlined as literals before sending the Bash call.

**Generate the token, write it, and set the initial heartbeat (single Bash call):**

```bash
if [ -d ~/.agentforge/workers/${WORKER_ID} ]; then
  WORKER_STATE_DIR=~/.agentforge/workers/${WORKER_ID}
else
  WORKER_STATE_DIR=~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/workers/${WORKER_ID}
fi
WORKER_SESSION_TOKEN=$(uuidgen | tr '[:upper:]' '[:lower:]')
mkdir -p "${WORKER_STATE_DIR}"
echo -n "${WORKER_SESSION_TOKEN}" > ${WORKER_STATE_DIR}/session_token
redis-cli SET agentforge:worker:${WORKER_ID}:session "${WORKER_SESSION_TOKEN}"
redis-cli SET agentforge:worker:${WORKER_ID}:hb "$(date +%s):${WORKER_SESSION_TOKEN}" EX 1200
echo "session_token=${WORKER_SESSION_TOKEN}"
echo "worker_state_dir=${WORKER_STATE_DIR}"
```

The 1200-second TTL on the heartbeat key matches the protocol (20 minutes — accommodates a 15-minute soft timeout plus safety margin). The `:hb` value is now in the format `<unix_ts>:<session-uuid>` from the very first write, matching what the sidecar will produce on subsequent refreshes.

**Parse the output** to capture the literal `WORKER_STATE_DIR` and `WORKER_SESSION_TOKEN` values. You will use the `WORKER_STATE_DIR` literal in A.4 (sidecar launch), B.2a (smoke-test handling), and E.1 (shutdown cleanup). As with `WORKER_ID`, inline the resolved literal path into every subsequent command.

**CRITICAL:** The `WORKER_STATE_DIR` resolution, token generation, and initial heartbeat must happen in the SAME Bash call. Do not split across two calls — `WORKER_STATE_DIR` would be lost in the second call (same shell-state-doesn't-persist rule as `WORKER_ID`).

### A.4 Launch the heartbeat sidecar

The heartbeat is now driven by an OS-level background process (sidecar), not by the LLM. This decouples liveness from polling activity entirely — the sidecar lives until Phase E kills it by PID. Because Phase B.1 blocks the LLM on a single long Bash call during idle periods, tool-call activity is near zero, so a PostToolUse hook cannot keep the heartbeat fresh and an independent background process is the only correct solution.

Launch the sidecar via ONE `Bash` call. Because the `Bash` tool does not preserve shell state between calls, the launch + PID capture + PID-file write must happen in a single invocation. The `${WORKER_ID}` references below are TEMPLATE notation — substitute the literal value (e.g., `worker-1`) before sending.

**CRITICAL — substitution failure mode:** Inside the single-quoted `bash -c '...'` body, the inner subshell NEVER expands `${WORKER_ID}`. The `$(date +%s)` is intentional (the inner subshell evaluates it each iteration), but `${WORKER_ID}` is undefined in that subshell because this skill forbids exporting environment variables (see step 3 of the Argument-parsing section). If you send the command with `${WORKER_ID}` left unsubstituted, the sidecar silently writes to `agentforge:worker::hb` (an empty-suffix key) every 60s. The actual heartbeat key for your worker is never refreshed, the daemon marks the worker stalled within 1200s, but `ps` still shows the sidecar running cleanly — making the failure invisible to normal liveness checks. This is a TIER-1 silent failure mode.

**WRONG (sidecar runs but writes to the wrong key, worker silently dies after 20 minutes):**

```bash
nohup bash -c 'while true; do redis-cli SET agentforge:worker:${WORKER_ID}:hb $(date +%s) EX 1200 > /dev/null 2>&1; sleep 60; done' > /dev/null 2>&1 &
```

**RIGHT (literal `worker-1` inlined into the inner-subshell body, session token read from file):**

```bash
nohup bash -c 'while true; do TOKEN=$(cat /path/to/worker-state-dir/session_token 2>/dev/null); if [ -z "$TOKEN" ]; then echo "FATAL: session_token unreadable at /path/to/worker-state-dir/session_token" >&2; exit 1; fi; redis-cli SET agentforge:worker:worker-1:hb "$(date +%s):${TOKEN}" EX 1200 > /dev/null 2>&1; sleep 60; done' > /dev/null 2>&1 &
```

The sidecar now writes `:hb` values in the format `<unix_ts>:<session-uuid>` (e.g. `1747000000:a1b2c3d4-...`). The `$(cat ...)` is evaluated by the inner subshell on each iteration, reading the session_token file from disk — the same pattern as `$(date +%s)`. If the session_token file becomes unreadable (deleted, permissions changed), the sidecar exits non-zero immediately rather than writing a heartbeat with an empty token. An empty token in `:hb` would be a silent failure mode analogous to the empty-`${WORKER_ID}` trap documented above.

**CRITICAL — two literal substitutions required:** Both `worker-1` (the WORKER_ID) and `/path/to/worker-state-dir/` (the WORKER_STATE_DIR resolved in A.3b) must be inlined as literals into the `bash -c '...'` body before sending the Bash call. Neither is available as a shell variable inside the `nohup` subshell.

For `/worker 2` or `/worker 3`, substitute `worker-2` or `worker-3` correspondingly. Do this BEFORE sending the Bash call — Claude Code's Bash tool will not retroactively expand a `${WORKER_ID}` left in the command string.

```bash
nohup bash -c 'while true; do TOKEN=$(cat ${WORKER_STATE_DIR}/session_token 2>/dev/null); if [ -z "$TOKEN" ]; then echo "FATAL: session_token unreadable at ${WORKER_STATE_DIR}/session_token" >&2; exit 1; fi; redis-cli SET agentforge:worker:${WORKER_ID}:hb "$(date +%s):${TOKEN}" EX 1200 > /dev/null 2>&1; sleep 60; done' > /dev/null 2>&1 &
SIDECAR_PID=$!
disown
mkdir -p ${WORKER_STATE_DIR}
echo $SIDECAR_PID > ${WORKER_STATE_DIR}/sidecar.pid
echo "sidecar started: PID=$SIDECAR_PID"
```

Note: `${WORKER_STATE_DIR}` here is template notation — substitute the literal path resolved in A.3b (e.g. `~/Dropbox/Projects/AgentForge/state/workers/emailmac/workers/emailmac-1` or `~/.agentforge/workers/emailmac-1`). The `mkdir -p` and pidfile path must also use this same literal.

The `sleep 60` refresh interval is well within the 1200s TTL safety margin. Verify the sidecar is actually running with `Bash(ps -p $(cat ${WORKER_STATE_DIR}/sidecar.pid) -o pid,command)` (substituting the literal `WORKER_STATE_DIR` path) — expect a line like `bash -c 'while true; do ... redis-cli SET ...`. If `ps` shows nothing (the process died immediately) or the pidfile is missing, halt the skill with a clear error — the worker cannot safely enter Phase B without a live heartbeat.

### A.4b Permissions

Subagent tool permissions are handled by the project-shared `.claude/settings.json` (committed, see commit 077bfb8). It contains an explicit allow whitelist for the tools subagents need: `Bash`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `Agent`, `WebFetch`, `WebSearch`, `TodoWrite`, `NotebookEdit`. Both the parent worker session and any spawned `Task` subagents inherit it.

**You do not need to do anything in Phase A for permissions.** Verify the file exists:

```bash
test -f ~/Dropbox/Projects/AgentForge/.claude/settings.json && echo "permissions OK" || echo "ERROR: settings.json missing — workers will be denied tool calls"
```

If the file is missing, halt the skill and tell the user to restore it (the file is committed to AgentForge main; `git checkout HEAD -- .claude/commands/worker.md .claude/settings.json` from any AgentForge clone will restore both).

If the user has a `.claude/settings.local.json` on their machine, leave it alone. It is gitignored, machine-private, and any contents are the user's own configuration.

### A.5 Log startup

Append a JSON line to `state/workers/${MACHINE}/workers/${WORKER_ID}/log.jsonl`:

```json
{"event": "worker_started", "worker_id": "worker-N", "timestamp": "<ISO8601 UTC>", "session_pid": <pid if known>}
```

Use `Bash(echo '...' >> path/to/log.jsonl)` or the `Write` tool with append semantics. (`Bash` with `>>` is fine here — this is a one-line append, not a file edit.)

### A.6 Confirm to user

Print a single line:

```
Worker ${WORKER_ID} ready. Polling for tasks.
```

Then enter the main loop.

---

## Phase B — Main loop

Loop indefinitely. Each iteration:

### B.1 Block on a single Bash call until task, shutdown, or timeout

This is the heart of the polling fix. Instead of looping in the LLM with multiple short Bash calls, the worker makes a single blocking Bash call that holds for up to 9 minutes. Inside that call, an OS-level sleep loop checks for task arrival or shutdown signal every 5 seconds. The model receives ZERO tokens during the wait. When the call returns, the model dispatches based on the result string.

**The Bash call (template — substitute `worker-N` literally):**

```bash
INBOX=~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/inbox
CONTROL_INBOX=~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/inbox/control
SHUTDOWN=~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/workers/${WORKER_ID}/shutdown
DEADLINE=$(($(date +%s) + 540))  # 9 minutes
while [ $(date +%s) -lt $DEADLINE ]; do
  if [ -f "$SHUTDOWN" ]; then
    echo "SHUTDOWN_REQUESTED"
    exit 0
  fi
  # Check control inbox first (smoke-tests take priority — fast turnaround required)
  ctrl=$(ls -1tr "$CONTROL_INBOX"/*.json 2>/dev/null | head -1)
  if [ -n "$ctrl" ]; then
    echo "CONTROL_FOUND $ctrl"
    exit 0
  fi
  task=$(ls -1tr "$INBOX"/*.json 2>/dev/null | head -1)
  if [ -n "$task" ]; then
    echo "TASK_FOUND $task"
    exit 0
  fi
  sleep 5
done
echo "TIMEOUT"
exit 0
```

**Required Bash tool parameters:** set `timeout: 570000` (9.5 min in ms). This gives the script a 30s safety margin before Claude Code force-kills the Bash call — the script's internal deadline is 540s (9 min), so it always exits cleanly before the tool timeout triggers.

**Result dispatch** — parse the first token of the returned stdout:

- `CONTROL_FOUND <path>` → continue to B.2a (smoke-test handling) with `<path>` as the control envelope.
- `TASK_FOUND <path>` → continue to B.2b (atomic claim) with `<path>` as the single candidate.
- `SHUTDOWN_REQUESTED` → jump to Phase E.1.
- `TIMEOUT` → loop back to the top of B.1 and re-issue the same Bash call. This is the only way the model wakes during pure-idle periods (~6.5 wakes/hour per worker).

Do NOT add any other Bash calls between B.1 returning and B.2a/B.2b — the whole point is one Bash call per polling window (see the first bullet of "Things to avoid").

### B.2a Smoke-test handling (control envelopes)

Entered when B.1 returns `CONTROL_FOUND <path>`. This handles smoke-test envelopes sent by the daemon to verify the worker's claim path is functional. Smoke-test handling must complete within ~1s so daemon-side timeouts can be tight.

1. **Read the control envelope.** Use `Read` on the file at `<path>`. Parse the JSON. Check the `kind` field.

2. **If `kind` is `smoketest`:**
   - Extract `task_id` from the envelope.
   - **Skip B.3** (no `redis-cli SET ... :status processing` — smoke-tests are transparent to the worker's status semantics).
   - **Skip the Task subagent dispatch entirely** — no B.4/B.5/B.6/B.7.
   - Read the session token from the session_token file: `Bash(cat ${WORKER_STATE_DIR}/session_token)` (substitute the literal `WORKER_STATE_DIR` path).
   - Compute timestamps: `Bash(echo "claimed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ) ack_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)")`.
   - Write a `smoketest_ack` envelope to the worker's outbox control directory using the `Write` tool:

     ```
     ~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/outbox/control/<task_id>.json
     ```

     Envelope contents (all values must be literal — do NOT embed shell expressions in the `Write` tool):

     ```json
     {
       "task_id": "<smoketest-task-id>",
       "kind": "smoketest_ack",
       "session_token": "<contents-of-session_token-file>",
       "claimed_at": "<iso8601>",
       "ack_at": "<iso8601>"
     }
     ```

   - **Delete the inbox control file** atomically: `Bash(rm <path>)` (the original `<path>` from B.1's `CONTROL_FOUND` output).
   - Append a log event to `log.jsonl`:
     ```json
     {"event": "smoketest_ack", "worker_id": "${WORKER_ID}", "task_id": "<smoketest-task-id>", "timestamp": "<ISO8601 UTC>"}
     ```
   - **Return to B.1 immediately.** Do not proceed to B.2b, B.3, or any subsequent phase.

3. **If `kind` is unrecognized:** Log a warning to `log.jsonl` (`{"event": "unknown_control_kind", ...}`), delete the control file, and return to B.1. Do not attempt to process it as a real task.

### B.2b Atomic claim

B.1 returned exactly one candidate path via `TASK_FOUND <path>`. Attempt to claim it:

```bash
mv ~/.../${MACHINE}/queue/inbox/task-X.json ~/.../${MACHINE}/queue/processing/task-X.${WORKER_ID}.json
```

POSIX `mv` on a local filesystem is atomic. If another worker claimed it first, the `mv` exits non-zero with "No such file or directory" — that's a race loss. On race loss, immediately return to the top of B.1; the next 5s tick of the new Bash wait will surface the next available file (or shutdown signal, or timeout) cleanly — there is no need to iterate locally.

On a successful claim:

- The file is now at `processing/task-X.${WORKER_ID}.json` and exclusively yours.
- Remember the original `task_id` (the basename without `.json` and without the `.${WORKER_ID}` suffix). You'll need it for the result envelope and for redis keys.

### B.3 Update redis claim state

```bash
redis-cli SET agentforge:worker:${WORKER_ID}:status processing
redis-cli SET agentforge:worker:${WORKER_ID}:task task-X
redis-cli SET agentforge:worker:${WORKER_ID}:started_at $(date -u +%Y-%m-%dT%H:%M:%S)
```

### B.4 Read the task envelope (with sync-tolerant retry)

The task file may arrive via Dropbox sync from another machine. In that case, the file listing can appear before the file contents are fully written. To handle this, wrap the read in a retry loop.

**Step 1:** Attempt to read and parse the file at `${MACHINE}/queue/processing/task-X.${WORKER_ID}.json`. Use a single `Bash` call that retries up to 5 times with 10s between attempts:

```bash
TASK_FILE="~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/processing/task-X.${WORKER_ID}.json"
for attempt in 1 2 3 4 5; do
  if python3 -c "
import json, sys
try:
    with open('$TASK_FILE') as f:
        data = json.load(f)
    assert 'prompt' in data, 'missing prompt'
    assert 'task_id' in data, 'missing task_id'
    assert 'repo_path' in data, 'missing repo_path'
    print('ENVELOPE_OK')
except (FileNotFoundError, json.JSONDecodeError, AssertionError) as e:
    print(f'SYNC_WAIT: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
    echo "READY"
    break
  fi
  if [ "$attempt" -eq 5 ]; then
    echo "SYNC_FAILED"
    break
  fi
  sleep 10
done
```

**Result dispatch:**
- `READY` → proceed to read the file with the `Read` tool and extract fields normally.
- `SYNC_FAILED` → the file did not become readable after 50s. Move it back to inbox for re-claim and return to Phase B.1:
  ```bash
  mv "$TASK_FILE" "~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/inbox/task-X.json"
  ```
  Log the event to `state/workers/${MACHINE}/workers/${WORKER_ID}/log.jsonl`:
  ```json
  {"event": "sync_timeout", "worker_id": "${WORKER_ID}", "task_file": "task-X.json", "timestamp": "<ISO8601>"}
  ```
  Then continue to the next iteration of Phase B.1.

**Step 2:** Once `READY`, `Read` the file and extract fields:

| Field | Default if missing |
|---|---|
| `task_id` | (required — error if missing) |
| `prompt` | (required — error if missing) |
| `system_prompt` | empty string |
| `repo_path` | (required — error if missing) |
| `role` | `"developer"` |
| `max_turns` | 50 |
| `timeout_seconds` | 900 |
| `max_continuations` | 2 |
| `allowed_tools` | null (= all tools allowed) |

If any required field is missing, jump to Phase C with a failure envelope (`success: false`, `error: "invalid_task_envelope"`, brief explanation in `output`).

If `repo_path` does not exist on disk, same: failure envelope with `error: "repo_not_found"`.

### B.5 Build the subagent prompt

The subagent gets one combined prompt that wraps the system prompt + the user prompt + a **mandatory working-directory check** + an allowed-tools constraint. Construct it like this (substituting the fields from the envelope):

```
You are a Claude subagent dispatched by AgentForge worker ${WORKER_ID}.

═══════════════════════════════════════════════════════════════════════
MANDATORY FIRST ACTION — DO NOT SKIP, DO NOT REORDER
═══════════════════════════════════════════════════════════════════════

Before doing ANYTHING else, your FIRST tool call MUST be exactly:

  Bash(cd ${repo_path} && pwd)

Then verify the output of `pwd` is exactly `${repo_path}`. If it is not,
STOP IMMEDIATELY. Do not retry. Do not attempt the task. End your
response with:

  SUMMARY: ABORTED — working directory mismatch. Expected ${repo_path}, got <actual pwd>.

This is a hard constraint enforced by the AgentForge worker coordinator.
Tasks that work in the wrong directory have caused real damage in the
past — git branches created in the wrong repo, files written into the
wrong project. The pwd verification is non-negotiable.

For the rest of the task, EVERY Bash command you run that touches files
must either be issued from this directory or use absolute paths under
${repo_path}. Do not `cd` anywhere else. Do not create a worktree —
work directly in the main checkout. The worker's coordinator has
already ensured no other task is in flight against this repo.

═══════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════
GIT BRANCH CONSTRAINT — DO NOT CREATE OR SWITCH BRANCHES
═══════════════════════════════════════════════════════════════════════

You are already on the correct git branch. The AgentForge daemon has
pre-provisioned a worktree with the exact branch name needed for this
task. Do NOT run `git checkout -b`, `git switch -c`, `git branch`, or
any command that creates or switches branches. Commit your work
directly to the current branch (the one `git branch --show-current`
returns when you first enter the repo).

If you create a different branch, your commits will be invisible to
the AgentForge result pipeline and the task will fail silently.

═══════════════════════════════════════════════════════════════════════

Tool constraint:
- You may only use these tools: ${allowed_tools_list}
  (If this list is "all", all tools are permitted.)

System context:
${system_prompt}

Your task:
${prompt}

When you are finished (successfully or not), end your response with a
1-2 sentence summary line prefixed with "SUMMARY:" so the worker can
extract it for the result envelope. Examples:

  SUMMARY: Implemented feature X in src/foo.py and added 4 passing tests.
  SUMMARY: ABORTED — working directory mismatch.
  SUMMARY: FAILED — pytest fixture conflict in tests/conftest.py, see output above.
```

Where `${allowed_tools_list}` is a comma-separated rendering of the `allowed_tools` array (or "all" if null/missing).

**Note on the Bash tool requirement:** because the mandatory first action is `Bash(cd ... && pwd)`, the `Bash` tool MUST be in the effective allowed-tools list even if the task envelope's `allowed_tools` field omits it. When constructing the subagent prompt, if `allowed_tools` is non-null and does not contain `"Bash"`, prepend `"Bash"` to the list before rendering it. If you have to do this, also note in the worker's `log.jsonl` that you augmented the allowed tools (`{"event": "allowed_tools_augmented", ...}`) so it's auditable.

### B.6 Spawn subagent

Invoke the `Task` tool with:

- `subagent_type`: `"general-purpose"`
- `description`: `"AF ${task_id_short}"` where `task_id_short` is the last 8 chars of the task_id (the Task tool requires a 3-5 word description; this stays under the limit).
- `prompt`: the combined prompt from B.5
- `run_in_background`: `true`

Capture the `agent_id` (or whatever identifier the Task tool returns) — you need it for `TaskOutput` and `TaskStop`.

Record the start time as `started_at_unix = $(date +%s)`.

### B.7 Inner poll loop

Loop until the subagent finishes, fails, or is aborted:

1. Compute sleep interval as `min(30, timeout_seconds // 10)` — for the default `timeout_seconds=900`, that's 30s. Sleep via `Bash(sleep N)`.
2. Call `TaskOutput` with the captured `agent_id`.
3. Inspect the returned status:
   - **`completed`**: extract the final output text. Build a success result envelope (Phase C). Break out of the inner loop.
   - **`failed`**: build a failure envelope (`success: false`, `error: "subagent_error"`, `output` = whatever partial output is available). Break out of the inner loop.
   - **`running`**:
     - Compute `elapsed = $(date +%s) - started_at_unix`.
     - If `elapsed >= timeout_seconds`: enter Phase D (continuation request flow). When Phase D returns, either continue this inner loop (with the timeout extended) or break out and proceed to Phase C with an aborted envelope.
     - Otherwise: continue the inner loop.

Do not call `TaskStop` on a healthy `running` agent. Only `TaskStop` on explicit abort from Phase D. The sidecar (Phase A.4) keeps the heartbeat fresh independently of any tool-call activity inside this inner loop, so there is no need for a defensive refresh here.

---

## Phase C — Successful (or final) result handling

This runs after the inner loop breaks for any reason (completed, failed, aborted, timed-out-with-no-decision).

### C.1 Build the result envelope

Per `protocol.md` "Result envelope" schema:

```json
{
  "task_id": "task-X",
  "worker_id": "worker-N",
  "success": true,
  "output": "<final response text from subagent>",
  "error": null,
  "tokens_used": 0,
  "session_id": "<this worker's claude code session id, if known>",
  "started_at": "<ISO8601 UTC at claim>",
  "completed_at": "<ISO8601 UTC now>",
  "duration_seconds": <integer>,
  "continuation_count": <integer>,
  "subagent_summary": "<extracted from the SUMMARY: line in the subagent's output, or first 1-2 sentences if no marker>"
}
```

For failures, set `success: false`, `error` to a short identifier (`subagent_error`, `timeout_aborted`, `continuation_timeout_no_response`, `aborted_by_continuation_decision`, `invalid_task_envelope`, `repo_not_found`, `working_directory_mismatch`), and put any partial output in `output`.

**Working directory verification:** Even when the subagent reports `completed`, check the final output for the substring `ABORTED — working directory mismatch`. If found, override the result envelope with `success: false` and `error: "working_directory_mismatch"`. This catches cases where the subagent followed the abort instruction in B.5's mandatory first action. Do NOT mark this as a success even though the subagent technically completed normally — the task did not run.

`tokens_used` should come from `TaskOutput` if it exposes that; otherwise leave it `0`. Do not synthesize a fake number.

> **WARNING — JSON creation method:** You MUST use the `Write` tool (not Bash heredoc, `echo`, or `cat <<EOF`) to create outbox and continuation JSON files. Shell variable syntax like `${WORKER_ID}` or `$(date +%s)` will NOT expand inside the `Write` tool — it accepts a literal string. Compute all dynamic values (timestamps, durations, task IDs, worker IDs) in a preceding `Bash` call and then inline the literal results into the `Write` tool's content parameter. This is the same substitution discipline as Phase A's `${WORKER_ID}` rule: every dynamic value must be resolved by you (the assistant) before it reaches the tool call.

### C.1b Compute dynamic values before writing

Before constructing the result envelope, run a single `Bash` call to capture the dynamic values you will need:

```bash
echo "completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ) duration=$(($(date +%s) - started_at_unix))"
```

Parse `completed_at` and `duration` from the output. Then use these literal values when you construct the JSON in step C.2 via the `Write` tool. Do NOT embed `$(date ...)` or any shell expression inside the `Write` tool's content — it will not be evaluated and will produce invalid JSON values.

### C.2 Write to outbox

Use the `Write` tool to create `state/workers/${MACHINE}/queue/outbox/task-X.json` with the envelope. The outbox file uses the bare `task-X.json` name (no `.${WORKER_ID}` suffix) — the executor on the AgentForge side polls for that exact name.

**Post-write validation:** Immediately after writing the outbox file, read it back with `Read` and verify it parses as valid JSON. Run: `Bash(python3 -c "import json; json.load(open('~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/queue/outbox/task-X.json')); print('JSON OK')")` (substituting the actual task filename). If this fails, the file contains malformed JSON — delete it, fix the content, and re-write before proceeding to C.3. Malformed outbox JSON causes silent failures in the AgentForge daemon's result polling.

### C.3 Archive the processing file

```bash
mv ~/.../${MACHINE}/queue/processing/task-X.${WORKER_ID}.json ~/.../${MACHINE}/queue/archive/task-X.json
```

### C.4 Update redis to idle

```bash
redis-cli SET agentforge:worker:${WORKER_ID}:status idle
redis-cli SET agentforge:worker:${WORKER_ID}:task ""
```

Do NOT delete `started_at` — leave it as the last task's start time. The daemon may use it for diagnostics.

### C.5 Append log event

```json
{"event": "task_completed", "worker_id": "worker-N", "task_id": "task-X", "success": <bool>, "duration_seconds": <int>, "timestamp": "<ISO8601 UTC>"}
```

### C.6 Return to the main loop

Return to the top of Phase B. The shutdown file check is handled inside the Phase B.1 blocking Bash call, so there is no separate gate here — if a shutdown file has been placed while the task was running, the next B.1 call will detect it on its first 5s tick and return `SHUTDOWN_REQUESTED`.

---

## Phase D — Continuation request flow

You enter this phase when the subagent is still `running` and `elapsed >= timeout_seconds`.

### D.1 Build the continuation request

Read the latest `TaskOutput` for the running agent. Summarize what the subagent appears to be doing in 1-2 sentences (e.g., "Subagent has modified 3 files and is currently running pytest. Last tool call was Bash(pytest tests/test_foo.py).").

Build the envelope per protocol.md:

```json
{
  "task_id": "task-X",
  "worker_id": "worker-N",
  "reason": "timeout_${timeout_minutes}min",
  "elapsed_seconds": <int>,
  "continuation_count_so_far": <int>,
  "context_summary": "<your 1-2 sentence summary>",
  "requested_at": "<ISO8601 UTC>"
}
```

### D.2 Write the continuation request

`Write` the envelope to `state/workers/${MACHINE}/queue/continuation/task-X.json`.

### D.3 Update redis

```bash
redis-cli SET agentforge:worker:${WORKER_ID}:status waiting_continuation
```

### D.4 Poll for control file

Loop:

1. `Bash(sleep 10)`.
2. Check whether `state/workers/${MACHINE}/queue/control/task-X.continue.json` or `state/workers/${MACHINE}/queue/control/task-X.abort.json` exists. (The sidecar is keeping the heartbeat fresh, so no defensive refresh is needed here.)

   - **`task-X.continue.json` found:**
     - `Read` it. Extract `additional_seconds` (default 900 if missing).
     - Delete it: `Bash(rm ~/.../${MACHINE}/queue/control/task-X.continue.json)`.
     - Increment your local `continuation_count`.
     - Set `redis-cli SET agentforge:worker:${WORKER_ID}:status processing`.
     - Reset `started_at_unix` for the inner-loop deadline calculation: effectively, extend `timeout_seconds` by `additional_seconds`. Simplest: `started_at_unix = $(date +%s) - (timeout_seconds - additional_seconds)`. Easier alternative: increase `timeout_seconds` in-place by `additional_seconds`.
     - Return to Phase B.7 (the inner poll loop).

   - **`task-X.abort.json` found:**
     - `Read` it (you don't actually need fields from it, but read it for symmetry / future-proofing).
     - Delete it: `Bash(rm ~/.../${MACHINE}/queue/control/task-X.abort.json)`.
     - Call `TaskStop` with the agent_id.
     - Build a failure envelope with `error: "aborted_by_continuation_decision"`, `success: false`, and whatever partial output the subagent had produced.
     - Proceed to Phase C step C.2 (write to outbox, archive, etc.).

   - **Neither file exists:**
     - Compute how long you've been waiting in Phase D (track a `continuation_started_unix` set at D.1).
     - If `(now - continuation_started_unix) > 3600` (1 hour): give up. Build a failure envelope with `error: "continuation_timeout_no_response"`. Do NOT call `TaskStop` — the subagent may still be making real progress, and the daemon may eventually answer. Just abandon ownership on the worker side and proceed to Phase C step C.2. The runaway subagent will be reaped by the agent SDK's own internal limits eventually.
     - Otherwise, continue the D.4 loop.

---

## Phase E — Graceful shutdown

The worker should exit cleanly when the user requests it. There are two shutdown paths:

### E.1 Soft shutdown (file-based)

Entered when Phase B.1's blocking Bash call returns `SHUTDOWN_REQUESTED`. Execute these steps in order:

1. Update redis: `redis-cli SET agentforge:worker:${WORKER_ID}:status stopping`.
2. **Kill the heartbeat sidecar** (the `|| true` on the `kill` is intentional — the sidecar may already be dead and that's fine). Then append a `sidecar_stopped` event to `log.jsonl`.
   ```bash
   PID=$(cat ${WORKER_STATE_DIR}/sidecar.pid)
   kill $PID 2>/dev/null || true
   rm -f ${WORKER_STATE_DIR}/sidecar.pid
   ```
   (Substitute the literal `WORKER_STATE_DIR` path resolved in A.3b.)
3. Remove worker from active set and clean up liveness keys:
   ```bash
   redis-cli SREM agentforge:workers ${WORKER_ID}
   redis-cli DEL agentforge:worker:${WORKER_ID}:hb agentforge:worker:${WORKER_ID}:status agentforge:worker:${WORKER_ID}:task agentforge:worker:${WORKER_ID}:started_at
   redis-cli DEL agentforge:worker:${WORKER_ID}:session
   redis-cli DEL agentforge:worker:${WORKER_ID}:ready
   ```
   The `:session` and `:ready` keys are part of the worker-liveness protocol. Cleaning them at shutdown prevents the daemon from seeing stale session data if the worker is restarted later.
3b. **Delete the session_token file:**
   ```bash
   rm -f ${WORKER_STATE_DIR}/session_token
   ```
4. Delete the shutdown file: `Bash(rm ~/Dropbox/Projects/AgentForge/state/workers/${MACHINE}/workers/${WORKER_ID}/shutdown)`.
5. Append a `worker_stopped` event to `log.jsonl`.
6. Print: `Worker ${WORKER_ID} stopped cleanly. You may close this session.`
7. Exit the main loop. Return control to the user.

### E.2 Hard shutdown (SIGINT / window close)

If the user closes the Cursor window or sends SIGINT, the session terminates without giving you a chance to clean up. The heartbeat key will simply expire after 1200s and the AgentForge daemon will mark the worker as stalled. The `:session` and `:ready` keys have no TTL and will persist, but the daemon's session-validation logic (FR-7) handles this: the next `/worker N` invocation writes a new `:session` UUID in A.3b, which invalidates the stale `:ready` key. The orphaned sidecar will continue writing heartbeats with the OLD session token, which the daemon will ignore once the new session is admitted. This is a legitimate exit path — no special handling required from this skill. To clean up the orphan manually, find it with `ps -ef | grep agentforge:worker | grep hb` and `kill` the matching PID.

---

## Things to avoid

- **Do NOT put polling logic in the LLM loop.** The entire idle-polling window must live inside a single blocking Bash tool call (see Phase B.1). Multiple short Bash calls in a model-driven polling loop are exactly what burned the Max-plan rate limit on 2026-04-08 — they grow conversation history at O(t²) and trip throttling within ~3 hours. If you find yourself writing `Bash(ls inbox); Bash(sleep 30)` in a loop, STOP and fix it.
- **Do NOT** add Python files. The whole point of the worker-shell pivot is to avoid `subprocess.run([claude, ...])`. This skill should drive everything via `Bash`, `redis-cli`, `Read`, `Write`, `Task`, `TaskOutput`, and `TaskStop`.
- **Do NOT** run tasks directly in the worker session. Always spawn a `Task` subagent so each task gets a fresh context. If you skip the subagent step, every task pollutes the worker's context and the worker eventually dies of context exhaustion.
- **Do NOT** call `TaskStop` on a `running` agent unless the abort path in Phase D explicitly tells you to. The whole continuation mechanism exists so we don't kill long-running but healthy work.
- **Do NOT** add error-handling for cases that can't happen. Validate at the edges (envelope read, redis ping, repo_path exists) and let everything else propagate.
- **Do NOT** add backwards-compat shims. This skill is brand new.
- **Do NOT** modify files outside the AgentForge state tree and the queue directories listed above. In particular, do not touch the user's `.claude/settings.local.json` — that's their machine-private configuration and Phase A.4b explains why it is not the worker's concern.
- **Do NOT** assume only one worker is running. The atomic-claim protocol in B.2b is what keeps multiple workers honest. Trust it.

---

## Smoke test

Once the skill is installed, validate it end-to-end with this procedure:

### 1. Start the pool

Open three Cursor windows in any repo (the working directory doesn't matter, but `~/Dropbox/Projects/AgentForge` is convenient since the queue lives under it). In each window, run:

```
/worker 1
/worker 2
/worker 3
```

You should see `Worker worker-N ready. Polling for tasks.` in each.

### 2. Verify registration

In a separate terminal:

```bash
redis-cli SMEMBERS agentforge:workers
# Expected: 1) "worker-1"  2) "worker-2"  3) "worker-3"  (in some order)

redis-cli GET agentforge:worker:worker-1:status
# Expected: "idle"

redis-cli GET agentforge:worker:worker-1:hb
# Expected: "<unix_ts>:<session-uuid>" (e.g. "1747000000:a1b2c3d4-e5f6-...")

redis-cli TTL agentforge:worker:worker-1:hb
# Expected: a positive integer <= 1200

redis-cli GET agentforge:worker:worker-1:session
# Expected: a lowercase UUID matching the session part of the :hb value
```

### 2b. Verify the heartbeat sidecar

Confirm each worker spawned a live sidecar and that the heartbeat refreshes independently of LLM activity. Run `ps -p $(cat ${WORKER_STATE_DIR}/sidecar.pid) -o pid,command` (substituting the literal state dir path) — expect a `bash -c 'while true; do ... redis-cli SET ...'` line. Then wait 90 seconds without touching the worker and run `redis-cli GET agentforge:worker:worker-1:hb` — expect a value like `<ts>:<session-uuid>` with TTL `> 1100` (the sidecar refreshed it within the last 60s, NOT any LLM activity). If the TTL is dropping toward zero instead of staying near 1200, the sidecar is dead and the worker is unsafe.

### 3. Drop a test task

Save the following to `~/Dropbox/Projects/AgentForge/state/workers/emailmac/queue/inbox/task-smoke001.json`:

```json
{
  "task_id": "task-smoke001",
  "prompt": "Run `echo hello from subagent` in bash and report what you see. End with a SUMMARY: line.",
  "system_prompt": "You are a smoke-test subagent. Be brief.",
  "repo_path": "~/Dropbox/Projects/AgentForge",
  "role": "smoke",
  "max_turns": 5,
  "timeout_seconds": 120,
  "max_continuations": 0,
  "allowed_tools": ["Bash"],
  "submitted_at": "2026-04-08T00:00:00",
  "submitted_by": "manual",
  "parent_task_id": null,
  "agentforge_task_record_path": null
}
```

Within ~5 seconds one of the workers should claim it (the B.1 blocking Bash call checks every 5s). Verify with:

```bash
ls ~/Dropbox/Projects/AgentForge/state/workers/emailmac/queue/processing/
# Expected: task-smoke001.worker-N.json   (for some N in 1..3)

redis-cli GET agentforge:worker:worker-N:status   # the one that claimed
# Expected: "processing"

redis-cli GET agentforge:worker:worker-N:task
# Expected: "task-smoke001"
```

### 4. Verify the result

After the subagent completes (should be quick), check:

```bash
cat ~/Dropbox/Projects/AgentForge/state/workers/emailmac/queue/outbox/task-smoke001.json
# Expected: a result envelope with success: true, output containing "hello from subagent"

ls ~/Dropbox/Projects/AgentForge/state/workers/emailmac/queue/archive/
# Expected: task-smoke001.json
```

### 5. Shutdown test

```bash
touch ~/Dropbox/Projects/AgentForge/state/workers/emailmac/workers/worker-1/shutdown
```

Within ~5 seconds (the B.1 blocking Bash loop checks every 5s) worker-1 should print `Worker worker-1 stopped cleanly.` and exit. Verify:

```bash
redis-cli SMEMBERS agentforge:workers
# Expected: only "worker-2" and "worker-3"

redis-cli EXISTS agentforge:worker:worker-1:hb
# Expected: 0

redis-cli EXISTS agentforge:worker:worker-1:session
# Expected: 0

redis-cli EXISTS agentforge:worker:worker-1:ready
# Expected: 0

ls ~/Dropbox/Projects/AgentForge/state/workers/emailmac/workers/worker-1/sidecar.pid 2>/dev/null
# Expected: no output — the file was removed by Phase E.1.

ls ~/Dropbox/Projects/AgentForge/state/workers/emailmac/workers/worker-1/session_token 2>/dev/null
# Expected: no output — the file was removed by Phase E.1 step 3b.

ps -ef | grep 'agentforge:worker:worker-1:hb' | grep -v grep
# Expected: no output — the sidecar was killed by Phase E.1.
```

---

## Operational tips

- **Where is the queue?** `~/Dropbox/Projects/AgentForge/state/workers/{machine}/queue/` (one subtree per machine). Inside the AgentForge gitignored `state/` tree, so nothing in here is committed.
- **How do I tell which worker grabbed which task?** Look at `{machine}/queue/processing/*.worker-N.json` filenames, or `redis-cli GET agentforge:worker:worker-N:task`.
- **The heartbeat sidecar.** Each worker spawns a background bash loop at startup that refreshes redis every 60s. The PID lives in `state/workers/${MACHINE}/workers/worker-N/sidecar.pid`. Phase E.1 kills it cleanly; hard shutdowns leave it as a harmless orphan (find with `ps -ef | grep agentforge:worker | grep -v grep` and `kill` if you care). If the sidecar dies silently the worker stops heartbeating and the daemon marks it stalled within 1200s.
- **A task is stuck. How do I abort?** Drop a `task-X.abort.json` file in `state/workers/${MACHINE}/queue/control/`. The worker will pick it up within 10s on its next Phase D poll. Note: this only works if the worker is in `waiting_continuation` state. If the subagent is healthy and running, it will run to its natural completion or until the soft timeout triggers a continuation request — then you can abort.
- **A worker is stalled (heartbeat expired in redis).** That's the AgentForge daemon's problem, not the worker's. The daemon will mark the worker `stalled` and the held task `failed` with reason `worker_stalled`. You can re-run `/worker N` in a new session to bring it back. Old residue in `${MACHINE}/queue/processing/task-X.${WORKER_ID}.json` can be moved back to `${MACHINE}/queue/inbox/task-X.json` manually if you want it retried.
- **The inbox has tasks but nothing is being claimed.** Check `redis-cli SMEMBERS agentforge:workers` — if it's empty, no workers are registered. Check that each worker session is actually executing the loop and not waiting on a user prompt. Also confirm each sidecar is alive (`ps -p $(cat .../sidecar.pid)`) — a dead sidecar means the worker probably halted at Phase A.4.

---

## Done criteria for this skill

You are not "done" with the worker after one task. The skill keeps you in the main loop until:

1. The user closes the session (hard shutdown — heartbeat expires naturally), OR
2. A `shutdown` file appears in `state/workers/${MACHINE}/workers/${WORKER_ID}/` and Phase B.1's blocking Bash call returns `SHUTDOWN_REQUESTED` on its next 5s tick, driving the worker into Phase E.

There is no other exit condition. Do not exit the loop after a successful task. Do not exit the loop after a failed task. Do not ask the user "should I keep going?" after each task. Just keep polling.

## User Request

$ARGUMENTS
