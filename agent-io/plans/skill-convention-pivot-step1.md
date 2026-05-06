# Skill Convention Pivot — Step 1 of 6

**Status:** Ready for AgentForge submission as a developer task.
**Authored:** 2026-05-06 in `/ai-design` session on AIAssistant.
**Roadmap context:** Step 1 of a 6-step pivot. Steps 2-6 are documented in this directory or scheduled for future sessions.

---

## Why this work

`.claude/commands/` is being repositioned as **runtime** (gitignored, populated by `claude-skills sync`). Source-of-truth for skills moves to **`<repo>/agent-io/skills/<skill>.md`** (git-tracked, dev-time artifact).

**Reasons:**
1. Avoid polluting downstream repos' git history with universal skills that aren't relevant to that repo's purpose.
2. Cleanly separate dev-time source from runtime artifact.
3. Make `deploys_to_repos` an escape-hatch for narrow cases (e.g., guest-mode utility libraries) instead of the default sharing mechanism.
4. Claude-web access to skills (where they need to be in git) is handled by ad-hoc snapshot branches, not by polluting main.

**Salvage from branch `5d3bcb4`** (unmerged work from cancelled task-7d071264): the schema additions, three-pass deploy loop, and frontmatter parsing for `deploys_to_repos` are still correct. Reuse them.

---

## Scope

### 1. `inventory.py` — walk `agent-io/skills/` as primary

For each home repo (read from `assistant.state.registry.load_registry()` `repo_path` field), walk in this order:

1. `<repo>/agent-io/skills/<skill>.md` — primary source location (NEW)
2. `<repo>/.claude/commands/<skill>.md` — legacy fallback, emit deprecation warning to stderr
3. `<repo>/commands/<skill>.md` — legacy fallback for ClaudeCommands universals only, deprecation warning

Update the registry's `home_path` to reflect whichever location was found. After Step 2 migration runs, all `home_path` values should resolve to `agent-io/skills/`.

### 2. `sync.py` — add per-repo runtime target

`sync.py` currently writes to `~/.claude/commands/` (user-global). Add a second target: `<repo>/.claude/commands/` for the **local repo when subscribed**.

Resolution logic:
- For each skill `s` with home_repo `R`, sync `s` to `<R>/.claude/commands/` so when the user `cd`s into `R` and starts Claude Code, the skill is loadable as a project-scoped command.
- For each skill `s` with `deploys_to_repos: [repos]` (after wildcard expansion), also sync to each target repo's `.claude/commands/`.

Three-pass pattern unchanged — never `rmtree`, refuse skills missing frontmatter.

### 3. `sync-repos` — re-spec from `5d3bcb4`

Cherry-pick or re-implement from agent branch `agent/developer/phase-2-task-4-claude-skills-sync-repos-7d071264` (commit `5d3bcb4`):

**Keep:**
- Schema additions: `last_repo_deploy` per-skill, sibling to `last_deploy`
- Frontmatter `deploys_to_repos: [repos] | ["*"]`
- Wildcard expansion at sync time via `project_registry.yaml` `repo_path`
- Three-pass deploy loop, conflict guards (refuse if `home_repo == target_repo`)
- Dirty-repo refusal (with `--force` override)
- Verification script

**Change:**
- **Remove auto-commit as default behavior.** Target `.claude/commands/` is gitignored after Step 2 migration runs, so a commit would be no-op anyway.
- **Add opt-in `--commit` flag.** When passed, behaves like the original spec: single per-repo commit with structured message. Use case: claude-web branch snapshots.
- Without `--commit`, just write the files and update `last_repo_deploy`. No git activity in the target repo.

### 4. New CLI: `claude-skills migrate-domain-skills`

```bash
claude-skills migrate-domain-skills              # dry-run
claude-skills migrate-domain-skills --apply
```

For each skill in registry whose `home_path` resolves to `<home>/.claude/commands/<skill>.md` or `<home>/commands/<skill>.md`:
- New path: `<home>/agent-io/skills/<skill>.md`
- Use `git mv` (preserves history); also move sibling `<skill>/` context dir if present
- Update registry `home_path` to the new location

For each home_repo touched:
- Append to `.gitignore` (idempotent — check before adding):
  ```
  # claude-skills runtime artifacts (populated by `claude-skills sync`)
  .claude/commands/
  .claude/skills/
  ```
- Stage `.gitignore` + the moves
- Single migration commit per repo:
  ```
  chore: migrate skills source to agent-io/skills/

  Convention pivot: .claude/commands/ is now runtime-only (gitignored,
  populated by `claude-skills sync`). Source-of-truth lives in
  agent-io/skills/.
  ```

**No push.** User pushes per-repo when ready.

### 5. Update ClaudeCommands and AIAssistant gitignores too

These repos are home for universal and platform skills. Apply the same `.gitignore` treatment to them. ClaudeCommands universals currently in `commands/` (not `.claude/commands/`) — `migrate-domain-skills` should also move them to `agent-io/skills/`.

### 6. Documentation updates

- Add a `## Skill Source-of-Truth` section to the ClaudeCommands README (or update existing section) explaining the new convention
- Add a schema-doc comment in `state/skill_registry.json` (or in `claude_skills/registry.py`) explaining `agent-io/skills/` as canonical
- If `claude_md/tier1.md` references `.claude/commands/` as a source location anywhere, update it (it shouldn't, but check)

---

## Out of scope

- **Running the migration** (`migrate-domain-skills --apply`) — user does this manually in Step 2 after this task lands and the user has reviewed the dry-run output.
- **Auditing existing skills for staleness** — Step 3 (separate researcher task).
- **Building new component-expert skills** — Step 5 (separate dev tasks).

---

## Verification

Self-contained script `scripts/verify_convention_pivot.sh` (or `.py`) that:

1. **Inventory walks new location:** Create temp repo with both `agent-io/skills/foo.md` and `.claude/commands/bar.md`. Run `inventory --apply` against it. Confirm `foo` registered with new home_path, `bar` registered with deprecation warning.

2. **Sync writes to per-repo runtime:** Stage a skill in a temp home repo's `agent-io/skills/`. Run `claude-skills sync <machine> --apply`. Confirm the skill appears in `<home>/.claude/commands/`.

3. **`migrate-domain-skills --dry-run`:** Set up temp repo with skills under `.claude/commands/`. Run the migrate command in dry-run. Confirm planned moves and gitignore additions are reported correctly. Confirm no actual file changes.

4. **`migrate-domain-skills --apply`:** Same setup. Run with `--apply`. Confirm `git mv` moves preserved, `.gitignore` updated, migration commit created.

5. **`sync-repos` no longer auto-commits:** Set `deploys_to_repos: [target]` on a test skill. Run `sync-repos --apply` against a temp target repo. Confirm files written but no commit created. Run with `--commit`. Confirm a commit was created with the structured message.

6. **`sync-repos` guards intact:** Conflict (home == target) refused. Dirty repo refused without `--force`. Wildcard expansion works.

7. Cleanup: real ClaudeCommands and AIAssistant repos untouched after script completes.

The agent runs the script and confirms all checks pass before marking the task complete.

---

## Reuse

- Branch `agent/developer/phase-2-task-4-claude-skills-sync-repos-7d071264` (commit `5d3bcb4`) — salvage `claude_skills/repo_sync.py` and schema work
- `claude_skills/manifest.py` — hashing
- `claude_skills/frontmatter.py` — YAML parsing
- `claude_skills/registry.py` — atomic writes
- `claude_skills/sync.py` — three-pass pattern (mirror it)
- `assistant.state.registry.load_registry()` (in AIAssistant, `PYTHONPATH=/Users/chenry/Dropbox/Projects/AIAssistant/src`) — `repo_path` lookups

---

## Submission

```bash
cd ~/Dropbox/Projects/AIAssistant
agentforge submit \
  --role developer \
  --machine primary-laptop \
  --repo ClaudeCommands \
  --repo AIAssistant:ro \
  --timeout 1800 \
  --summary "Convention pivot Step 1: agent-io/skills/ source + sync runtime + migrate CLI" \
  --tag claudecommands --tag convention-pivot \
  "$(cat ~/Dropbox/Projects/ClaudeCommands/agent-io/plans/skill-convention-pivot-step1.md)"
```

Auto-merge default ON (developer role). Per memory: chain `merge ✓` doesn't actually merge — verify and manual-merge after.
