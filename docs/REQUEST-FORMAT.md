# Request File Format

## Purpose

This document defines the standard format for request files passed to Claude Code in headless mode. Request files contain the specific user requirements for a particular command execution.

## File Format

**Format**: JSON
**Filename**: `request.json` (standardized)
**Location**: Working directory

## Schema

```json
{
  "request_type": "string - matches command_type",
  "description": "string - brief description of what user wants",
  "context": {
    // Command-specific context fields
  },
  "constraints": {
    // Optional constraints or preferences
  },
  "previous_context": "string - if resuming from user_query status"
}
```

## Request Types by Command

### create-prd Request

```json
{
  "request_type": "create-prd",
  "description": "Create PRD for user profile editing feature",
  "context": {
    "feature_request": "Add ability for users to edit their profile information including name, email, avatar, and bio",
    "target_users": "End users of the web application",
    "existing_system": "We have a user authentication system and user database"
  },
  "constraints": {
    "technical_stack": "React frontend, Node.js backend, PostgreSQL database",
    "timeline": "2 weeks",
    "complexity": "medium"
  }
}
```

**Required Fields:**
- `feature_request`: Description of the feature to build

**Optional Fields:**
- `target_users`: Who will use this feature
- `existing_system`: Relevant existing components
- `business_goals`: Business objectives
- `technical_constraints`: Known technical limitations
- `design_guidelines`: UI/UX requirements

### generate-tasks Request

```json
{
  "request_type": "generate-tasks",
  "description": "Generate task list for user profile editing PRD",
  "context": {
    "prd_file": "PRDs/0001-user-profile-editing.md",
    "codebase_path": "./src",
    "existing_patterns": "We use React functional components with hooks, Jest for testing"
  },
  "constraints": {
    "task_granularity": "medium",
    "include_testing": true
  }
}
```

**Required Fields:**
- `prd_file`: Path to the PRD to implement

**Optional Fields:**
- `codebase_path`: Where the code lives
- `existing_patterns`: Known patterns to follow
- `task_granularity`: "fine", "medium", or "coarse"
- `include_testing`: Boolean for test tasks

### doc-code-for-dev Request

```json
{
  "request_type": "doc-code-for-dev",
  "description": "Document architecture of the user service",
  "context": {
    "codebase_path": "./src/services/user",
    "focus_areas": ["authentication", "user management", "profile system"],
    "entry_points": ["src/services/user/index.ts"]
  },
  "constraints": {
    "depth": "comprehensive",
    "include_diagrams": false
  }
}
```

**Required Fields:**
- `codebase_path`: Path to code to document

**Optional Fields:**
- `focus_areas`: Specific areas to emphasize
- `entry_points`: Known main files
- `depth`: "overview", "comprehensive", or "deep-dive"
- `include_diagrams`: Whether to create mermaid diagrams

### doc-code-usage Request

```json
{
  "request_type": "doc-code-usage",
  "description": "Document how to use the user API client library",
  "context": {
    "codebase_path": "./client-sdk",
    "interface_type": "library",
    "target_audience": "external developers"
  },
  "constraints": {
    "include_examples": true,
    "example_complexity": "beginner-friendly"
  }
}
```

**Required Fields:**
- `codebase_path`: Path to code to document

**Optional Fields:**
- `interface_type`: "library", "cli", "api", or "mixed"
- `target_audience`: "beginners", "intermediate", "advanced"
- `include_examples`: Boolean
- `example_complexity`: Level of example detail

### free-agent Request

```json
{
  "request_type": "free-agent",
  "description": "Clone the authentication-service repository and organize by module",
  "context": {
    "repository_url": "https://github.com/example/authentication-service",
    "organization_strategy": "Group files by feature module"
  },
  "constraints": {
    "working_directory": "./projects",
    "cleanup_after": false
  }
}
```

**Required Fields:**
- `description`: Natural language description of task

**Optional Fields:**
- Context-specific fields based on the task
- `working_directory`: Where to perform operations
- Any relevant URLs, paths, or identifiers

## Resumption Pattern

When resuming after a `user_query` status, include the previous context:

```json
{
  "request_type": "create-prd",
  "description": "Continue PRD creation with user responses",
  "previous_context": "User was asked clarifying questions about authentication requirements",
  "user_responses": {
    "query_1": "Yes, integrate with existing OAuth system",
    "query_2": {
      "choice_id": "option_b",
      "choice_value": "Support both email/password and social login"
    }
  }
}
```

## Best Practices

### 1. Be Specific
- Provide clear, unambiguous requirements
- Include relevant context
- Specify paths explicitly

### 2. Include Context
- Reference existing systems
- Note technical stack
- Mention known constraints

### 3. Set Expectations
- Indicate desired level of detail
- Specify timeline if relevant
- Note any preferences

### 4. Provide References
- Include file paths
- Provide URLs
- Reference related work

## Validation

Before sending a request, verify:
- âœ… `request_type` matches the command being run
- âœ… Required fields for that command type are present
- âœ… Paths are valid and accessible
- âœ… URLs are complete and correct
- âœ… JSON is valid and well-formed

## Examples by Scenario

### Example 1: New Feature PRD
```json
{
  "request_type": "create-prd",
  "description": "Add real-time notifications system",
  "context": {
    "feature_request": "Users should receive real-time notifications for important events (messages, mentions, updates) with options to customize notification preferences",
    "target_users": "All registered users",
    "existing_system": "We have a user system with profiles and a messaging feature. Backend is Node.js with Express, frontend is React.",
    "business_goals": "Increase user engagement and reduce time to respond to messages"
  },
  "constraints": {
    "technical_stack": "WebSocket or Server-Sent Events, Redis for pub/sub",
    "timeline": "3 weeks",
    "complexity": "high",
    "must_work_offline": true
  }
}
```

### Example 2: Documentation Request
```json
{
  "request_type": "doc-code-for-dev",
  "description": "Document the payment processing system architecture",
  "context": {
    "codebase_path": "./src/payments",
    "focus_areas": [
      "payment gateway integration",
      "transaction processing",
      "refund handling",
      "webhook processing"
    ],
    "entry_points": [
      "src/payments/index.ts",
      "src/payments/gateway/stripe.ts"
    ]
  },
  "constraints": {
    "depth": "comprehensive",
    "include_diagrams": true,
    "prioritize": "data flow and error handling"
  }
}
```

### Example 3: Simple Task
```json
{
  "request_type": "free-agent",
  "description": "Convert all markdown files in docs/ to HTML with styling",
  "context": {
    "source_directory": "./docs",
    "output_directory": "./docs/html",
    "styling": "Use GitHub markdown CSS",
    "preserve_structure": true
  },
  "constraints": {
    "overwrite_existing": false,
    "include_toc": true
  }
}
```
