# Email Analysis JSON Schema

## Overview

This document describes the structured JSON schema used for email analysis output. The schema captures comprehensive information about analyzed emails including classification, project assignment, task extraction, and draft responses.

## Schema Version

Current version: **1.0**

## File Naming Convention

Email analysis files are saved in the `orchestrator/email-analysis/` directory with the following naming pattern:

```
orchestrator/email-analysis/[NNNN]-[YYYY-MM-DD]-[sender-name].json
```

**Examples**:
- `orchestrator/email-analysis/0001-2025-11-09-jane-doe.json`
- `orchestrator/email-analysis/0042-2025-11-15-john-smith.json`

**Components**:
- `NNNN`: Sequential 4-digit number (0001, 0002, etc.)
- `YYYY-MM-DD`: Date the email was received
- `sender-name`: Sender's name in kebab-case

## Schema Structure

### Top-Level Fields

```json
{
  "email_metadata": { ... },
  "classification": { ... },
  "project_assignment": { ... },
  "tasks": [ ... ],
  "draft_response": { ... },
  "summary": { ... },
  "analysis_metadata": { ... }
}
```

## Field Definitions

### 1. email_metadata

Contains core email information extracted from the original message.

```json
{
  "subject": "string",
  "sender": {
    "name": "string",
    "email": "string"
  },
  "recipients": {
    "to": ["email@example.com"],
    "cc": ["email@example.com"],
    "bcc": ["email@example.com"]
  },
  "date_received": "ISO 8601 datetime",
  "thread_id": "string or null",
  "message_id": "string or null",
  "attachments": ["filename.ext"]
}
```

**Field Details**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `subject` | string | Yes | Email subject line |
| `sender.name` | string | Yes | Sender's display name |
| `sender.email` | string | Yes | Sender's email address |
| `recipients.to` | array[string] | Yes | Primary recipients (can be empty array) |
| `recipients.cc` | array[string] | No | CC recipients |
| `recipients.bcc` | array[string] | No | BCC recipients (if available) |
| `date_received` | string | Yes | ISO 8601 formatted datetime |
| `thread_id` | string/null | No | Email thread identifier |
| `message_id` | string/null | No | Unique message identifier |
| `attachments` | array[string] | No | List of attachment filenames |

---

### 2. classification

AI-generated classification of the email's category, urgency, and sentiment.

```json
{
  "category": "unimportant | personal | professional",
  "confidence": 0.0-1.0,
  "reasoning": "string",
  "urgency_level": "critical | high | medium | low",
  "is_actionable": true/false,
  "sentiment": "positive | neutral | negative | mixed"
}
```

**Field Details**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | enum | Yes | Primary classification category |
| `confidence` | number | Yes | Confidence score (0.0-1.0) |
| `reasoning` | string | Yes | Explanation of classification decision |
| `urgency_level` | enum | Yes | Urgency assessment |
| `is_actionable` | boolean | Yes | Whether email requires action |
| `sentiment` | enum | Yes | Overall tone/sentiment |

**Category Values**:
- `unimportant`: Mass emails, newsletters, low-priority updates
- `personal`: Personal correspondence, non-work related
- `professional`: Work-related, business correspondence

**Urgency Levels**:
- `critical`: Immediate action required, blocking issues (<24 hours)
- `high`: Near-term deadline (1-3 days), important stakeholders
- `medium`: Standard priority (4-7 days), routine requests
- `low`: Long-term deadline (>7 days), informational

---

### 3. project_assignment

Results of RAG database query to assign email to relevant project(s).

```json
{
  "status": "assigned | unassigned | multiple_matches | needs_review | rag_unavailable",
  "primary_project": {
    "project_id": "string or null",
    "project_name": "string or null",
    "similarity_score": 0.0-1.0,
    "match_reasoning": "string"
  },
  "alternative_projects": [
    {
      "project_id": "string",
      "project_name": "string",
      "similarity_score": 0.0-1.0,
      "match_reasoning": "string"
    }
  ],
  "rag_query_used": "string",
  "keywords_extracted": ["string"]
}
```

**Field Details**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | enum | Yes | Assignment status |
| `primary_project.project_id` | string/null | Yes | Unique project identifier |
| `primary_project.project_name` | string/null | Yes | Human-readable project name |
| `primary_project.similarity_score` | number | Yes | Match confidence (0.0-1.0) |
| `primary_project.match_reasoning` | string | Yes | Explanation of match |
| `alternative_projects` | array | No | Alternative project matches |
| `rag_query_used` | string | Yes | Query sent to RAG database |
| `keywords_extracted` | array[string] | Yes | Keywords used for matching |

**Status Values**:
- `assigned`: Successfully matched to a single project
- `unassigned`: No suitable project match found
- `multiple_matches`: Multiple strong matches requiring user review
- `needs_review`: Uncertain match requiring human review
- `rag_unavailable`: RAG database unavailable or error

**Similarity Score Thresholds**:
- `>= 0.8`: Strong match
- `0.5 - 0.79`: Moderate match
- `< 0.5`: Weak match (usually results in unassigned status)

---

### 4. tasks

Array of action items extracted from the email content.

```json
{
  "tasks": [
    {
      "task_id": "string",
      "description": "string",
      "task_type": "review | respond | create | schedule | research | approve | other",
      "owner": "self | sender | other",
      "urgency": "critical | high | medium | low",
      "deadline": {
        "date": "ISO 8601 datetime or null",
        "is_explicit": true/false,
        "original_text": "string or null",
        "suggested_deadline": "ISO 8601 datetime or null"
      },
      "status": "pending",
      "context": "string",
      "dependencies": ["task_id"],
      "estimated_effort": "string"
    }
  ]
}
```

**Field Details**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | Yes | Unique task identifier (T001, T002, etc.) |
| `description` | string | Yes | Clear description of the task |
| `task_type` | enum | Yes | Category of task |
| `owner` | enum | Yes | Who is responsible |
| `urgency` | enum | Yes | Task urgency level |
| `deadline.date` | string/null | No | ISO 8601 deadline if known |
| `deadline.is_explicit` | boolean | Yes | Whether deadline was stated in email |
| `deadline.original_text` | string/null | No | Original deadline text from email |
| `deadline.suggested_deadline` | string/null | No | Suggested deadline if none explicit |
| `status` | string | Yes | Current task status (always "pending" initially) |
| `context` | string | No | Additional context from email |
| `dependencies` | array[string] | No | Task IDs this task depends on |
| `estimated_effort` | string | No | Rough effort estimate |

**Task Types**:
- `review`: Review document, proposal, code, etc.
- `respond`: Respond to question or request
- `create`: Create deliverable, document, report
- `schedule`: Schedule meeting or event
- `research`: Research topic or gather information
- `approve`: Approve or reject proposal
- `other`: Other task types

**Estimated Effort Examples**:
- "15 minutes"
- "1 hour"
- "2 hours"
- "1 day"
- "1 week"

---

### 5. draft_response

AI-generated draft email response with metadata.

```json
{
  "should_respond": true/false,
  "response_urgency": "immediate | today | this_week | no_rush",
  "suggested_subject": "string",
  "draft_body": "string",
  "tone": "formal | professional | casual | friendly | apologetic",
  "requires_attachments": true/false,
  "placeholders": [
    {
      "placeholder": "string",
      "description": "string",
      "location": "string"
    }
  ],
  "key_points_to_address": ["string"]
}
```

**Field Details**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `should_respond` | boolean | Yes | Whether a response is needed |
| `response_urgency` | enum | Yes (if should_respond=true) | How soon to respond |
| `suggested_subject` | string | Yes (if should_respond=true) | Suggested subject line |
| `draft_body` | string | Yes (if should_respond=true) | Full draft email body |
| `tone` | enum | Yes (if should_respond=true) | Appropriate tone for response |
| `requires_attachments` | boolean | Yes | Whether response needs attachments |
| `placeholders` | array | No | User input needed in draft |
| `key_points_to_address` | array[string] | Yes (if should_respond=true) | Points to cover in response |

**Response Urgency**:
- `immediate`: Respond ASAP (within 1-2 hours)
- `today`: Respond within business day
- `this_week`: Respond within 2-3 days
- `no_rush`: Can wait more than 3 days

**Tone Guidelines**:
- `formal`: Very formal business communication
- `professional`: Standard professional tone
- `casual`: Relaxed but professional
- `friendly`: Warm and personable
- `apologetic`: Apologetic or conciliatory

**Placeholders**:
Used to mark where user input is needed in the draft. Format: `[YOUR_INPUT_NEEDED]` or `[YOUR_INPUT_NEEDED: specific instruction]`

---

### 6. summary

High-level summaries and entity extraction.

```json
{
  "one_line": "string",
  "detailed": "string",
  "key_entities": [
    {
      "type": "person | project | document | date | organization | department | amount",
      "value": "string"
    }
  ]
}
```

**Field Details**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `one_line` | string | Yes | Single sentence summary (max 150 chars) |
| `detailed` | string | Yes | Longer summary (2-3 sentences) |
| `key_entities` | array | Yes | Important entities mentioned in email |

**Entity Types**:
- `person`: Person's name
- `project`: Project name or code
- `document`: Document name or reference
- `date`: Important date mentioned
- `organization`: Company or org name
- `department`: Department or team name
- `amount`: Financial amount or quantity

---

### 7. analysis_metadata

Metadata about the analysis process itself.

```json
{
  "analyzed_at": "ISO 8601 datetime",
  "analysis_version": "string",
  "model_used": "string",
  "processing_time_seconds": number,
  "confidence_overall": 0.0-1.0,
  "requires_human_review": true/false,
  "review_reason": "string or null"
}
```

**Field Details**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `analyzed_at` | string | Yes | ISO 8601 timestamp of analysis |
| `analysis_version` | string | Yes | Schema version (e.g., "1.0") |
| `model_used` | string | Yes | AI model identifier |
| `processing_time_seconds` | number | Yes | Time taken to analyze |
| `confidence_overall` | number | Yes | Overall confidence (0.0-1.0) |
| `requires_human_review` | boolean | Yes | Whether human review needed |
| `review_reason` | string/null | No | Why human review is needed |

**Human Review Triggers**:
- Low confidence scores (<0.6)
- Detected sensitive information
- Multiple strong project matches
- Unclear task assignments
- Unusual email patterns

---

## Usage Examples

### Minimal Valid Email Analysis

```json
{
  "email_metadata": {
    "subject": "Quick question",
    "sender": {
      "name": "John Doe",
      "email": "john@example.com"
    },
    "recipients": {
      "to": ["me@example.com"],
      "cc": [],
      "bcc": []
    },
    "date_received": "2025-11-09T10:00:00Z",
    "thread_id": null,
    "message_id": null,
    "attachments": []
  },
  "classification": {
    "category": "personal",
    "confidence": 0.85,
    "reasoning": "Casual inquiry from friend",
    "urgency_level": "low",
    "is_actionable": false,
    "sentiment": "neutral"
  },
  "project_assignment": {
    "status": "unassigned",
    "primary_project": {
      "project_id": null,
      "project_name": null,
      "similarity_score": 0.0,
      "match_reasoning": "Personal email, no project relevance"
    },
    "alternative_projects": [],
    "rag_query_used": "Quick question",
    "keywords_extracted": ["question"]
  },
  "tasks": [],
  "draft_response": {
    "should_respond": false,
    "response_urgency": "no_rush",
    "suggested_subject": null,
    "draft_body": null,
    "tone": "casual",
    "requires_attachments": false,
    "placeholders": [],
    "key_points_to_address": []
  },
  "summary": {
    "one_line": "Personal question from John Doe",
    "detailed": "Casual personal inquiry from John Doe. No action required.",
    "key_entities": [
      {"type": "person", "value": "John Doe"}
    ]
  },
  "analysis_metadata": {
    "analyzed_at": "2025-11-09T10:05:00Z",
    "analysis_version": "1.0",
    "model_used": "claude-sonnet-4-5",
    "processing_time_seconds": 2.1,
    "confidence_overall": 0.85,
    "requires_human_review": false,
    "review_reason": null
  }
}
```

## Validation Rules

### Required Field Validation

1. All top-level objects must be present (even if empty/null)
2. ISO 8601 datetime format for all dates
3. Confidence scores must be between 0.0 and 1.0
4. Enum values must match exactly (case-sensitive)
5. Email addresses must be valid format

### Consistency Rules

1. If `should_respond = false`, draft_response fields can be null
2. If `tasks` is empty array, no deadline information needed
3. If `status = "unassigned"`, primary_project fields should be null
4. If `requires_human_review = true`, review_reason should not be null

### Data Quality

1. `one_line` summary should be under 150 characters
2. `detailed` summary should be 2-3 sentences
3. Task `task_id` should follow pattern: T001, T002, etc.
4. Similarity scores should reflect actual match quality

## Schema Evolution

### Version History

- **v1.0** (2025-11-09): Initial schema release

### Future Considerations

Potential enhancements for future versions:
- Multi-language support
- Calendar integration fields
- Automated follow-up scheduling
- Email importance learning from user feedback
- Integration with other productivity tools
- Enhanced sentiment analysis granularity

## Integration Notes

### RAG Database Requirements

The RAG database should:
- Accept natural language queries
- Return similarity scores with results
- Include project metadata in responses
- Support threshold-based filtering

### Recommended Tools

- **Date Parsing**: Use robust datetime libraries (e.g., date-fns, moment)
- **Validation**: JSON Schema validators
- **Storage**: Document databases (MongoDB) or structured storage (PostgreSQL with JSON columns)
- **Search**: Full-text search on summary and classification fields

## See Also

- [analyze-email command documentation](../commands/analyze-email.md)
- [Example request file](../examples/analyze-email-example.json)
- [Example output file](../examples/analyze-email-output-example.json)
