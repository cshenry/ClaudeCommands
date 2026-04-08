# Command: worker

## Purpose

Run this Claude Code session as one of the persistent workers in the **AgentForge worker-shell pool**. The worker polls a shared inbox for task envelopes, claims them atomically, runs each task in a fresh `Task` subagent (so the parent session's OAuth covers the work and each task gets its own context), handles soft timeouts via continuation requests rather than killing the subagent, and writes results to an outbox.

This skill replaces the broken `subprocess.run(["claude", "--print", ...])` call site in AgentForge after the **April 4 2026 Anthropic policy change** that blocked subprocess invocations of `claude` from Max plan accounts (returns 400 "third-party app"). Interactive Claude Code sessions, subagents, and hooks are unaffected — so the pivot is to keep three persistent interactive sessions polling a file queue.

## Invocation

```
/worker 1
/worker 2
/worker 3
```

The single argument is the worker number (1, 2, or 3). Open three Cursor windows in any repo, run one of these in each, and you have a 3-worker pool. The worker number is the only thing that distinguishes the three sessions; they share the same queue directories and redis namespace.

## Authoritative spec

The file-handoff protocol that this skill implements is defined in:

```
/Users/chenry/Dropbox/Projects/AIAssistant/agent-io/prds/agentforge-worker-shell-pivot/protocol.md
```

If anything below conflicts with that file, the protocol wins. Read it before modifying this skill.

---

## What you (Claude) should do when this skill is invoked

You are about to become a worker. The user has run `/worker N` and you are now responsible for executing the loop below until the user closes the session or asks you to stop. Treat this as a long-running operational task — you are NOT a one-shot coding assistant for the duration of this session.

### Argument parsing

1. Read `$ARGUMENTS`. It should be a single integer in `{1, 2, 3}`. If it is missing, malformed, or out of range, halt with a clear error message and ask the user to re-invoke with a valid worker number. Do not pick a default.
2. Set `WORKER_NUM` to the parsed integer and `WORKER_ID` to `worker-${WORKER_NUM}`.
3. Export `WORKER_ID` in the bash environment for the rest of the session: `Bash(export WORKER_ID=worker-N)` — you'll need it in the heartbeat hook command.

---

## Phase A — Registration

Run all of these once at startup, before entering the main loop.

### A.1 Verify and create directories

The worker queue lives under AgentForge's gitignored `state/` tree:

```
/Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/inbox
/Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/processing
/Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/outbox
/Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/continuation
/Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/control
/Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/archive
/Users/chenry/Dropbox/Projects/AgentForge/state/workers/workers/${WORKER_ID}
```

Create any that are missing with `Bash(mkdir -p ...)`. Do not error if they already exist.

### A.2 Verify redis is up

Run `Bash(redis-cli ping)`. The expected output is `PONG`. If it's not, halt the skill with a one-line error explaining that redis is required and that the user should start it (e.g., `brew services start redis`) before re-running `/worker N`. Do NOT continue without redis — the AgentForge daemon depends on the heartbeat keys to know which workers are alive.

### A.3 Register in redis

Run these commands (substituting `${WORKER_ID}`):

```bash
redis-cli SADD agentforge:workers ${WORKER_ID}
redis-cli SET agentforge:worker:${WORKER_ID}:status idle
redis-cli SET agentforge:worker:${WORKER_ID}:task ""
redis-cli SET agentforge:worker:${WORKER_ID}:hb $(date +%s) EX 1200
```

The 1200-second TTL on the heartbeat key matches the protocol (20 minutes — accommodates a 15-minute soft timeout plus safety margin).

### A.4 Configure the PostToolUse heartbeat hook (preferred)

The hook keeps the worker's heartbeat key fresh after every tool call, including tool calls made by the spawned subagent. This is what lets the daemon distinguish a stalled worker from one that's just running a long task.

**Procedure:**

1. Determine the path to the session's `.claude/settings.json`. This is the **session working directory** (whatever directory the user opened Cursor in), not the AgentForge tree.
2. Read it with the `Read` tool. If the file does not exist, treat existing settings as `{}`.
3. Parse the JSON. Find or create `hooks.PostToolUse` (it is an array). Append a hook entry that runs the heartbeat refresh:

   ```json
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "*",
           "hooks": [
             {
               "type": "command",
               "command": "redis-cli SET agentforge:worker:${WORKER_ID}:hb $(date +%s) EX 1200 > /dev/null 2>&1 || true"
             }
           ]
         }
       ]
     }
   }
   ```

   **Important merge rules:**
   - DO NOT clobber existing `PostToolUse` entries. Append to the array.
   - DO NOT touch other top-level keys in `settings.json`.
   - The `${WORKER_ID}` literal MUST be expanded into the command string before writing — write `worker-1` (or whichever) directly into the file, not the unexpanded variable. Hooks are exec'd by Claude Code without the parent shell's environment, so the env var won't be available.
   - The `|| true` suffix prevents a hook failure (e.g., redis briefly down) from blocking tool calls.
4. Write the merged JSON back with the `Write` tool.
5. Inform the user one time that you wrote a hook entry to `.claude/settings.json` and that they may want to remove it after stopping the worker.

If the merge is non-trivial (existing PostToolUse hooks with complex matchers, schema you don't recognize, etc.), DO NOT guess — print the JSON snippet above and ask the user to add it manually, then wait for them to confirm before continuing. Phase B's defensive heartbeat refresh in the loop body is enough to keep the worker alive even without the hook, so this is acceptable.

### A.5 Defensive heartbeat (always on)

Even with the hook installed, the main loop will refresh the heartbeat at the top of every iteration as a safety net. See Phase B step 1.

### A.6 Log startup

Append a JSON line to `state/workers/workers/${WORKER_ID}/log.jsonl`:

```json
{"event": "worker_started", "worker_id": "worker-N", "timestamp": "<ISO8601 UTC>", "session_pid": <pid if known>}
```

Use `Bash(echo '...' >> path/to/log.jsonl)` or the `Write` tool with append semantics. (`Bash` with `>>` is fine here — this is a one-line append, not a file edit.)

### A.7 Confirm to user

Print a single line:

```
Worker ${WORKER_ID} ready. Polling for tasks.
```

Then enter the main loop.

---

## Phase B — Main loop

Loop indefinitely. Each iteration:

### B.1 Refresh heartbeat (defensive)

```bash
redis-cli SET agentforge:worker:${WORKER_ID}:hb $(date +%s) EX 1200
```

The hook should already do this on every tool call, but the worker may have been idle (no tool calls) for the full 30s sleep cycle, so refresh at the top of each iteration to be safe.

### B.2 Poll inbox

List `state/workers/queue/inbox/*.json` sorted by mtime ascending. Use:

```bash
ls -1tr /Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/inbox/*.json 2>/dev/null
```

(`-1` one per line, `-t` sort by mtime, `-r` reverse so oldest first.)

If the listing is empty or the glob matched nothing, sleep 30 seconds via `Bash(sleep 30)` and continue the loop.

### B.3 Atomic claim

For each file in the listing (oldest first), attempt to claim it:

```bash
mv /Users/chenry/.../queue/inbox/task-X.json /Users/chenry/.../queue/processing/task-X.${WORKER_ID}.json
```

POSIX `mv` on a local filesystem is atomic. If another worker claimed it first, the `mv` exits non-zero with "No such file or directory". Catch that, move on to the next file in the list, and try again. If all files in the listing fail to claim (race with the other workers), sleep 30s and continue.

On a successful claim:

- The file is now at `processing/task-X.${WORKER_ID}.json` and exclusively yours.
- Remember the original `task_id` (the basename without `.json` and without the `.${WORKER_ID}` suffix). You'll need it for the result envelope and for redis keys.

### B.4 Update redis claim state

```bash
redis-cli SET agentforge:worker:${WORKER_ID}:status processing
redis-cli SET agentforge:worker:${WORKER_ID}:task task-X
redis-cli SET agentforge:worker:${WORKER_ID}:started_at $(date -u +%Y-%m-%dT%H:%M:%S)
```

### B.5 Read the task envelope

`Read` the file at `processing/task-X.${WORKER_ID}.json`. Parse the JSON and extract:

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

### B.6 Build the subagent prompt

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

### B.7 Spawn subagent

Invoke the `Task` tool with:

- `subagent_type`: `"general-purpose"`
- `description`: `"AF ${task_id_short}"` where `task_id_short` is the last 8 chars of the task_id (the Task tool requires a 3-5 word description; this stays under the limit).
- `prompt`: the combined prompt from B.6
- `run_in_background`: `true`

Capture the `agent_id` (or whatever identifier the Task tool returns) — you need it for `TaskOutput` and `TaskStop`.

Record the start time as `started_at_unix = $(date +%s)`.

### B.8 Inner poll loop

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

Notes:
- Do not call `TaskStop` on a healthy `running` agent. Only `TaskStop` on explicit abort from Phase D.
- The PostToolUse hook fires on each `TaskOutput` and `Bash(sleep)` call, so the worker's heartbeat stays fresh during long subagent runs even without the defensive refresh in Phase B.1.
- The subagent's own tool calls also trigger the hook (it inherits the parent session's hook config), so subagent activity also keeps the heartbeat fresh.

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

**Working directory verification:** Even when the subagent reports `completed`, check the final output for the substring `ABORTED — working directory mismatch`. If found, override the result envelope with `success: false` and `error: "working_directory_mismatch"`. This catches cases where the subagent followed the abort instruction in B.6's mandatory first action. Do NOT mark this as a success even though the subagent technically completed normally — the task did not run.

`tokens_used` should come from `TaskOutput` if it exposes that; otherwise leave it `0`. Do not synthesize a fake number.

### C.2 Write to outbox

Use the `Write` tool to create `state/workers/queue/outbox/task-X.json` with the envelope. The outbox file uses the bare `task-X.json` name (no `.${WORKER_ID}` suffix) — the executor on the AgentForge side polls for that exact name.

### C.3 Archive the processing file

```bash
mv /Users/chenry/.../queue/processing/task-X.${WORKER_ID}.json /Users/chenry/.../queue/archive/task-X.json
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

### C.6 Check for shutdown signal (Phase E gate)

Before returning to the top of the main loop, check whether `state/workers/workers/${WORKER_ID}/shutdown` exists. If it does, jump to Phase E. Otherwise, return to Phase B.

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

`Write` the envelope to `state/workers/queue/continuation/task-X.json`.

### D.3 Update redis

```bash
redis-cli SET agentforge:worker:${WORKER_ID}:status waiting_continuation
```

### D.4 Poll for control file

Loop:

1. `Bash(sleep 10)`.
2. Refresh heartbeat (the subagent may not be making any tool calls right now if it's stuck waiting on something, so the worker itself needs to keep heartbeating):
   ```bash
   redis-cli SET agentforge:worker:${WORKER_ID}:hb $(date +%s) EX 1200
   ```
3. Check whether `state/workers/queue/control/task-X.continue.json` or `state/workers/queue/control/task-X.abort.json` exists.

   - **`task-X.continue.json` found:**
     - `Read` it. Extract `additional_seconds` (default 900 if missing).
     - Delete it: `Bash(rm /Users/chenry/.../queue/control/task-X.continue.json)`.
     - Increment your local `continuation_count`.
     - Set `redis-cli SET agentforge:worker:${WORKER_ID}:status processing`.
     - Reset `started_at_unix` for the inner-loop deadline calculation: effectively, extend `timeout_seconds` by `additional_seconds`. Simplest: `started_at_unix = $(date +%s) - (timeout_seconds - additional_seconds)`. Easier alternative: increase `timeout_seconds` in-place by `additional_seconds`.
     - Return to Phase B.8 (the inner poll loop).

   - **`task-X.abort.json` found:**
     - `Read` it (you don't actually need fields from it, but read it for symmetry / future-proofing).
     - Delete it: `Bash(rm /Users/chenry/.../queue/control/task-X.abort.json)`.
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

Between tasks, the worker checks for `state/workers/workers/${WORKER_ID}/shutdown` (see C.6). If present:

1. Update redis: `redis-cli SET agentforge:worker:${WORKER_ID}:status stopping`.
2. Remove worker from active set:
   ```bash
   redis-cli SREM agentforge:workers ${WORKER_ID}
   redis-cli DEL agentforge:worker:${WORKER_ID}:hb agentforge:worker:${WORKER_ID}:status agentforge:worker:${WORKER_ID}:task agentforge:worker:${WORKER_ID}:started_at
   ```
3. Delete the shutdown file: `Bash(rm state/workers/workers/${WORKER_ID}/shutdown)`.
4. Append a `worker_stopped` event to `log.jsonl`.
5. Print: `Worker ${WORKER_ID} stopped cleanly. You may close this session.`
6. Exit the main loop. Return control to the user.

### E.2 Hard shutdown (SIGINT / window close)

If the user closes the Cursor window or sends SIGINT, the session terminates without giving you a chance to clean up. The heartbeat key will simply expire after 1200s and the AgentForge daemon will mark the worker as stalled. This is a legitimate exit path — no special handling required from this skill.

---

## Things to avoid

- **Do NOT** add Python files. The whole point of the worker-shell pivot is to avoid `subprocess.run([claude, ...])`. This skill should drive everything via `Bash`, `redis-cli`, `Read`, `Write`, `Task`, `TaskOutput`, and `TaskStop`.
- **Do NOT** run tasks directly in the worker session. Always spawn a `Task` subagent so each task gets a fresh context. If you skip the subagent step, every task pollutes the worker's context and the worker eventually dies of context exhaustion.
- **Do NOT** call `TaskStop` on a `running` agent unless the abort path in Phase D explicitly tells you to. The whole continuation mechanism exists so we don't kill long-running but healthy work.
- **Do NOT** add error-handling for cases that can't happen. Validate at the edges (envelope read, redis ping, repo_path exists) and let everything else propagate.
- **Do NOT** add backwards-compat shims. This skill is brand new.
- **Do NOT** modify files outside the AgentForge state tree, the working directory's `.claude/settings.json`, and the queue directories listed above.
- **Do NOT** assume only one worker is running. The atomic-claim protocol in B.3 is what keeps multiple workers honest. Trust it.

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

redis-cli TTL agentforge:worker:worker-1:hb
# Expected: a positive integer <= 1200
```

### 3. Drop a test task

Save the following to `/Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/inbox/task-smoke001.json`:

```json
{
  "task_id": "task-smoke001",
  "prompt": "Run `echo hello from subagent` in bash and report what you see. End with a SUMMARY: line.",
  "system_prompt": "You are a smoke-test subagent. Be brief.",
  "repo_path": "/Users/chenry/Dropbox/Projects/AgentForge",
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

Within ~30 seconds one of the workers should claim it. Verify with:

```bash
ls /Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/processing/
# Expected: task-smoke001.worker-N.json   (for some N in 1..3)

redis-cli GET agentforge:worker:worker-N:status   # the one that claimed
# Expected: "processing"

redis-cli GET agentforge:worker:worker-N:task
# Expected: "task-smoke001"
```

### 4. Verify the result

After the subagent completes (should be quick), check:

```bash
cat /Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/outbox/task-smoke001.json
# Expected: a result envelope with success: true, output containing "hello from subagent"

ls /Users/chenry/Dropbox/Projects/AgentForge/state/workers/queue/archive/
# Expected: task-smoke001.json
```

### 5. Shutdown test

```bash
touch /Users/chenry/Dropbox/Projects/AgentForge/state/workers/workers/worker-1/shutdown
```

Within one main-loop iteration (≤30s after the current task ends — or immediately if idle when checked) worker-1 should print `Worker worker-1 stopped cleanly.` and exit. Verify:

```bash
redis-cli SMEMBERS agentforge:workers
# Expected: only "worker-2" and "worker-3"

redis-cli EXISTS agentforge:worker:worker-1:hb
# Expected: 0
```

Note: the current implementation only checks the shutdown file at the end of Phase C (between tasks). If a worker is idle in the Phase B sleep, it will pick up the shutdown signal at the next iteration of the main loop. Add a shutdown check at the top of Phase B if you need faster reaction during idle periods.

---

## Operational tips

- **Where is the queue?** `/Users/chenry/Dropbox/Projects/AgentForge/state/workers/`. Inside the AgentForge gitignored `state/` tree, so nothing in here is committed.
- **How do I tell which worker grabbed which task?** Look at `processing/*.worker-N.json` filenames, or `redis-cli GET agentforge:worker:worker-N:task`.
- **A task is stuck. How do I abort?** Drop a `task-X.abort.json` file in `state/workers/queue/control/`. The worker will pick it up within 10s on its next Phase D poll. Note: this only works if the worker is in `waiting_continuation` state. If the subagent is healthy and running, it will run to its natural completion or until the soft timeout triggers a continuation request — then you can abort.
- **A worker is stalled (heartbeat expired in redis).** That's the AgentForge daemon's problem, not the worker's. The daemon will mark the worker `stalled` and the held task `failed` with reason `worker_stalled`. You can re-run `/worker N` in a new session to bring it back. Old residue in `processing/task-X.${WORKER_ID}.json` can be moved back to `inbox/task-X.json` manually if you want it retried.
- **The inbox has tasks but nothing is being claimed.** Check `redis-cli SMEMBERS agentforge:workers` — if it's empty, no workers are registered. Check that each worker session is actually executing the loop and not waiting on a user prompt.
- **I want to remove the heartbeat hook from settings.json.** It lives in `.claude/settings.json` in whatever directory you launched the worker from. Remove the `agentforge:worker:` line from the `PostToolUse` hooks array. Or just delete the whole file if you don't have other custom settings — the worker will function with only the defensive heartbeat in Phase B.1, just with a coarser refresh interval.

---

## Done criteria for this skill

You are not "done" with the worker after one task. The skill keeps you in the main loop until:

1. The user closes the session (hard shutdown — heartbeat expires naturally), OR
2. A `shutdown` file appears in `state/workers/workers/${WORKER_ID}/` and you process it via Phase E.

There is no other exit condition. Do not exit the loop after a successful task. Do not exit the loop after a failed task. Do not ask the user "should I keep going?" after each task. Just keep polling.

## $ARGUMENTS
