# Global preferences — Chris Henry, Argonne National Laboratory

I am a computational biologist building an AI-assisted development platform. My core repos live in `~/Dropbox/Projects/` and sync across machines via Dropbox.

## Collaboration style

- Be direct and concise. Lead with the answer, not the reasoning.
- Don't summarize what you just did at the end of responses — I can read the diff.
- When I say "do X", do X. Don't ask for confirmation unless the action is destructive or ambiguous.
- I prefer bundled PRs over many small ones when the changes are logically related.

## Project ecosystem

- **AIAssistant** — the AI Platform brain: project registry, sessions, action items, audits, AgentForge coordination.
- **AgentForge** — multi-agent task orchestrator with file-based handoff workers.
- **EmailAssistant** — email retrieval, processing, project matching, task extraction.
- **KBUtilLib** — composable utility framework for KBase/ModelSEED bioinformatics.
- **ClaudeCommands** — curated library of universal Claude skills (cursor-setup, jupyter-dev, create-new-project). Deploy commands have been removed; skills are managed per-repo now.

## Key constraints

- Email and document databases contain sensitive grant/HR/NDA content. Never send their contents to external services.
- AgentForge workers spawn with `--repo <target>` and inherit the target repo's `.claude/commands/`. Don't duplicate skills across repos for worker access.
- The project registry (`AIAssistant/state/project_registry.yaml`) is the master of project definitions, not ClaudeCommands' legacy `data/projects.json`.
