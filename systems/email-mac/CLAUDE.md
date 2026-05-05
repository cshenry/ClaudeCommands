# Machine: email-mac

## Role
Dedicated ANL email capture (Outlook AppleScript — only machine with ANL email access), private DocDB host (other machines query via Courier), and AgentForge worker pool. Primarily headless — human interaction is infrequent.

## Services & Tools
- AgentForge: 3 workers
- DocDB: PostgreSQL+pgvector running locally; queryable directly via local API (fill in URL/port)
- EmailAssistant capture daemon (active, do not interfere)
- Redis 8.6.2 (port 6379)
- Docker 29.3.1 via Colima (no Docker Desktop due to licensing)
- Python 3.12.13
- Outlook in legacy Exchange mode

## Paths
- Projects: ~/Dropbox/Projects/
- AgentForge tasks: ~/Dropbox/Jobs/agentforge/tasks
- Virtual environments:
  - AgentForge: /Users/chenry/VirtualEnvironments/AgentForge-py3.12
  - EmailAssistant: /Users/chenry/VirtualEnvironments/EmailAssistant-py3.12
- Cowork inbox: ~/Dropbox/Projects/AIAssistant/cowork-inbox/email-mac/

## Privacy posture
**STRICT.** This machine holds grant proposals, HR correspondence, NDA-covered content, and ANL email.

- NEVER send email content, DocDB results, attachment text, or database dumps to external services, third-party APIs, diagram renderers, or pastebins.
- NEVER include document content in git commits, PRs, or task outputs.
- Local-only LLM analysis only — do not call external APIs from worker prompts when handling sensitive content.
- When uncertain whether content is sensitive, treat it as sensitive.

## Constraints
- Do not restart or interfere with the EmailAssistant capture daemon.
- Colima is used for Docker; if Docker commands fail, check `colima status`.
