# Claude Code Headless Execution Examples

## Overview

This document provides complete examples of how to invoke Claude Code in headless mode for each command type. Each example includes the full command-line invocation and the complete set of files needed.

## General Pattern

All headless executions follow this pattern:

```bash
claude code headless \
  --system-prompt /path/to/SYSTEM-PROMPT.md \
  --command /path/to/commands/[command-name].md \
  --request /path/to/request.json \
  --output /path/to/output \
  --working-dir /path/to/project
```

## File Structure

For each execution, you need:

```
project/
├── SYSTEM-PROMPT.md           # Universal system prompt (same for all commands)
├── commands/
│   ├── create-prd.md
│   ├── generate-tasks.md
│   ├── doc-code-for-dev.md
│   ├── doc-code-usage.md
│   └── free-agent.md
├── request.json               # Command-specific request
└── working-dir/               # Where Claude does its work
    └── claude-output.json     # Generated output
```

---

## Example 1: Create PRD

### Request File: `request.json`

```json
{
  "request_type": "create-prd",
  "description": "Create PRD for user profile editing feature",
  "context": {
    "feature_request": "Add ability for users to edit their profile information including name, email, avatar, and bio. Users should be able to update their information from their profile page with real-time validation and immediate visual feedback.",
    "target_users": "End users of the web application, primarily desktop users but should work on mobile",
    "existing_system": "We have a user authentication system using JWT tokens, a PostgreSQL database with a users table, and a React frontend. User data is currently read-only in the profile view.",
    "business_goals": "Improve user engagement by allowing profile customization. Reduce support tickets related to profile information being incorrect."
  },
  "constraints": {
    "technical_stack": "React frontend with TypeScript, Node.js backend with Express, PostgreSQL database",
    "timeline": "2 weeks for development, 1 week for testing",
    "complexity": "medium",
    "must_support": ["image upload", "validation", "error handling"]
  }
}
```

### Command Invocation

```bash
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/create-prd.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./my-project
```

### Expected Output Structure

After execution, you'll find:

```
my-project/
├── agent-io/
│   └── PRD/
│       └── 0001-user-profile-editing.md     # Generated PRD
└── claude-output.json                        # Execution report
```

### Sample Output JSON

```json
{
  "command_type": "create-prd",
  "status": "complete",
  "session_id": "session-20240115-abc123",
  "parent_session_id": null,
  "session_summary": "Created comprehensive PRD for user profile editing feature with 8 functional requirements and 4 user stories",
  "tasks": [
    {
      "task_id": "1.0",
      "description": "Clarify requirements",
      "status": "completed",
      "parent_task_id": null,
      "notes": "No clarification needed - request was comprehensive"
    },
    {
      "task_id": "2.0",
      "description": "Generate PRD content",
      "status": "completed",
      "parent_task_id": null
    },
    {
      "task_id": "3.0",
      "description": "Save PRD file",
      "status": "completed",
      "parent_task_id": null
    }
  ],
  "files": {
    "created": [
      {
        "path": "agent-io/PRD/0001-user-profile-editing.md",
        "purpose": "Product Requirements Document for user profile editing feature",
        "type": "markdown"
      }
    ],
    "modified": [],
    "deleted": []
  },
  "artifacts": {
    "prd_filename": "agent-io/PRD/0001-user-profile-editing.md"
  },
  "comments": [
    "PRD includes 8 functional requirements covering data validation, image upload, and error handling",
    "4 user stories defined for different user personas",
    "Technical considerations note integration with existing JWT authentication",
    "Success metrics include 90% completion rate and 50% reduction in related support tickets",
    "Assumed feature is web-only initially, noted mobile as future enhancement"
  ]
}
```

---

## Example 2: Generate Tasks

### Request File: `request.json`

```json
{
  "request_type": "generate-tasks",
  "description": "Generate implementation tasks for user profile editing PRD",
  "context": {
    "prd_file": "agent-io/PRD/0001-user-profile-editing.md",
    "codebase_path": "./src",
    "existing_patterns": "React functional components with hooks, Express REST API, Jest and React Testing Library for tests, Multer for file uploads"
  },
  "constraints": {
    "task_granularity": "medium",
    "include_testing": true,
    "prioritize_backend_first": true
  }
}
```

### Command Invocation

```bash
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/generate-tasks.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./my-project
```

### Expected Output Structure

```
my-project/
├── agent-io/
│   └── PRD/
│       └── 0001-user-profile-editing.md
└── claude-output.json                   # Contains complete task list
```

### Sample Output JSON (First Phase - Parent Tasks)

```json
{
  "command_type": "generate-tasks",
  "status": "user_query",
  "session_id": "session-20240115-def456",
  "parent_session_id": null,
  "session_summary": "Generated 5 high-level tasks for user profile editing feature implementation",
  "tasks": [
    {
      "task_id": "1.0",
      "description": "Set up data models and database schema",
      "status": "pending",
      "parent_task_id": null
    },
    {
      "task_id": "2.0",
      "description": "Implement backend API endpoints",
      "status": "pending",
      "parent_task_id": null
    },
    {
      "task_id": "3.0",
      "description": "Create frontend components and forms",
      "status": "pending",
      "parent_task_id": null
    },
    {
      "task_id": "4.0",
      "description": "Add validation and error handling",
      "status": "pending",
      "parent_task_id": null
    },
    {
      "task_id": "5.0",
      "description": "Implement tests and documentation",
      "status": "pending",
      "parent_task_id": null
    }
  ],
  "files": {
    "created": [],
    "modified": [],
    "deleted": []
  },
  "queries_for_user": [
    {
      "query_number": 1,
      "query": "I have generated the high-level tasks based on the PRD. Ready to generate sub-tasks? Respond with 'Go' to proceed.",
      "type": "text"
    }
  ],
  "comments": [
    "5 parent tasks identified covering full implementation lifecycle",
    "Tasks prioritized with backend first as requested",
    "Will generate 25-35 sub-tasks once confirmed"
  ],
  "context": "PRD analyzed. Found 8 functional requirements. Existing codebase uses React/Express/PostgreSQL. Identified patterns: React hooks, REST API, Jest testing. Ready to generate detailed sub-tasks."
}
```

### User Response File: `response.json`

User creates a new session that continues from the previous session. Claude Code automatically links sessions via parent_session_id.

```json
{
  "request_type": "generate-tasks",
  "description": "Continue task generation",
  "user_responses": {
    "query_1": "Go"
  }
}
```

Note: The new session will automatically have `parent_session_id: "session-20240115-def456"` which gives Claude access to the full context from Phase 1.

### Command Invocation (Phase 2)

```bash
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/generate-tasks.md \
  --request ./response.json \
  --output ./claude-output.json \
  --working-dir ./my-project
```

### Sample Output JSON (Second Phase - Complete)

```json
{
  "command_type": "generate-tasks",
  "status": "complete",
  "session_id": "session-20240115-ghi789",
  "parent_session_id": "session-20240115-def456",
  "session_summary": "Generated complete task list with 5 parent tasks and 28 sub-tasks for user profile editing feature",
  "tasks": [
    {
      "task_id": "1.0",
      "description": "Set up data models and database schema",
      "status": "pending",
      "parent_task_id": null
    },
    {
      "task_id": "1.1",
      "description": "Add profile fields to users table: avatar_url (VARCHAR), bio (TEXT), updated_at (TIMESTAMP)",
      "status": "pending",
      "parent_task_id": "1.0",
      "notes": "Create migration file in db/migrations/"
    },
    {
      "task_id": "1.2",
      "description": "Create UserProfile model in models/UserProfile.ts",
      "status": "pending",
      "parent_task_id": "1.0",
      "notes": "Follow pattern from models/User.ts, include validation methods"
    },
    {
      "task_id": "2.0",
      "description": "Implement backend API endpoints",
      "status": "pending",
      "parent_task_id": null
    },
    {
      "task_id": "2.1",
      "description": "Create GET /api/users/:id/profile endpoint",
      "status": "pending",
      "parent_task_id": "2.0",
      "notes": "Return user profile data with proper authorization check"
    },
    {
      "task_id": "2.2",
      "description": "Create PUT /api/users/:id/profile endpoint",
      "status": "pending",
      "parent_task_id": "2.0",
      "notes": "Accept name, email, bio updates. Validate input. Check user owns resource."
    },
    {
      "task_id": "2.3",
      "description": "Create POST /api/users/:id/avatar endpoint for image upload",
      "status": "pending",
      "parent_task_id": "2.0",
      "notes": "Use multer middleware. Validate image type/size. Store in uploads/ directory."
    },
    // ... more tasks ...
  ],
  "files": {
    "created": [],
    "modified": [],
    "deleted": []
  },
  "comments": [
    "Generated 5 parent tasks and 28 sub-tasks total",
    "RELEVANT FILES:",
    "- db/migrations/[timestamp]-add-profile-fields.sql - Database schema changes",
    "- src/models/UserProfile.ts - User profile model",
    "- src/models/UserProfile.test.ts - Model tests",
    "- src/api/routes/profile.ts - Profile API endpoints",
    "- src/api/routes/profile.test.ts - API tests",
    "- src/api/middleware/uploadImage.ts - Image upload middleware",
    "- src/components/ProfileEdit.tsx - Profile editing form component",
    "- src/components/ProfileEdit.test.tsx - Component tests",
    "- src/components/AvatarUpload.tsx - Avatar upload component",
    "- src/validation/profileSchema.ts - Validation schemas",
    "Tasks follow existing patterns: React hooks, Express REST, Jest testing",
    "Image uploads use multer as in existing file upload features"
  ]
}
```

---

## Example 3: Document Code Architecture

### Request File: `request.json`

```json
{
  "request_type": "doc-code-for-dev",
  "description": "Document the architecture of the authentication service",
  "context": {
    "codebase_path": "./src/auth",
    "focus_areas": [
      "JWT token generation and validation",
      "User session management",
      "OAuth integration",
      "Password reset flow"
    ],
    "entry_points": [
      "src/auth/index.ts",
      "src/auth/middleware/authenticate.ts"
    ]
  },
  "constraints": {
    "depth": "comprehensive",
    "include_diagrams": false,
    "target_audience": "developers who will extend authentication"
  }
}
```

### Command Invocation

```bash
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/doc-code-for-dev.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./my-project
```

### Expected Output Structure

```
my-project/
├── agent-io/
│   └── docs/
│       └── authentication-service-architecture-documentation.md
└── claude-output.json
```

### Sample Output JSON

```json
{
  "command_type": "doc-code-for-dev",
  "status": "complete",
  "session_id": "session-20240115-jkl012",
  "parent_session_id": null,
  "session_summary": "Created comprehensive architecture documentation for authentication service covering 15 modules and 4 major data flows",
  "files": {
    "created": [
      {
        "path": "agent-io/docs/authentication-service-architecture-documentation.md",
        "purpose": "Architecture documentation for authentication service",
        "type": "documentation"
      }
    ],
    "modified": [],
    "deleted": []
  },
  "artifacts": {
    "documentation_filename": "agent-io/docs/authentication-service-architecture-documentation.md"
  },
  "metrics": {
    "files_analyzed": 47,
    "lines_of_code": 3250
  },
  "comments": [
    "Analyzed 47 files across 6 major modules",
    "Identified layered architecture: routes → services → repositories",
    "JWT tokens use RS256 algorithm with 1-hour expiration",
    "OAuth flow supports Google, GitHub, and Microsoft providers",
    "Session management uses Redis for storage with 7-day TTL",
    "Password reset uses time-limited tokens stored in database",
    "Found middleware chain: rateLimit → authenticate → authorize",
    "Extension point: ProviderStrategy interface for new OAuth providers",
    "Tests use Jest with supertest for API testing",
    "Documentation includes 4 data flow diagrams and dependency graph"
  ]
}
```

---

## Example 4: Document Code Usage

### Request File: `request.json`

```json
{
  "request_type": "doc-code-usage",
  "description": "Create usage documentation for the API client library",
  "context": {
    "codebase_path": "./client-sdk",
    "interface_type": "library",
    "target_audience": "external developers integrating our service"
  },
  "constraints": {
    "include_examples": true,
    "example_complexity": "beginner-friendly",
    "programming_languages": ["JavaScript", "TypeScript", "Python"]
  }
}
```

### Command Invocation

```bash
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/doc-code-usage.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./my-project
```

### Expected Output Structure

```
my-project/
├── agent-io/
│   └── docs/
│       └── api-client-usage-documentation.md
└── claude-output.json
```

### Sample Output JSON

```json
{
  "command_type": "doc-code-usage",
  "status": "complete",
  "session_id": "session-20240115-mno345",
  "parent_session_id": null,
  "session_summary": "Created comprehensive usage documentation with API reference for 42 public methods and 15 complete examples",
  "files": {
    "created": [
      {
        "path": "agent-io/docs/api-client-usage-documentation.md",
        "purpose": "Usage documentation for API client library",
        "type": "documentation"
      }
    ],
    "modified": [],
    "deleted": []
  },
  "artifacts": {
    "documentation_filename": "agent-io/docs/api-client-usage-documentation.md"
  },
  "comments": [
    "Documented 42 public methods across 6 client classes",
    "Created 15 complete working examples covering common use cases",
    "Quick start guide enables first API call in under 5 minutes",
    "Installation instructions for npm, pip, and manual setup",
    "All methods include parameter descriptions and return types",
    "Error handling section covers 8 common error scenarios",
    "Examples are beginner-friendly with extensive comments",
    "Configuration section covers all environment variables and options",
    "Library supports Node.js 14+, Python 3.8+, browsers via CDN"
  ]
}
```

---

## Example 5: Free Agent Task

### Request File: `request.json`

```json
{
  "request_type": "free-agent",
  "description": "Clone the project repository, set up the development environment, and run tests",
  "context": {
    "repository_url": "https://github.com/example/my-project",
    "branch": "develop",
    "setup_steps": [
      "Install dependencies",
      "Copy .env.example to .env",
      "Run database migrations",
      "Run test suite"
    ]
  },
  "constraints": {
    "working_directory": "./projects",
    "node_version": "18.x",
    "verify_tests_pass": true
  }
}
```

### Command Invocation

```bash
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/free-agent.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./workspace
```

### Expected Output Structure

```
workspace/
├── projects/
│   └── my-project/          # Cloned repository
│       ├── .env             # Created from .env.example
│       ├── node_modules/    # Installed dependencies
│       └── ...
└── claude-output.json
```

### Sample Output JSON

```json
{
  "command_type": "free-agent",
  "status": "complete",
  "session_summary": "Successfully cloned repository, set up development environment, and verified all tests pass",
  "files": {
    "created": [
      {
        "path": "projects/my-project/",
        "purpose": "Cloned git repository",
        "type": "code"
      },
      {
        "path": "projects/my-project/.env",
        "purpose": "Environment configuration from .env.example",
        "type": "config"
      }
    ],
    "modified": [],
    "deleted": []
  },
  "artifacts": {
    "git_commit": "a1b2c3d4e5f6..."
  },
  "comments": [
    "Cloned from: https://github.com/example/my-project (branch: develop)",
    "Repository size: 15.3 MB, 234 files",
    "Installed 47 npm dependencies (Node.js 18.17.0)",
    "Created .env file from .env.example template",
    "Applied 12 database migrations successfully",
    "Ran test suite: 156 tests passed, 0 failed (execution time: 23.4s)",
    "Project is ready for development"
  ]
}
```

---

## Example 6: Error Handling

### Request File: `request.json`

```json
{
  "request_type": "free-agent",
  "description": "Run the test suite and fix any failing tests",
  "context": {
    "project_path": "./my-project",
    "test_command": "npm test"
  }
}
```

### Sample Output JSON (With Errors)

```json
{
  "command_type": "free-agent",
  "status": "incomplete",
  "session_summary": "Attempted to run test suite but encountered 3 failing tests that require code changes",
  "files": {
    "created": [],
    "modified": [],
    "deleted": []
  },
  "errors": [
    {
      "message": "Test failed: UserProfile.updateAvatar returns 400 for invalid image",
      "type": "TestFailure",
      "fatal": false,
      "context": "Test expects 400 status code but received 500. Appears to be missing error handling for invalid image types."
    },
    {
      "message": "Test failed: AuthMiddleware rejects expired tokens",
      "type": "TestFailure",
      "fatal": false,
      "context": "Token expiration check is not working correctly. May need to update JWT verification logic."
    }
  ],
  "comments": [
    "Ran test suite: 153 of 156 tests passed",
    "3 tests failed requiring code modifications:",
    "  1. UserProfile.updateAvatar - missing image validation error handling",
    "  2. AuthMiddleware.rejects expired tokens - token expiration logic issue",
    "  3. ProfileAPI.validateEmail - regex pattern not matching edge cases",
    "These failures require code changes in:",
    "  - src/api/routes/profile.ts (image validation)",
    "  - src/auth/middleware/authenticate.ts (token expiration)",
    "  - src/validation/profileSchema.ts (email regex)",
    "Cannot auto-fix as this exceeds free-agent scope",
    "Recommend creating tasks to address each failing test"
  ],
  "context": "Test execution completed. 3 tests failing due to implementation issues. Need code modifications in profile routes, auth middleware, and validation schema."
}
```

---

## Automation Scripts

### Bash Script for Running Commands

```bash
#!/bin/bash
# run-claude-command.sh

SYSTEM_PROMPT="./SYSTEM-PROMPT.md"
COMMAND_DIR="./commands"
REQUEST_FILE="./request.json"
OUTPUT_FILE="./claude-output.json"
WORKING_DIR="./workspace"

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <command-name>"
    echo "Available commands: create-prd, generate-tasks, doc-code-for-dev, doc-code-usage, free-agent"
    exit 1
fi

COMMAND_NAME=$1
COMMAND_FILE="$COMMAND_DIR/$COMMAND_NAME.md"

# Validate command file exists
if [ ! -f "$COMMAND_FILE" ]; then
    echo "Error: Command file not found: $COMMAND_FILE"
    exit 1
fi

# Validate request file exists
if [ ! -f "$REQUEST_FILE" ]; then
    echo "Error: Request file not found: $REQUEST_FILE"
    exit 1
fi

# Run Claude Code
echo "Running command: $COMMAND_NAME"
echo "Request file: $REQUEST_FILE"
echo "Output will be written to: $OUTPUT_FILE"
echo ""

claude code headless \
  --system-prompt "$SYSTEM_PROMPT" \
  --command "$COMMAND_FILE" \
  --request "$REQUEST_FILE" \
  --output "$OUTPUT_FILE" \
  --working-dir "$WORKING_DIR"

# Check result
if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Command completed successfully"
    echo "Output: $OUTPUT_FILE"
    
    # Pretty print status
    STATUS=$(jq -r '.status' "$OUTPUT_FILE")
    echo "Status: $STATUS"
    
    if [ "$STATUS" = "user_query" ]; then
        echo ""
        echo "⚠ User input required. Check $OUTPUT_FILE for queries."
    fi
else
    echo ""
    echo "✗ Command failed"
    exit 1
fi
```

### Usage

```bash
# Make script executable
chmod +x run-claude-command.sh

# Run a command
./run-claude-command.sh create-prd

# Check output
cat claude-output.json | jq '.session_summary'
```

---

## Tips for Production Use

### 1. Logging and Monitoring

```bash
# Add logging
claude code headless \
  --system-prompt ./SYSTEM-PROMPT.md \
  --command ./commands/create-prd.md \
  --request ./request.json \
  --output ./claude-output.json \
  --working-dir ./project \
  --log-file ./logs/run-$(date +%Y%m%d-%H%M%S).log
```

### 2. Timeout Handling

```bash
# Run with timeout
timeout 300 claude code headless ...

# Check exit code
if [ $? -eq 124 ]; then
    echo "Command timed out after 5 minutes"
fi
```

### 3. Chaining Commands

```bash
#!/bin/bash
# Pipeline: Create PRD → Generate Tasks → Document

# Step 1: Create PRD
./run-claude-command.sh create-prd
if [ $? -ne 0 ]; then exit 1; fi

# Step 2: Extract PRD filename from output
PRD_FILE=$(jq -r '.artifacts.prd_filename' claude-output.json)

# Step 3: Update request for generate-tasks
jq --arg prd "$PRD_FILE" '.context.prd_file = $prd' \
   request-template-tasks.json > request.json

# Step 4: Generate tasks
./run-claude-command.sh generate-tasks
```

### 4. Error Recovery

```bash
# Save previous output before retry
if [ -f claude-output.json ]; then
    mv claude-output.json claude-output-$(date +%s).json
fi

# Retry with previous context
if [ -f claude-output-previous.json ]; then
    CONTEXT=$(jq -r '.context' claude-output-previous.json)
    jq --arg ctx "$CONTEXT" '.previous_context = $ctx' \
       request.json > request-with-context.json
fi
```
