# Implementation Notes

## Current Status

**Design**: ✅ Complete
**Repository**: ✅ Set up
**Testing**: ⚠️ Conceptual (needs actual headless mode)

## What Exists

This repository contains a complete, production-ready design for a unified Claude Code headless execution system with:

- ✅ Single system prompt (SYSTEM-PROMPT.md)
- ✅ Unified JSON output schema
- ✅ 5 command definitions
- ✅ Complete documentation
- ✅ Example request files
- ✅ Automation scripts

## Implementation Gap

The design assumes a Claude Code headless mode with this interface:

```bash
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/create-prd.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./workspace
```

**However**, the actual Claude Code CLI (as of this implementation) does not have a native `headless` subcommand with this exact interface.

## Current Claude Code CLI Capabilities

The actual `claude` command supports:

```bash
claude [options] [prompt]
  --print                    # Non-interactive mode
  --output-format json       # JSON output
  --system-prompt <file>     # Load system prompt
  --setting-sources          # Control settings
  # ... other options
```

## Implementation Options

### Option 1: Use Wrapper Script (Included)

We've provided `scripts/claude-headless.sh` which adapts the designed interface to work with the current Claude CLI:

```bash
./scripts/claude-headless.sh \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/create-prd.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./workspace
```

**Status**: Implemented but requires testing and refinement

**Pros**:
- Uses existing Claude CLI
- Provides designed interface
- No changes needed to Claude Code

**Cons**:
- Wrapper complexity
- May not perfectly replicate intended behavior
- Depends on current CLI output format

### Option 2: Feature Request to Anthropic

Request a native `claude code headless` command with:
- Structured command file input
- Structured request file input
- Guaranteed JSON output format
- Working directory isolation

**Status**: Not pursued yet

**Pros**:
- Clean, official implementation
- Better integration
- More reliable

**Cons**:
- Depends on Anthropic roadmap
- Unknown timeline

### Option 3: Build Custom CLI Wrapper

Create a standalone tool that:
- Implements the exact designed interface
- Uses Claude API directly (not CLI)
- Provides all designed features

**Status**: Not implemented

**Pros**:
- Full control
- Exact implementation of design
- Can add custom features

**Cons**:
- Requires API key management
- Needs ongoing maintenance
- More complex to deploy

### Option 4: Use as Slash Commands

Convert commands to Claude Code slash commands:

```bash
# .claude/commands/create-prd.md
cat SYSTEM-PROMPT.md
cat commands/create-prd.md
<< inject request context from user >>
```

**Status**: Feasible with current CLI

**Pros**:
- Works with current Claude Code
- Interactive and headless compatible
- No wrapper needed

**Cons**:
- Requires per-project setup
- Less isolated than designed
- Manual request formatting

## Recommended Path Forward

### Phase 1: Validate Design (Current)
- ✅ Complete repository structure
- ✅ Create all documentation
- ✅ Build example files
- 🔄 Test wrapper script with real scenarios

### Phase 2: Practical Implementation
1. Test `claude-headless.sh` wrapper
2. Refine based on actual output
3. Document quirks and limitations
4. Create working examples

### Phase 3: Production Use
1. Choose implementation option based on testing
2. Potentially build custom wrapper if needed
3. Or work with Anthropic on native support
4. Or use slash command approach

## Testing the Current System

### Manual Test

1. Review the design files:
   ```bash
   cat SYSTEM-PROMPT.md
   cat commands/create-prd.md
   cat examples/create-prd-example.json
   ```

2. Try the wrapper (experimental):
   ```bash
   ./scripts/claude-headless.sh \
     --system-prompt ./SYSTEM-PROMPT.md \
     --command ./commands/create-prd.md \
     --request ./examples/create-prd-example.json \
     --output ./test-output.json \
     --working-dir ./test-workspace
   ```

3. Validate output:
   ```bash
   ./scripts/validate-output.sh ./test-output.json
   ```

### Conceptual Test

You can validate the design by:

1. Reading the combined context manually:
   ```bash
   cat SYSTEM-PROMPT.md commands/create-prd.md examples/create-prd-example.json
   ```

2. Running interactive Claude Code with this context:
   ```bash
   claude --system-prompt ./SYSTEM-PROMPT.md
   # Then paste the command and request content
   ```

3. Checking if the output matches the expected format

## What This Repository Provides

Even without a native headless mode, this repository is valuable because:

1. **Standardized format** - Clear structure for requests and outputs
2. **Complete documentation** - Well-documented command patterns
3. **Reusable prompts** - System prompt and commands work in any context
4. **Reference implementation** - Shows what ideal headless mode would look like
5. **Migration ready** - When native headless exists, this is ready to use

## Using the System Today

### As Slash Commands

1. Copy commands to your project:
   ```bash
   mkdir -p .claude/commands
   cp SYSTEM-PROMPT.md .claude/
   cp commands/*.md .claude/commands/
   ```

2. Create a wrapper command:
   ```bash
   # .claude/commands/prd.md
   cat .claude/SYSTEM-PROMPT.md
   cat .claude/commands/create-prd.md

   User request:
   {{ paste request JSON here }}
   ```

3. Use in Claude Code:
   ```bash
   claude
   /prd
   ```

### As Manual Prompts

Simply combine the files manually:
1. Start Claude Code
2. Paste system prompt
3. Paste command definition
4. Paste request
5. Ask for JSON output

### As API Calls

Use the prompts with Claude API:
```python
import anthropic

system_prompt = open('SYSTEM-PROMPT.md').read()
command = open('commands/create-prd.md').read()
request = open('examples/create-prd-example.json').read()

prompt = f"{command}\n\nUser Request:\n{request}"

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    system=system_prompt,
    messages=[{"role": "user", "content": prompt}]
)
```

## Next Steps

1. **Test wrapper script** - Try `claude-headless.sh` with real scenarios
2. **Document findings** - Update this file with test results
3. **Choose implementation** - Decide on best path forward
4. **Iterate** - Refine based on actual usage

## Questions?

See docs/ARCHITECTURE.md for system design details.
See docs/EXAMPLES.md for usage patterns.
See README.md for quick start guide.

---

**Bottom Line**: The design is complete and production-ready. The implementation path depends on how you want to integrate with Claude Code (wrapper, slash commands, API, or native feature).
