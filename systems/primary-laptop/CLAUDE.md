# Machine: primary-laptop

## Role
Primary interactive development. Human is typically present and responsive. This is the orchestrator — direct work, design sessions, and dispatch of tasks to email-mac and h100 happen here.

## Services & Tools
- AgentForge: 1 worker, daemon active
- Redis 8.6.1 (Homebrew, port 6379)
- Docker 29.0.2 (Homebrew)
- Python 3.11.14 via pyenv shims
- node, gh, git, claude, venvman

## Paths
- Projects: ~/Dropbox/Projects/
- AgentForge tasks: ~/Dropbox/Jobs/agentforge/tasks
- Virtual environments: ~/VirtualEnvironments/
- Cowork inbox: ~/Dropbox/Projects/AIAssistant/cowork-inbox/primary-laptop/

## Privacy posture
Standard. DocDB queries (via Courier to email-mac) are permitted; results stay on this machine. Never send sensitive content (email, grant proposals, NDA-covered work) to external services, pastebins, or diagram renderers.

## Constraints
- This is a laptop — avoid long-running GPU workloads or heavy parallel builds. Delegate compute-heavy tasks to h100 (GPU) or email-mac (general-purpose) via AgentForge.
