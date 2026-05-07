# API Reference

Complete reference for the CodeBench REST API. Default server address: `http://localhost:8000`.

---

## Base URL

```
http://<host>:<port>/api/v1
```

All endpoints return JSON. Responses use standard HTTP status codes.

---

## Common Response Headers

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json; charset=utf-8` |

---

## Error Format

All errors follow a consistent structure:

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE"  // optional
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 200 | Success |
| 400 | Invalid request body or parameters |
| 404 | Resource not found |
| 405 | Method not allowed |
| 500 | Internal server error |

---

## Endpoints

### `GET /api/v1/health`

Health check endpoint. Returns server status and version.

**Response:**

```json
{
  "status": "ok"
}
```

---

### `GET /api/v1/models`

List all available model providers and their configurations.

**Response:**

```json
{
  "models": [
    {
      "name": "claude-sonnet-4-20250514",
      "provider": "claude",
      "api_base": "https://api.anthropic.com",
      "capabilities": ["chat", "vision"]
    }
  ]
}
```

---

### `POST /api/v1/evaluate`

Submit a direct model evaluation task. The model generates text given a prompt, and the result is recorded.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | string | Yes | Model identifier (e.g., `"claude-sonnet-4-20250514"`) |
| `prompt` | string | Yes | Evaluation prompt |
| `max_tokens` | integer | No | Maximum output tokens (default: 1024) |
| `temperature` | float | No | Sampling temperature (default: 0.0) |

**Example:**

```json
{
  "model": "claude-sonnet-4-20250514",
  "prompt": "Explain the difference between a list and a tuple in Python.",
  "max_tokens": 512
}
```

**Response:**

```json
{
  "task_id": "a1b2c3d4",
  "status": "pending"
}
```

---

### `POST /api/v1/agent/evaluate`

Submit a coding agent evaluation. The agent generates code, which is then executed in a sandbox and tested.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_type` | string | Yes | Agent identifier: `"claude"`, `"codex"`, or custom |
| `model` | string | Yes | Underlying model name |
| `api_key` | string | Yes | API key for the model provider, or `"ENV"` to read from environment variable |
| `base_url` | string | No | Custom API endpoint URL |
| `task` | object | Yes | Coding task definition (see below) |

**`task` object:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | Yes | Natural language description of the coding task |
| `language` | string | Yes | Programming language (`python`, `javascript`, `java`, `cpp`, `bash`) |
| `test_cases` | array | Yes | List of test case objects (see below) |
| `context` | string | No | Additional context (existing code, file descriptions) |
| `difficulty` | string | No | Difficulty level: `"easy"`, `"medium"` (default), `"hard"` |
| `max_tokens` | integer | No | Max tokens for code generation (default: 4096) |
| `timeout` | integer | No | Per-test timeout in seconds (default: 30) |

**`test_cases` item:**

```json
{"code": "assert solution(2, 3) == 5"}
```

or for input/output tests:

```json
{"input": "2\n3", "expected": "5"}
```

**Full Example:**

```json
{
  "agent_type": "claude",
  "model": "claude-sonnet-4-20250514",
  "api_key": "sk-ant-...",
  "task": {
    "description": "Implement a function `solution(a, b)` that returns the sum of two integers.",
    "language": "python",
    "difficulty": "easy",
    "test_cases": [
      {"code": "assert solution(2, 3) == 5"},
      {"code": "assert solution(-1, 1) == 0"},
      {"code": "assert solution(0, 0) == 0"}
    ]
  }
}
```

**Response:**

```json
{
  "task_id": "e5f6g7h8",
  "status": "pending"
}
```

---

### `POST /api/v1/sandbox/execute`

Execute arbitrary code in an isolated sandbox. Useful for debugging and experimentation.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | Yes | Source code to execute |
| `language` | string | Yes | Programming language (`python`, `bash`) |
| `timeout` | integer | No | Execution timeout in seconds (default: 30) |
| `memory_limit` | integer | No | Memory limit in MB (default: 256) |
| `files` | object | No | Map of `filename` → `content` for multi-file execution |

**Example:**

```json
{
  "code": "import math\nprint(math.factorial(10))",
  "language": "python",
  "timeout": 10
}
```

**Response:**

```json
{
  "exit_code": 0,
  "stdout": "3628800\n",
  "stderr": "",
  "timed_out": false,
  "memory_exceeded": false,
  "execution_time": 0.042
}
```

**Error response (execution failed):**

```json
{
  "exit_code": 1,
  "stdout": "",
  "stderr": "Traceback (most recent call last):\n  File \"<string>\", line 1\nNameError: name 'x' is not defined\n",
  "timed_out": false,
  "memory_exceeded": false,
  "execution_time": 0.008
}
```

**Timeout response:**

```json
{
  "exit_code": -1,
  "stdout": "",
  "stderr": "",
  "timed_out": true,
  "memory_exceeded": false,
  "execution_time": 30.001
}
```

---

### `GET /api/v1/tasks/{id}`

Query the status and results of a task.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Task ID returned by evaluate/agent/evaluate |

**Response (task in progress):**

```json
{
  "task_id": "e5f6g7h8",
  "status": "running",
  "type": "agent_evaluate",
  "created_at": 1715078400,
  "started_at": 1715078401,
  "completed_at": null,
  "error": null,
  "result": null
}
```

**Response (task completed):**

```json
{
  "task_id": "e5f6g7h8",
  "status": "completed",
  "type": "agent_evaluate",
  "created_at": 1715078400,
  "started_at": 1715078401,
  "completed_at": 1715078412,
  "error": null,
  "result": {
    "task_id": "e5f6g7h8",
    "agent_name": "claude-code",
    "success": true,
    "total_tests": 3,
    "passed_tests": 3,
    "generated_code": "def solution(a, b):\n    return a + b\n",
    "execution_time": 10.852,
    "tokens_used": 142,
    "error": null
  }
}
```

**Response (task failed):**

```json
{
  "task_id": "e5f6g7h8",
  "status": "failed",
  "type": "agent_evaluate",
  "created_at": 1715078400,
  "started_at": 1715078401,
  "completed_at": 1715078415,
  "error": "Code generation failed: API returned 429 rate limit",
  "result": null
}
```

---

### `POST /api/v1/tasks/{id}/pause`

Pause a running task. The current progress is saved as a checkpoint.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Task ID |

**Response:**

```json
{
  "task_id": "e5f6g7h8",
  "status": "paused",
  "completed_tests": 5,
  "remaining_tests": 15
}
```

---

### `POST /api/v1/tasks/{id}/resume`

Resume a paused task from its last checkpoint.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Task ID |

**Response:**

```json
{
  "task_id": "e5f6g7h8",
  "status": "running",
  "resumed_from_test": 5,
  "remaining_tests": 15
}
```

---

### `POST /api/v1/tasks/{id}/retry`

Create a new task that retries a failed one. Inherits configuration and error history.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Task ID of the failed task |

**Request Body (optional):**

```json
{
  "retry_count": 5,
  "retry_delay": 2.0
}
```

**Response:**

```json
{
  "task_id": "i9j0k1l2",
  "status": "pending",
  "retry_count": 1,
  "message": "Retry task created"
}
```

---

### `GET /api/v1/tasks/{id}/bugs`

Get an automated bug analysis report for a completed task.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Task ID |

**Response:**

```json
{
  "task_id": "e5f6g7h8",
  "summary": {
    "total_bugs": 3,
    "high_severity": 2,
    "medium_severity": 1,
    "low_severity": 0,
    "common_pattern": "name_error",
    "error_types": {
      "name_error": 1,
      "index_error": 1,
      "type_error": 1
    }
  },
  "bugs": [
    {
      "test_index": 1,
      "error_type": "name_error",
      "severity": "high",
      "description": "Variable 'undefined_var' is not defined",
      "suggested_fix": "Check spelling and scope. Ensure 'undefined_var' is defined before use.",
      "confidence": 0.85
    },
    {
      "test_index": 2,
      "error_type": "index_error",
      "severity": "high",
      "description": "list index out of range",
      "suggested_fix": "Add boundary check: if 0 <= index < len(arr):",
      "confidence": 0.9
    },
    {
      "test_index": 3,
      "error_type": "type_error",
      "severity": "medium",
      "description": "unsupported operand type(s) for +: 'int' and 'str'",
      "suggested_fix": "Check types. Use type conversion: int(), str(), float().",
      "confidence": 0.75
    }
  ]
}
```

---

## Task Status Codes

| Status | Description |
|--------|-------------|
| `pending` | Task created, waiting to start |
| `running` | Task is actively executing |
| `paused` | Task paused by user, checkpoint saved |
| `completed` | Task finished successfully |
| `failed` | Task finished with an error |
| `retrying` | A retry task has been created |
| `cancelling` | Task is being cancelled (graceful shutdown) |
| `cancelled` | Task was cancelled before completion |

---

## Rate Limiting

CodeBench does not implement server-side rate limiting. Rate limits are governed by the upstream model providers (Anthropic, Google, OpenAI). The server handles `429 Too Many Requests` from providers by surfacing the error in the task result.

For high-throughput evaluation, consider:
- Using the provider's batch API when available
- Distributing evaluations across multiple API keys
- Setting appropriate delays between requests via `task_manager.py` configuration
