# Machine: h100

## Role
GPU compute server (poplar.cels.anl.gov, NVIDIA H100), AgentForge worker, embedding host. Fully headless — no human interactive sessions. Receives GPU dispatch from primary-laptop and email-mac via AgentForge.

## Services & Tools
- AgentForge: 1 worker
- NVIDIA H100 GPU
- Docker installed
- Python 3.12 (system)
- Linux (no macOS-specific tools — no AppleScript, no Outlook, no homebrew paths)

## Paths
- Projects: /home/chenry/Dropbox/Projects (Dropbox is synced on this machine)
- AgentForge tasks: /home/chenry/Dropbox/jobs/agentforge/tasks
- AgentForge config: ~/.agentforge/config.yaml (machine_alias=h100)
- Cowork inbox: /home/chenry/Dropbox/Projects/AIAssistant/cowork-inbox/h100/

## Privacy posture
No sensitive documents on this machine. Standard code privacy: don't leak API keys or credentials in outputs.

## Constraints
- This is a shared compute host (poplar.cels.anl.gov) shared with other users — be considerate of GPU memory and disk. Avoid loading multiple large GPU models simultaneously.
- No interactive `/ai-*` sessions here. Those run on primary-laptop and dispatch tasks via AgentForge or cowork-inbox.
- No sudo access — this is a devops-managed machine and we are unprivileged users.
- Persist outputs to Dropbox-synced directories (`/home/chenry/Dropbox/...`) so they reach other machines. Treat `/scratch` and `/tmp` as ephemeral.
- No human watching — when uncertain about a task, fail loudly with a clear error rather than guessing. Do not invent paths or capabilities not verified against this machine's actual environment.
- Linux paths only (no `~/Library/...`, no `/Applications/...`).
