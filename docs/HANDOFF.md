# Project Handoff: Claude Code Headless System

## Session Context

**Date**: October 30, 2024  
**Original Session**: Claude.ai web interface  
**Continuation**: Claude Code on your server  
**Project Status**: Design complete, ready for implementation

## What We Built

We redesigned your Claude Code headless execution system from scratch to be unified and consistent.

### The Problem You Had
- Multiple inconsistent output formats across commands
- Tasks tracked in separate markdown files  
- PRDs saved in wrong directory (`/tasks` instead of `PRDs/`)
- Duplicate instructions across command files
- No standard way to track file operations
- Inconsistent patterns across commands

### The Solution We Created

**Unified System with:**
1. Single JSON output format for ALL commands
2. Single system prompt used by all commands
3. Tasks tracked IN the JSON output (not separate files)
4. PRDs saved to `PRDs/` directory
5. Complete file operation tracking
6. Stateful resumption support
7. Comprehensive documentation

### Files Created

All files are in `/mnt/user-data/outputs/`:

**Core System:**
- `SYSTEM-PROMPT.md` - Universal instructions (CRITICAL - use in every execution)
- `unified-output-schema.json` - Single output schema
- `commands/` - 5 command definitions (create-prd, generate-tasks, doc-code-for-dev, doc-code-usage, free-agent)

**Documentation:**
- `INDEX.md` - Start here guide
- `SUMMARY.md` - System overview and migration
- `ARCHITECTURE.md` - Complete system design
- `HEADLESS-EXAMPLES.md` - 6+ detailed examples
- `request-format.md` - Request file specification

## Key Design Decisions

### 1. Two-File Input Pattern
Every execution needs:
- Command file (what type of activity)
- Request file (specific requirements)
- Plus system prompt (universal instructions)

### 2. Unified Output Format
```json
{
  "command_type": "create-prd",
  "status": "complete|incomplete|user_query|error",
  "session_summary": "what happened",
  "tasks": [...],        // Tasks with status tracking
  "files": {...},        // All file operations documented
  "artifacts": {...},    // Command-specific outputs
  "comments": [...]      // Important notes
}
```

### 3. Task Management
- Tasks stored IN the JSON output
- Hierarchical (parent/child) structure
- Status tracking per task
- NO separate markdown files

### 4. File Tracking
- Every file operation documented
- Created/modified/deleted arrays
- Purpose and type for each file
- Complete audit trail

### 5. PRD Location
- PRDs saved to `PRDs/[NNNN]-[name].md`
- Sequence starting from 0001
- Referenced in JSON output artifacts

## Current State

### ✅ Completed
- System design and architecture
- All command files redesigned
- Unified output schema defined
- System prompt created
- Complete documentation written
- Examples and patterns documented

### 🔨 Not Yet Done
- Setting up proper git repository
- Organizing into proper directory structure
- Testing the system with actual Claude Code
- Creating automation scripts
- Building example projects

## Next Steps

### Immediate (What You Should Do Next)

1. **Set Up Git Repository**
   ```bash
   mkdir claude-code-headless-system
   cd claude-code-headless-system
   git init
   ```

2. **Copy Files** (from /mnt/user-data/outputs/)
   ```
   claude-code-headless-system/
   ├── README.md              (copy from INDEX.md or create new)
   ├── SYSTEM-PROMPT.md       (CRITICAL)
   ├── unified-output-schema.json
   ├── docs/
   │   ├── ARCHITECTURE.md
   │   ├── EXAMPLES.md        (from HEADLESS-EXAMPLES.md)
   │   ├── SUMMARY.md
   │   └── REQUEST-FORMAT.md
   ├── commands/
   │   ├── create-prd.md
   │   ├── generate-tasks.md
   │   ├── doc-code-for-dev.md
   │   ├── doc-code-usage.md
   │   └── free-agent.md
   ├── examples/              (NEW - create example requests)
   │   ├── create-prd-example.json
   │   ├── generate-tasks-example.json
   │   └── ...
   └── scripts/               (NEW - automation)
       ├── run-command.sh
       └── validate-output.sh
   ```

3. **Test the System**
   - Create a simple test project
   - Run create-prd command
   - Validate the output JSON
   - Verify PRD is created correctly

4. **Build Automation**
   - Create run-command.sh script
   - Add output validation
   - Build example workflows

### Medium-Term (Future Work)

- Build CI/CD integration examples
- Create project templates
- Add monitoring/logging
- Build dashboard for outputs
- Create more example projects

## How to Continue with Claude Code

### Option 1: Use This Handoff (Recommended)

Give Claude Code this file plus the context below:

```bash
claude code

# Then in the conversation, say:
"I'm continuing work on the Claude Code headless system.
Please read HANDOFF.md for full context on what we built.

I want to:
1. Set up the proper git repository structure
2. Organize the files from /mnt/user-data/outputs/
3. Test the system with a real example
4. Create automation scripts

The files are currently in /mnt/user-data/outputs/ and need to be
organized into a proper project structure as outlined in the handoff doc."
```

### Option 2: Direct Context

If Claude Code supports loading context, you could also just say:

```
I've designed a unified Claude Code headless execution system. Here's what exists:

SYSTEM-PROMPT.md - Universal instructions for all executions
unified-output-schema.json - Single JSON schema
commands/*.md - 5 command definitions
Complete documentation in docs/

Current location: /mnt/user-data/outputs/
Need to: Set up proper git repo and project structure

Key insight: Single system prompt + unified output format + tasks in JSON
```

## Example First Task for Claude Code

```
Help me set up the git repository for the Claude Code headless system.

Current state:
- All files are in /mnt/user-data/outputs/
- Need proper directory structure
- Need README.md
- Need .gitignore
- Need examples/ directory

Please:
1. Create the directory structure
2. Move files from outputs to proper locations
3. Create a proper README.md (different from INDEX.md)
4. Add .gitignore
5. Create an examples/ directory with sample request files
6. Create scripts/ directory with run-command.sh
```

## Important Context for Claude Code

### What Makes This System Different

**Traditional approach:**
- Each command has own output format
- Tasks in separate markdown files
- No standard tracking

**Our approach:**
- Single unified output format
- Tasks in JSON output
- Complete file tracking
- Stateful resumption

### The Key Files

**SYSTEM-PROMPT.md** is the heart of the system:
- Used in EVERY execution
- Defines output format
- Contains core principles
- Commands reference it, don't duplicate it

**Commands are simple:**
- Just define the PROCESS
- Don't define output format (that's in system prompt)
- Focus on "what to do" not "how to report"

### The Execution Pattern

```bash
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/[command-name].md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./workspace
```

## Questions You Might Have

**Q: Can I literally continue this web session in Claude Code?**
A: No, sessions don't transfer between interfaces. But you can give Claude Code full context via this handoff doc.

**Q: Will the new Claude Code instance understand everything we built?**
A: Yes, if you provide this handoff doc and point to the files. Claude can read all the documentation we created.

**Q: What if I want to change something about the design?**
A: Easy! Update SYSTEM-PROMPT.md for output changes, update individual command files for process changes.

**Q: How do I test the system?**
A: See HEADLESS-EXAMPLES.md Example 1 - it has a complete create-prd test case.

## Files You Must Include in Git Repo

### Critical Files (System Won't Work Without These)
- ✅ SYSTEM-PROMPT.md
- ✅ unified-output-schema.json
- ✅ commands/*.md (all 5 command files)

### Important Files (For Understanding/Using System)
- ✅ README.md (create from INDEX.md)
- ✅ docs/ARCHITECTURE.md
- ✅ docs/EXAMPLES.md
- ✅ docs/SUMMARY.md

### Nice to Have
- examples/*.json (sample requests)
- scripts/run-command.sh
- .gitignore
- LICENSE

## .gitignore Recommendations

```gitignore
# Working directories
workspace/
work/
test-projects/

# Output files
claude-output.json
**/claude-output.json

# Generated artifacts (unless you want to track them)
PRDs/
docs/generated/

# OS files
.DS_Store
Thumbs.db

# Editor files
.vscode/
.idea/
*.swp
```

## Command to Start Fresh with Claude Code

```bash
# On your server
cd /path/to/where/you/want/project

# Download or copy this handoff file
# Copy all files from /mnt/user-data/outputs/

# Start Claude Code
claude code

# First message:
"I'm setting up the Claude Code headless execution system.
I have all the design files in /mnt/user-data/outputs/.
Please read HANDOFF.md for full context.

Let's set up the proper git repository structure and get this working."
```

## What You'll Tell Claude Code

Here's a template for your first message:

---

I'm continuing work on a Claude Code headless execution system that was designed in a previous session. The design is complete, and now I need to set it up properly.

**Context:**
- All design files are in `/mnt/user-data/outputs/`
- Read `HANDOFF.md` for full project context
- Read `SUMMARY.md` for system overview
- Read `INDEX.md` for file guide

**Current State:**
- System fully designed
- Documentation complete
- Files need organization into proper git repo

**What I Need:**
1. Set up proper git repository structure
2. Move files to correct locations
3. Create automation scripts
4. Test with a simple example
5. Prepare for team use

**Key System Concepts:**
- Single unified JSON output format (see `unified-output-schema.json`)
- Single system prompt used by all commands (`SYSTEM-PROMPT.md`)
- Tasks tracked in JSON output (not separate files)
- Two-file input pattern: command + request

Please start by reading the handoff doc and then help me organize this into a production-ready repository.

---

## Summary

You have:
- ✅ Complete system design
- ✅ All files created
- ✅ Full documentation
- ✅ Examples and patterns

You need:
- 🔨 Proper git repository structure
- 🔨 Testing and validation
- 🔨 Automation scripts
- 🔨 Team documentation

This handoff doc + the files in `/mnt/user-data/outputs/` contain everything Claude Code needs to continue exactly where we left off.

Good luck with the implementation!
