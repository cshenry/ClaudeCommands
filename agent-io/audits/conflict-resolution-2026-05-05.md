# Skill Registry Conflict Resolution Audit

**Date:** 2026-05-05
**Registry:** `/Users/chenry/Dropbox/Projects/ClaudeCommands/state/skill_registry.json`
**Registry snapshot:** `written_at: 2026-05-05T04:56:45Z`

## Executive Summary

The skill registry flags **20 skills** with `conflict: true`. After analysis:

- **Easy:** 17 conflicts -- one clearly-legitimate home repo + N identical junk-drawer copies from legacy mass-deploy
- **Hard:** 1 conflict (`ai-forge`) -- genuine content divergence between two legitimate repos (AgentForge and AIAssistant)
- **Retire candidates:** 2 (`doc-code-for-dev`, `doc-code-usage`) -- generic code-documentation skills with no clear owner; superseded by repo-specific development guides

All 20 conflicts follow the same root cause: a pre-2026-04 mass-deploy pushed every skill to 8 workspace/notebook repos (ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis). The 2026-04-17 skills audit updated canonical copies but left junk-drawer copies stale.

**Total junk-drawer copies to delete:** ~143 files across 8 repos (each repo has ~18 conflicting skills to remove, not counting non-conflicting legacy files also present).

**Repos needing commits:** 8 junk-drawer repos (bulk `git rm`) + 0 legitimate repos (no changes needed to canonical copies).

**Pattern:** For 19 of 20 conflicts, all junk-drawer copies share the same hash (identical old mass-deploy content), while the legitimate home has a different, newer hash from the 2026-04-17 audit. The one exception is `ai-forge` where both AgentForge and AIAssistant have independently-authored, legitimately-different versions.

---

## Easy Conflicts (17)

### `claude-commands-expert` -- easy

- **Keep**: `ClaudeCommands` at `/Users/chenry/Dropbox/Projects/ClaudeCommands/commands/claude-commands-expert.md` (mtime: 2026-04-17, last commit: `a70e670` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `32f5d4d2`)
- **Rationale**: Skill is about ClaudeCommands itself; ClaudeCommands is the obvious and only legitimate home.

### `create-new-project` -- easy

- **Keep**: `ClaudeCommands` at `/Users/chenry/Dropbox/Projects/ClaudeCommands/commands/create-new-project.md` (mtime: 2026-04-17, last commit: `a70e670` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `03b2cd26`)
- **Rationale**: Universal scaffolding skill; belongs in ClaudeCommands per user's mental model.

### `cursor-setup` -- easy

- **Keep**: `ClaudeCommands` at `/Users/chenry/Dropbox/Projects/ClaudeCommands/commands/cursor-setup.md` (mtime: 2026-04-17, last commit: `a70e670` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `a7488e18`)
- **Rationale**: IDE setup skill; universal scaffolding belongs in ClaudeCommands.

### `envman-expert` -- easy

- **Keep**: `ClaudeCommands` at `/Users/chenry/Dropbox/Projects/ClaudeCommands/commands/envman-expert.md` (mtime: 2026-04-17, last commit: `a70e670` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `40ee3654`)
- **Rationale**: EnvironmentManager repo has no `.claude/commands/` directory -- it was never set up as a skill-authoring home. ClaudeCommands holds the updated version. If EnvironmentManager becomes active again, this skill could migrate there, but for now ClaudeCommands is correct.
- **Note**: `envman-expert` is flagged in registry with `home_repo: ADP1Notebooks` which is wrong -- the canonical copy is in ClaudeCommands (alternate entry).

### `jupyter-dev` -- easy

- **Keep**: `ClaudeCommands` at `/Users/chenry/Dropbox/Projects/ClaudeCommands/commands/jupyter-dev.md` (mtime: 2026-04-17, last commit: `a70e670` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `9bc74e46`)
- **Rationale**: Universal development skill; ClaudeCommands is the canonical home.

### `emailassistant-expert` -- easy

- **Keep**: `EmailAssistant` at `/Users/chenry/Dropbox/Projects/EmailAssistant/.claude/commands/emailassistant-expert.md` (mtime: 2026-04-17, last commit: `f2abeb6` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `d04fff26`)
- **Rationale**: Domain skill for the EmailAssistant repo; belongs in its home repo.

### `emailassistant-ops` -- easy

- **Keep**: `EmailAssistant` at `/Users/chenry/Dropbox/Projects/EmailAssistant/.claude/commands/emailassistant-ops.md` (mtime: 2026-04-17, last commit: `f2abeb6` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `fbc84704`)
- **Rationale**: Domain skill for EmailAssistant operations; belongs in its home repo.

### `fbapkg-expert` -- easy

- **Keep**: `ModelSEEDpy` at `/Users/chenry/Dropbox/Projects/ModelSEEDpy/.claude/commands/fbapkg-expert.md` (mtime: 2026-04-17, last commit: `24f133f` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `96711f84`)
- **Rationale**: FBA Packages is part of ModelSEEDpy ecosystem. No separate FBAPackages/fba_packages repo exists on this machine. ModelSEEDpy is the authoring home.

### `kb-sdk-dev` -- easy

- **Keep**: `KBUtilLib` at `/Users/chenry/Dropbox/Projects/KBUtilLib/.claude/commands/kb-sdk-dev.md` (mtime: 2026-04-17, last commit: `352484c` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `c3e37d1f`)
- **Rationale**: KBase SDK development skill; KBUtilLib is the KBase utility home repo.

### `kbdatalake-dashboard-dev` -- easy

- **Keep**: `KBDatalakeDashboard` at `/Users/chenry/Dropbox/Projects/KBDatalakeDashboard/.claude/commands/kbdatalake-dashboard-dev.md` (mtime: 2026-04-17, last commit: `b75c4e9` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `ac7a0fc1`)
- **Rationale**: Strong name match -- skill name contains repo name.

### `kbdatalakeapps-dev` -- easy

- **Keep**: `KBDatalakeApps` at `/Users/chenry/Dropbox/Projects/KBDatalakeApps/.claude/commands/kbdatalakeapps-dev.md` (mtime: 2026-04-17, last commit: `0f5522d` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `6e26c72f`)
- **Rationale**: Strong name match -- skill name contains repo name.

### `kbutillib-dev` -- easy

- **Keep**: `KBUtilLib` at `/Users/chenry/Dropbox/Projects/KBUtilLib/.claude/commands/kbutillib-dev.md` (mtime: 2026-04-17, last commit: `352484c` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `233bc16d`)
- **Rationale**: Strong name match -- skill name contains repo name.

### `kbutillib-expert` -- easy

- **Keep**: `KBUtilLib` at `/Users/chenry/Dropbox/Projects/KBUtilLib/.claude/commands/kbutillib-expert.md` (mtime: 2026-04-17, last commit: `352484c` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `aba213b9`)
- **Rationale**: Strong name match -- skill name contains repo name.

### `modelseeddb-expert` -- easy

- **Keep**: `ModelSEEDDatabase` at `/Users/chenry/Dropbox/Projects/ModelSEEDDatabase/.claude/commands/modelseeddb-expert.md` (mtime: 2026-04-17, last commit: `bcb138c` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `9c383529`)
- **Rationale**: Strong name match -- ModelSEEDDatabase is the obvious home.

### `modelseedpy-expert` -- easy

- **Keep**: `ModelSEEDpy` at `/Users/chenry/Dropbox/Projects/ModelSEEDpy/.claude/commands/modelseedpy-expert.md` (mtime: 2026-04-17, last commit: `24f133f` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `c89e5117`)
- **Rationale**: Strong name match -- ModelSEEDpy is the obvious home.

### `msmodelutl-expert` -- easy

- **Keep**: `KBUtilLib` at `/Users/chenry/Dropbox/Projects/KBUtilLib/.claude/commands/msmodelutl-expert.md` (mtime: 2026-04-17, last commit: `352484c` "chore: Claude skills audit" on 2026-04-17)
- **Delete from**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `6d37b612`)
- **Rationale**: MSModelUtil is a module within KBUtilLib; KBUtilLib is the authoring home.

### `worker` -- easy

- **Keep**: `AgentForge` at `/Users/chenry/Dropbox/Projects/AgentForge/.claude/commands/worker.md` (mtime: 2026-05-03, last commit: `ac7831f` "feat: headless subprocess worker + worker skill machine_alias support" on 2026-05-03)
- **Delete from**: AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all junk-drawer, all identical old hash `64d4450a`)
- **Rationale**: Worker skill belongs in AgentForge. AIOrchestrator is the legacy name for the same project (now dormant). AgentForge version is actively maintained (commit 3 days ago).
- **Note**: ADP1Notebooks does NOT have a `worker.md` copy (only 7 junk-drawer repos for this skill).

---

## Hard Conflicts (1)

### `ai-forge` -- hard

- **Legitimate homes (with content differences)**:

  | Home | Path | mtime | Last commit | Hash (first 8) |
  |---|---|---|---|---|
  | AgentForge | `/Users/chenry/Dropbox/Projects/AgentForge/.claude/commands/ai-forge.md` | 2026-05-03 | `b56003a` "feat: add /ai-forge operator console command" 2026-04-13 | `942fb960` |
  | AIAssistant | `/Users/chenry/Dropbox/Projects/AIAssistant/.claude/commands/ai-forge.md` | 2026-05-03 | `a180630` "chore: update ai-* skills" 2026-05-03 | `150e8580` |

- **Junk-drawer copies**: None -- this conflict is only between two legitimate repos.

- **Diff snippet** (most meaningful divergence):
  ```diff
  --- AgentForge (302 lines)
  +++ AIAssistant (511 lines, with YAML frontmatter)
  -# Command: ai-forge
  +---
  +name: AI Forge
  +description: Submit, monitor, manage, and debug AgentForge tasks from AIAssistant
  +scope: repo:AIAssistant
  +---
  
  AgentForge version: "Native operator console for the AgentForge task system"
  AIAssistant version: "You are the AgentForge integration manager...You do NOT modify code in the AgentForge repo"
  
  AIAssistant version includes: hardcoded paths, session file references, machine names,
  --auto-review/--auto-merge conventions, --timeout 900 defaults.
  AgentForge version: generic operator console without AIAssistant-specific paths.
  ```

- **Recommended canonical**: **Both are legitimate.** These are two intentionally different skills:
  - **AgentForge's `ai-forge.md`**: the generic operator console for AgentForge itself (302 lines, no frontmatter)
  - **AIAssistant's `ai-forge.md`**: the AIAssistant-scoped integration that calls AgentForge from within AIAssistant (511 lines, `scope: repo:AIAssistant`)

- **Open question for user**: These should likely be two separate skills with different names. Options:
  1. Rename AgentForge's to just `ai-forge` (the native console) and rename AIAssistant's to `ai-forge-submit` or keep as `ai-forge` with the `scope: repo:AIAssistant` frontmatter distinguishing it.
  2. Merge the AIAssistant-specific paths/conventions into the AgentForge version and delete the AIAssistant copy.
  3. Keep both as-is and resolve the registry conflict by scoping them differently (the `scope: repo:AIAssistant` frontmatter already does this conceptually, but the registry treats them as the same skill name).

---

## Retire Candidates (2)

### `doc-code-for-dev` -- retire candidate

- **Current home**: AIAssistant (alternate with different hash from junk drawers)
- **Junk-drawer copies**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all identical old hash `aa33b63e`)
- **Why retire**: This is a generic "document code for developers" skill. The 2026-04-15 audit notes `doc-code-for-dev` and `doc-code-usage` as part of the old `command_type` enum pattern. Modern repos have their own `-dev` skills (e.g., `kbutillib-dev`, `kbdatalakeapps-dev`) that provide repo-specific development guides. A generic doc-code skill adds little value.
- **If keeping**: AIAssistant at `/Users/chenry/Dropbox/Projects/AIAssistant/.claude/commands/doc-code-for-dev.md` (mtime: 2026-04-17, last commit: `61f44da` on 2026-04-17). Delete all 8 junk-drawer copies.
- **Recommendation**: Retire. Delete from AIAssistant and all junk drawers.

### `doc-code-usage` -- retire candidate

- **Current home**: AIAssistant (alternate with different hash from junk drawers)
- **Junk-drawer copies**: ADP1Notebooks, AIOrchestrator, AISynbioPipeline, ANMENotebooks, BERDLTablesPrototype, BVBRCHackathon, FitnessDatabaseAnalysis, PangenomeAnalysis (all identical old hash `3742969d`)
- **Why retire**: Same rationale as `doc-code-for-dev` -- generic code documentation skill superseded by repo-specific development guides.
- **If keeping**: AIAssistant at `/Users/chenry/Dropbox/Projects/AIAssistant/.claude/commands/doc-code-usage.md` (mtime: 2026-04-17, last commit: `61f44da` on 2026-04-17). Delete all 8 junk-drawer copies.
- **Recommendation**: Retire. Delete from AIAssistant and all junk drawers.

### Non-conflicting retire candidates (noted for completeness)

The 2026-04-15 audit also flagged these as retire candidates, but they are NOT in the conflict list (no `conflict: true`):
- `run_headless` -- superseded by AgentForge + direct CLI
- `free-agent` -- related to old headless workflow
- `create-prd` -- PRD workflow evolving; keep only if rewritten
- `generate-tasks` -- still a good primitive but low usage
- `analyze-email` -- predates EmailAssistant's own CLI

These exist only in junk-drawer repos (primarily ADP1Notebooks) and have no registry conflict because they have no legitimate home with a different version.

---

## Cleanup Execution Plan

### Repo: ADP1Notebooks

```bash
cd /Users/chenry/Dropbox/Projects/ADP1Notebooks
git rm .claude/commands/claude-commands-expert.md
git rm .claude/commands/create-new-project.md
git rm .claude/commands/cursor-setup.md
git rm .claude/commands/envman-expert.md
git rm .claude/commands/jupyter-dev.md
git rm .claude/commands/emailassistant-expert.md
git rm .claude/commands/emailassistant-ops.md
git rm .claude/commands/fbapkg-expert.md
git rm .claude/commands/kb-sdk-dev.md
git rm .claude/commands/kbdatalake-dashboard-dev.md
git rm .claude/commands/kbdatalakeapps-dev.md
git rm .claude/commands/kbutillib-dev.md
git rm .claude/commands/kbutillib-expert.md
git rm .claude/commands/modelseeddb-expert.md
git rm .claude/commands/modelseedpy-expert.md
git rm .claude/commands/msmodelutl-expert.md
git rm .claude/commands/doc-code-for-dev.md
git rm .claude/commands/doc-code-usage.md
git commit -m "chore: remove 18 mass-deployed skill copies (conflict cleanup)"
```

### Repo: AIOrchestrator

```bash
cd /Users/chenry/Dropbox/Projects/AIOrchestrator
git rm .claude/commands/claude-commands-expert.md
git rm .claude/commands/create-new-project.md
git rm .claude/commands/cursor-setup.md
git rm .claude/commands/envman-expert.md
git rm .claude/commands/jupyter-dev.md
git rm .claude/commands/emailassistant-expert.md
git rm .claude/commands/emailassistant-ops.md
git rm .claude/commands/fbapkg-expert.md
git rm .claude/commands/kb-sdk-dev.md
git rm .claude/commands/kbdatalake-dashboard-dev.md
git rm .claude/commands/kbdatalakeapps-dev.md
git rm .claude/commands/kbutillib-dev.md
git rm .claude/commands/kbutillib-expert.md
git rm .claude/commands/modelseeddb-expert.md
git rm .claude/commands/modelseedpy-expert.md
git rm .claude/commands/msmodelutl-expert.md
git rm .claude/commands/doc-code-for-dev.md
git rm .claude/commands/doc-code-usage.md
git rm .claude/commands/worker.md
git commit -m "chore: remove 19 mass-deployed skill copies (conflict cleanup)"
```

### Repo: AISynbioPipeline

```bash
cd /Users/chenry/Dropbox/Projects/AISynbioPipeline
git rm .claude/commands/claude-commands-expert.md
git rm .claude/commands/create-new-project.md
git rm .claude/commands/cursor-setup.md
git rm .claude/commands/envman-expert.md
git rm .claude/commands/jupyter-dev.md
git rm .claude/commands/emailassistant-expert.md
git rm .claude/commands/emailassistant-ops.md
git rm .claude/commands/fbapkg-expert.md
git rm .claude/commands/kb-sdk-dev.md
git rm .claude/commands/kbdatalake-dashboard-dev.md
git rm .claude/commands/kbdatalakeapps-dev.md
git rm .claude/commands/kbutillib-dev.md
git rm .claude/commands/kbutillib-expert.md
git rm .claude/commands/modelseeddb-expert.md
git rm .claude/commands/modelseedpy-expert.md
git rm .claude/commands/msmodelutl-expert.md
git rm .claude/commands/doc-code-for-dev.md
git rm .claude/commands/doc-code-usage.md
git rm .claude/commands/worker.md
git commit -m "chore: remove 19 mass-deployed skill copies (conflict cleanup)"
```

### Repo: ANMENotebooks

```bash
cd /Users/chenry/Dropbox/Projects/ANMENotebooks
git rm .claude/commands/claude-commands-expert.md
git rm .claude/commands/create-new-project.md
git rm .claude/commands/cursor-setup.md
git rm .claude/commands/envman-expert.md
git rm .claude/commands/jupyter-dev.md
git rm .claude/commands/emailassistant-expert.md
git rm .claude/commands/emailassistant-ops.md
git rm .claude/commands/fbapkg-expert.md
git rm .claude/commands/kb-sdk-dev.md
git rm .claude/commands/kbdatalake-dashboard-dev.md
git rm .claude/commands/kbdatalakeapps-dev.md
git rm .claude/commands/kbutillib-dev.md
git rm .claude/commands/kbutillib-expert.md
git rm .claude/commands/modelseeddb-expert.md
git rm .claude/commands/modelseedpy-expert.md
git rm .claude/commands/msmodelutl-expert.md
git rm .claude/commands/doc-code-for-dev.md
git rm .claude/commands/doc-code-usage.md
git rm .claude/commands/worker.md
git commit -m "chore: remove 19 mass-deployed skill copies (conflict cleanup)"
```

### Repo: BERDLTablesPrototype

```bash
cd /Users/chenry/Dropbox/Projects/BERDLTablesPrototype
git rm .claude/commands/claude-commands-expert.md
git rm .claude/commands/create-new-project.md
git rm .claude/commands/cursor-setup.md
git rm .claude/commands/envman-expert.md
git rm .claude/commands/jupyter-dev.md
git rm .claude/commands/emailassistant-expert.md
git rm .claude/commands/emailassistant-ops.md
git rm .claude/commands/fbapkg-expert.md
git rm .claude/commands/kb-sdk-dev.md
git rm .claude/commands/kbdatalake-dashboard-dev.md
git rm .claude/commands/kbdatalakeapps-dev.md
git rm .claude/commands/kbutillib-dev.md
git rm .claude/commands/kbutillib-expert.md
git rm .claude/commands/modelseeddb-expert.md
git rm .claude/commands/modelseedpy-expert.md
git rm .claude/commands/msmodelutl-expert.md
git rm .claude/commands/doc-code-for-dev.md
git rm .claude/commands/doc-code-usage.md
git rm .claude/commands/worker.md
git commit -m "chore: remove 19 mass-deployed skill copies (conflict cleanup)"
```

### Repo: BVBRCHackathon

```bash
cd /Users/chenry/Dropbox/Projects/BVBRCHackathon
git rm .claude/commands/claude-commands-expert.md
git rm .claude/commands/create-new-project.md
git rm .claude/commands/cursor-setup.md
git rm .claude/commands/envman-expert.md
git rm .claude/commands/jupyter-dev.md
git rm .claude/commands/emailassistant-expert.md
git rm .claude/commands/emailassistant-ops.md
git rm .claude/commands/fbapkg-expert.md
git rm .claude/commands/kb-sdk-dev.md
git rm .claude/commands/kbdatalake-dashboard-dev.md
git rm .claude/commands/kbdatalakeapps-dev.md
git rm .claude/commands/kbutillib-dev.md
git rm .claude/commands/kbutillib-expert.md
git rm .claude/commands/modelseeddb-expert.md
git rm .claude/commands/modelseedpy-expert.md
git rm .claude/commands/msmodelutl-expert.md
git rm .claude/commands/doc-code-for-dev.md
git rm .claude/commands/doc-code-usage.md
git rm .claude/commands/worker.md
git commit -m "chore: remove 19 mass-deployed skill copies (conflict cleanup)"
```

### Repo: FitnessDatabaseAnalysis

```bash
cd /Users/chenry/Dropbox/Projects/FitnessDatabaseAnalysis
git rm .claude/commands/claude-commands-expert.md
git rm .claude/commands/create-new-project.md
git rm .claude/commands/cursor-setup.md
git rm .claude/commands/envman-expert.md
git rm .claude/commands/jupyter-dev.md
git rm .claude/commands/emailassistant-expert.md
git rm .claude/commands/emailassistant-ops.md
git rm .claude/commands/fbapkg-expert.md
git rm .claude/commands/kb-sdk-dev.md
git rm .claude/commands/kbdatalake-dashboard-dev.md
git rm .claude/commands/kbdatalakeapps-dev.md
git rm .claude/commands/kbutillib-dev.md
git rm .claude/commands/kbutillib-expert.md
git rm .claude/commands/modelseeddb-expert.md
git rm .claude/commands/modelseedpy-expert.md
git rm .claude/commands/msmodelutl-expert.md
git rm .claude/commands/doc-code-for-dev.md
git rm .claude/commands/doc-code-usage.md
git rm .claude/commands/worker.md
git commit -m "chore: remove 19 mass-deployed skill copies (conflict cleanup)"
```

### Repo: PangenomeAnalysis

```bash
cd /Users/chenry/Dropbox/Projects/PangenomeAnalysis
git rm .claude/commands/claude-commands-expert.md
git rm .claude/commands/create-new-project.md
git rm .claude/commands/cursor-setup.md
git rm .claude/commands/envman-expert.md
git rm .claude/commands/jupyter-dev.md
git rm .claude/commands/emailassistant-expert.md
git rm .claude/commands/emailassistant-ops.md
git rm .claude/commands/fbapkg-expert.md
git rm .claude/commands/kb-sdk-dev.md
git rm .claude/commands/kbdatalake-dashboard-dev.md
git rm .claude/commands/kbdatalakeapps-dev.md
git rm .claude/commands/kbutillib-dev.md
git rm .claude/commands/kbutillib-expert.md
git rm .claude/commands/modelseeddb-expert.md
git rm .claude/commands/modelseedpy-expert.md
git rm .claude/commands/msmodelutl-expert.md
git rm .claude/commands/doc-code-for-dev.md
git rm .claude/commands/doc-code-usage.md
git rm .claude/commands/worker.md
git commit -m "chore: remove 19 mass-deployed skill copies (conflict cleanup)"
```

### Repo: AIAssistant (only if retiring doc-code-*)

```bash
cd /Users/chenry/Dropbox/Projects/AIAssistant
git rm .claude/commands/doc-code-for-dev.md
git rm .claude/commands/doc-code-usage.md
git commit -m "chore: retire doc-code-for-dev and doc-code-usage skills (superseded by repo-specific -dev skills)"
```

### Post-cleanup: Re-run skill inventory

After all junk-drawer deletions are committed, re-run the skill inventory to clear conflict flags:

```bash
# From ClaudeCommands or AIAssistant, invoke the inventory scan
# This should clear all 20 conflicts (19 easy + 1 hard needs manual decision)
```

### Hard conflict: ai-forge (manual decision required)

No git operations listed -- user must decide on naming/scoping strategy first. See the "Hard Conflicts" section above for options.
