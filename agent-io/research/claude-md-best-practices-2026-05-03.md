# CLAUDE.md Best Practices Research

**Date:** 2026-05-03  
**Purpose:** Inform design of a 3-tier CLAUDE.md system (Universal / Machine / Repo)

---

## Executive Summary

Anthropic's official guidance is clear: CLAUDE.md should be under 200 lines, concise, specific, and contain only what Claude cannot infer from code. The file loads into every session's context window, consuming tokens before any work begins. Community consensus reinforces brevity --- the best real-world files are 30-80 lines. Hierarchical setups (user-global + per-repo) are first-class in Claude Code, with more-specific files taking precedence. The 3-tier scheme proposed here aligns well with both Anthropic's architecture and community patterns.

---

## 1. Anthropic's Own Guidance

Anthropic's official documentation at [code.claude.com/docs/en/memory](https://code.claude.com/docs/en/memory) and [code.claude.com/docs/en/best-practices](https://code.claude.com/docs/en/best-practices) provides canonical guidance:

**Purpose:** Give Claude persistent context it cannot infer from code alone --- build commands, conventions, architectural decisions, workflow rules.

**What to include:**
- Bash commands Claude cannot guess
- Code style rules that differ from defaults
- Testing instructions and preferred test runners
- Repository etiquette (branch naming, PR conventions)
- Architectural decisions specific to the project
- Developer environment quirks (required env vars)
- Common gotchas or non-obvious behaviors

**What to exclude:**
- Anything Claude can figure out by reading code
- Standard language conventions Claude already knows
- Detailed API documentation (link instead)
- Information that changes frequently
- Long explanations or tutorials
- File-by-file descriptions of the codebase
- Self-evident practices like "write clean code"

**Length:** "Target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence."

**Key quote:** "For each line, ask: 'Would removing this cause Claude to make mistakes?' If not, cut it. Bloated CLAUDE.md files cause Claude to ignore your actual instructions!"

Sources:
- [Memory docs](https://code.claude.com/docs/en/memory)
- [Best practices](https://code.claude.com/docs/en/best-practices)
- [Anthropic teams usage PDF](https://www-cdn.anthropic.com/58284b19e702b49db9302d5b6f135ad8871e7658.pdf)

---

## 2. Mature Community Patterns

### Real-world examples analyzed:

1. **anthropics/claude-code-action** ([CLAUDE.md](https://github.com/anthropics/claude-code-action/blob/main/CLAUDE.md)) --- ~50 lines. Sections: Commands, What This Is, How It Runs, Key Concepts, Things That Will Bite You, Code Conventions. Notably focuses on gotchas and runtime choices (Bun not Node). Leaves out: code style details, testing strategy beyond "bun test".

2. **anthropics/claude-code** ([repo](https://github.com/anthropics/claude-code)) --- Anthropic's own monorepo uses CLAUDE.md plus `.claude/rules/` for path-scoped guidance. Modular approach with plugins documented in their own directories.

3. **HumanLayer production file** ([blog](https://www.humanlayer.dev/blog/writing-a-good-claude-md)) --- Under 60 lines. Focuses exclusively on build/test commands and architectural gotchas. Explicitly avoids code style (defers to linters). Uses progressive disclosure: separate `agent_docs/` files for deep knowledge.

4. **centminmod/my-claude-code-setup** ([GitHub](https://github.com/centminmod/my-claude-code-setup)) --- Template approach with "memory bank" files. Demonstrates shared rules via symlinks across projects.

5. **shanraisshan/claude-code-best-practice** ([GitHub](https://github.com/shanraisshan/claude-code-best-practice)) --- Reference implementation showing skills, subagents, hooks, and commands structure. CLAUDE.md is minimal; behavior delegated to `.claude/rules/` and skills.

6. **affaan-m/everything-claude-code** ([user-CLAUDE.md](https://github.com/affaan-m/everything-claude-code/blob/main/examples/user-CLAUDE.md)) --- Example user-level `~/.claude/CLAUDE.md` with personal preferences (editor, communication style, common paths).

**Pattern:** The best files are 30-80 lines, focus on "what will bite you," and defer domain knowledge to skills or rules. None include lengthy explanations.

---

## 3. Hierarchical / Multi-file CLAUDE.md

### How Claude Code resolves the hierarchy (official docs):

| Scope | Location | Loaded |
|-------|----------|--------|
| Managed policy | `/Library/Application Support/ClaudeCode/CLAUDE.md` | Always, cannot be excluded |
| User-global | `~/.claude/CLAUDE.md` | Every session |
| Project | `./CLAUDE.md` or `./.claude/CLAUDE.md` | Every session in that project |
| Local | `./CLAUDE.local.md` | Every session (gitignored) |
| Subdirectory | `./subdir/CLAUDE.md` | On-demand when files in subdir are read |

**Precedence:** All files are concatenated into context (not overriding). Ordered root-down: user-global appears first, then project-root, then local. More-specific content is read last, giving it recency bias.

**Key behaviors:**
- Project-root CLAUDE.md survives `/compact`; subdirectory files do not auto-reload after compaction.
- `@path/to/import` syntax allows referencing shared files (max 5 hops).
- `claudeMdExcludes` setting skips irrelevant files in monorepos.
- Symlinks supported in `.claude/rules/` for cross-project sharing.

**For the 3-tier scheme:** Tier 1 + Tier 2 concatenated into `~/.claude/CLAUDE.md` is the correct approach. Claude loads it first every session. Tier 3 lives in each repo's `.claude/CLAUDE.md`. This matches the documented architecture exactly.

Source: [Memory docs - How CLAUDE.md files load](https://code.claude.com/docs/en/memory)

---

## 4. Content Taxonomy and Tier Assignment

| Category | Examples | Recommended Tier | Rationale |
|----------|----------|-----------------|-----------|
| Behavioral norms | Be specific, be honest, don't over-engineer | **Tier 1 (Universal)** | Same everywhere, defines interaction contract |
| Destructive action policy | Confirm before force-push, file deletion | **Tier 1** | Universal safety |
| Artifact file organization | agent-io/ structure | **Tier 1** | Cross-repo convention |
| Git hygiene | Commit style, staging practices | **Tier 1** | Universal |
| State file policy | Don't hand-edit state/ | **Tier 1** | Any repo with state/ |
| Privacy/security posture | What NOT to send externally | **Tier 2 (Machine)** | Varies by machine sensitivity |
| Available services/tools | Redis, DocDB, GPU access | **Tier 2** | Machine-specific |
| Filesystem paths | Dropbox location, venv paths | **Tier 2** | Machine-specific |
| Machine role | Interactive dev vs headless worker | **Tier 2** | Defines Claude's operating mode |
| Forbidden operations | Don't run GPU jobs on laptop | **Tier 2** | Machine-specific constraints |
| Build/test commands | `npm test`, `pytest` | **Tier 3 (Repo)** | Repo-specific |
| Code style deviations | Import style, naming | **Tier 3** | Repo-specific |
| Architecture decisions | Module boundaries, API patterns | **Tier 3** | Repo-specific |
| Common gotchas | Race conditions, quirky APIs | **Tier 3** | Repo-specific |
| Project glossary | Domain terms | **Tier 3** | Repo-specific |
| Dependencies/toolchain | Python version, Bun vs Node | **Tier 3** | Repo-specific |

---

## 5. Anti-patterns

1. **Bloat / Kitchen Sink:** Including every possible instruction. Result: Claude ignores important rules buried in noise.
   > Bad: 500-line CLAUDE.md with formatting rules, API docs, tutorials, and philosophy.

2. **Restating what code already says:** Describing file-by-file structure that Claude can discover via `ls` and `Read`.
   > Bad: "src/auth/login.ts handles login, src/auth/logout.ts handles logout..."

3. **Linter-in-prose:** Writing code style rules that a formatter enforces automatically.
   > Bad: "Use 2-space indentation, trailing commas, semicolons." (Just run prettier.)

4. **Stale instructions:** Version-specific commands or paths that rot.
   > Bad: "Use Node 18.4.2" when you've upgraded twice since writing it.

5. **Narrating internal state:** Treating CLAUDE.md as a changelog or session log.
   > Bad: "Last session we discussed refactoring the auth module..."

6. **Secret/credential leakage:** Including API keys, tokens, or connection strings.
   > Bad: "Database password is hunter2" --- even in CLAUDE.local.md.

7. **Verbose examples:** Pasting 50-line code blocks as examples when a one-liner reference suffices.
   > Bad: Full function implementations as "templates." Use `@path` imports or skills instead.

8. **Prescriptive boilerplate:** Generic best-practice platitudes.
   > Bad: "Write clean, maintainable, well-documented code." Claude already does this.

---

## 6. Length and Token-Budget Guidance

**Official recommendation:** Under 200 lines per file.

**Community consensus:** Under 60-80 lines is optimal for production. Under 2,000 tokens ideal; under 5,000 tokens acceptable.

**Token economics:**
- CLAUDE.md loads every session, every turn after compaction. It is a fixed cost.
- On a 200K context window, autocompact fires at ~167K tokens. Your CLAUDE.md re-injects after compaction.
- A 200-line CLAUDE.md is roughly 2,000-3,000 tokens --- about 1.5% of context. Acceptable.
- A 500-line CLAUDE.md at ~5,000-7,000 tokens starts crowding actual work context.
- Research suggests Claude can follow ~150-200 instructions consistently; more causes dropout.

**When it becomes counterproductive:**
- When rules contradict each other (Claude picks arbitrarily)
- When important rules get lost in noise
- When the file exceeds 300 lines and Claude starts ignoring content it deems "irrelevant"
- When token cost of CLAUDE.md exceeds 3% of effective working context

**Practical rule:** If you can't read your CLAUDE.md in 60 seconds, it's too long.

Sources:
- [code.claude.com/docs/en/memory](https://code.claude.com/docs/en/memory)
- [code.claude.com/docs/en/costs](https://code.claude.com/docs/en/costs)
- [HumanLayer blog](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [Prompt Shelf: Token Budget Optimization](https://thepromptshelf.dev/blog/claude-md-token-budget-optimization/)

---

## 7. Gap Analysis: Current Tier 1 Content

### Current content (SYSTEM-PROMPT.md, 47 lines including the `---` separator):

**Strengths:**
- Concise (~40 lines of actual content) --- within budget
- Well-structured with clear headers
- "Core behavior" section is tight and actionable
- Git hygiene rules are practical and specific
- State file policy is a good universal rule

**Recommended ADDITIONS:**

1. **Testing/verification expectation:**
   > Add: `- **Verify your work.** Run tests, check types, or validate output before declaring a task complete. Don't leave the user to find your mistakes.`
   > Rationale: Anthropic's #1 best practice is "give Claude a way to verify its work." The current Tier 1 says nothing about self-verification.

2. **Context management hint:**
   > Add: `- **Stay focused.** Don't read files speculatively or explore broadly without reason. Context is finite --- use it on what matters for the current task.`
   > Rationale: Prevents the "infinite exploration" anti-pattern flagged in official docs.

3. **Error handling / asking for help:**
   > Add: `- **Ask rather than guess.** If a task requires credentials, paths, or decisions you don't have, ask the user. Don't invent plausible-sounding answers.`
   > Rationale: Prevents confabulation on machine-specific details (especially important when workers span machines).

**Recommended SUBTRACTIONS:**

1. **Lines 44-47 ("Repo-specific conventions" header + separator):**
   ```
   ## Repo-specific conventions
   
   If this repo adds further conventions, they appear below this block.
   
   ---
   ```
   > Remove from Tier 1. This is deployment scaffolding, not an instruction. Each repo's Tier 3 file can have its own section header. This wastes 4 lines of token budget on meta-commentary that Claude doesn't need.

2. **Consider trimming state file section:**
   > The "State files may include JSON logs, SQLite databases..." sentence is descriptive rather than instructive. Claude doesn't need to know what formats exist --- it needs the rule "don't hand-edit." Consider condensing to one bullet:
   > `- If a repo has a `state/` directory, treat it as authoritative. Mutate only through the repo's documented API --- never hand-edit.`

---

## 8. Tier 2 Content Template and Worked Examples

### Template

```markdown
# Machine: <machine-name>

## Role
<One sentence: primary dev / email+DocDB host / GPU compute worker / guest environment>

## Services & Tools
- <List available services: Redis, DocDB, GPU, etc.>
- <Key CLI tools installed: gh, aws, docker, etc.>

## Paths
- Projects: <path>
- AgentForge tasks: <path>
- Python venv: <path or "managed by venvman">

## Privacy Posture
- <What data lives here and what restrictions apply>
- <What must NOT leave this machine>

## Constraints
- <What NOT to do on this machine>
- <Resource limits, if any>
```

### Worked Example A: primary-laptop (macOS, interactive dev)

```markdown
# Machine: primary-laptop

## Role
Primary interactive development machine. Human is present and responsive.

## Services & Tools
- Redis (local, port 6379)
- Docker Desktop available
- gh, git, claude, venvman CLIs installed
- AgentForge orchestrator + workers available

## Paths
- Projects: ~/Dropbox/Projects/
- AgentForge tasks: ~/Dropbox/Jobs/agentforge/tasks
- Python: managed by venvman (Python 3.13+)

## Privacy Posture
- DocDB queries are permitted locally but results must never leave this machine.
- No sensitive content to external services, pastebins, or diagram renderers.

## Constraints
- This is a laptop --- avoid long-running GPU workloads or heavy parallel builds.
- Prefer delegating compute-heavy tasks to h100 via AgentForge.
```

### Worked Example B: email-mac (DocDB host, strict privacy)

```markdown
# Machine: email-mac

## Role
DocDB host, email capture daemon, and AgentForge worker. Primarily headless --- human interaction is infrequent.

## Services & Tools
- DocDB (ProjectDocumentDatabase) running locally
- EmailAssistant capture daemon active
- AgentForge worker pool (1 worker)
- gh, git, venvman CLIs installed

## Paths
- Projects: ~/Dropbox/Projects/
- DocDB data: ~/DocDB/
- AgentForge tasks: ~/Dropbox/Jobs/agentforge/tasks

## Privacy Posture
- STRICT: This machine holds grant proposals, HR correspondence, and NDA-covered content.
- NEVER send email content, DocDB results, attachment text, or database dumps to external services.
- NEVER include document content in git commits, PRs, or task outputs.
- When uncertain whether content is sensitive, treat it as sensitive.

## Constraints
- Do not run resource-intensive builds --- this machine's primary job is email capture.
- Do not restart or interfere with the EmailAssistant daemon.
- AgentForge tasks here should be lightweight (research, document processing).
```

### Worked Example C: h100 (Linux GPU compute, AgentForge worker pool)

```markdown
# Machine: h100

## Role
GPU compute server running AgentForge worker pool. Fully headless --- no human interactive sessions.

## Services & Tools
- NVIDIA H100 GPU (CUDA 12.x)
- AgentForge worker pool (4 workers)
- Docker, conda, venvman, git installed
- No browser, no GUI tools

## Paths
- Projects: ~/projects/
- AgentForge tasks: ~/jobs/agentforge/tasks
- Model weights: /data/models/
- Scratch space: /scratch/ (not backed up)

## Privacy Posture
- No sensitive documents on this machine.
- Standard code privacy: don't leak API keys or credentials in outputs.

## Constraints
- GPU memory is shared across workers --- avoid loading multiple large models simultaneously.
- /scratch/ is ephemeral; persist important outputs to ~/projects/ or commit to git.
- No Dropbox sync --- file delivery uses AgentForge's cross-machine queue.
- Network egress is unrestricted but expensive --- avoid large downloads without reason.
```

---

## Summary of Recommendations for the 3-Tier System

1. **Tier 1** should be 25-35 lines of behavioral norms. Add self-verification and "ask don't guess" rules. Remove meta-scaffolding.
2. **Tier 2** should be 15-25 lines per machine. Role, services, paths, privacy, constraints. Keep it factual, not philosophical.
3. **Tier 3** stays as-is per repo. Ensure each is under 200 lines; use `.claude/rules/` for overflow.
4. Combined Tier 1 + Tier 2 in `~/.claude/CLAUDE.md` should stay under 60 lines total --- well within the "under 200" official limit and the "under 2,000 tokens" ideal.
5. Deploy Tier 1 from ClaudeCommands as source-of-truth; concatenate with machine-specific Tier 2 during setup.
