# CodeBench

**A modern evaluation framework for AI coding agents — sandboxed, extensible, API-first.**

CodeBench provides a complete infrastructure for benchmarking coding AI systems (Claude Code, OpenAI Codex, etc.) with isolated code execution, automated bug analysis, task lifecycle management, and an optional Web UI — all built on a lightweight REST API with zero external dependencies.

Built on top of [OpenCompass](https://github.com/open-compass/opencompass) by [Shanghai AI Laboratory](https://www.shlab.org.cn/).

---

## Why CodeBench

Evaluating AI coding agents is fundamentally different from evaluating text models. You need real code execution, not just token comparison. CodeBench addresses this with:

- **Real sandboxed execution** — Code runs in isolated environments (subprocess or Docker) with configurable timeout and memory limits. No mock execution, no shortcuts.
- **Automatic bug analysis** — When a generated solution fails tests, CodeBench classifies the error type (TypeError, IndexError, NameError, etc.), assigns a severity level, and generates a fix suggestion — all without requiring an external LLM call.
- **Full task lifecycle** — Pause long-running evaluations and resume from checkpoints. Retry failed tasks with exponential backoff. Cancel in-flight work cleanly.
- **Minimal footprint** — The API server uses only Python's standard library (`http.server`). No Flask, no FastAPI, no gunicorn. Deploy it anywhere Python runs.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    REST API Server                    │
│              (stdlib http.server)                     │
│                                                       │
│  POST /evaluate  POST /agent/evaluate  POST /sandbox  │
│  GET  /tasks/{id}   .../pause   .../resume   .../bugs │
└──────┬──────────┬──────────┬──────────┬──────────────┘
       │          │          │          │
  ┌────▼───┐ ┌───▼────┐ ┌──▼─────┐ ┌──▼──────────┐
  │ Models │ │ Agents │ │Sandbox │ │Task Manager │
  │        │ │        │ │        │ │             │
  │ Claude │ │Claude  │ │Sub-    │ │ Checkpoint  │
  │ Gemini │ │Code    │ │process │ │ Retry       │
  │ OpenAI │ │Codex   │ │Docker  │ │ Pause/Resume│
  │ ...    │ │Custom  │ │        │ │             │
  └────────┘ └────────┘ └────────┘ └──────┬──────┘
                                        │
                                  ┌─────▼──────┐
                                  │ Bug Detector│
                                  │             │
                                  │ 16+ error   │
                                  │ patterns    │
                                  │ Severity    │
                                  │ Fix hints   │
                                  └─────────────┘
```

---

## Features

### Multi-Provider Model Support

Evaluate against any major API provider through a unified interface:

| Provider | API Format | Key Capabilities |
|----------|-----------|-----------------|
| **Anthropic Claude** | Messages API (via SDK) | System prompts, vision, streaming, custom base URL |
| **Google Gemini** | Generative AI REST | SystemInstruction, vision, `responseModalities`, custom endpoint |
| **OpenAI** | Chat Completions | Standard chat format with function calling support |
| **OpenAI** | Responses API | New structured response format with tool use |
| **OpenCompass** | 40+ original providers | Full backward compatibility with existing model configs |

Each provider is a standalone module implementing `BaseAPIModel.generate()` and `get_token_len()`. Adding a new provider requires one file, ~150 lines of code.

### Coding Agent Evaluation

Instead of testing raw model outputs, CodeBench evaluates complete agent workflows:

1. **Task submission** — Define a coding task with description, language, difficulty, and test cases.
2. **Code generation** — The agent (Claude Code, Codex, or custom wrapper) generates a solution.
3. **Execution** — The generated code runs in an isolated sandbox.
4. **Verification** — Test cases are evaluated against the sandbox output.
5. **Bug analysis** — Failed tests trigger automated error classification.

### Sandboxed Execution

| Feature | Subprocess Sandbox | Docker Sandbox |
|---------|-------------------|----------------|
| Isolation | Separate process + temp working directory | Full container isolation |
| Timeout | Configurable (default 30s) | Configurable |
| Memory limit | `resource.setrlimit` | Container flag |
| Languages | Python, Bash (extensible) | Any installed in image |
| Dependencies | None | Docker runtime |

### Bug Detection Engine

Analyzes stderr and error messages from failed executions:

- **16+ error patterns** — SyntaxError, TypeError, IndexError, KeyError, NameError, ValueError, ImportError, RuntimeError, TimeoutError, MemoryError, AttributeError, ZeroDivisionError, RecursionError, FileNotFoundError, and more.
- **Severity classification** — Each detected bug is rated `low`, `medium`, `high`, or `critical`.
- **Confidence scoring** — Pattern matching includes a confidence score (0.0–1.0) based on match specificity.
- **Fix suggestions** — High-confidence matches include actionable repair hints (e.g., "Add boundary check: `if 0 <= index < len(arr):`").
- **Aggregate statistics** — Summary reports include total bug count, severity distribution, and the most common error pattern.

### Task Lifecycle

```
  ┌──────────┐    start    ┌──────────┐   complete   ┌───────────┐
  │ PENDING  │────────────▶│ RUNNING  │────────────▶│ COMPLETED │
  └────┬─────┘             └────┬─────┘              └───────────┘
       │                        │
       │                   pause│         ┌───────────┐
       │             ┌──────────▼─────────▶│  PAUSED   │
       │             │                    └─────┬─────┘
       │             │                    resume│
       │             │             ┌──────────▼─────┐    fail    ┌────────┐
       │             │             │   RUNNING      │──────────▶│ FAILED │
       │             │             └────────────────┘           └───┬────┘
       │             │                                           retry│
       │             │                                    ┌────────▼────┐
       │             └───────────────────────────────────▶│  RETRYING   │
       │                                                   └─────────────┘
  cancel│
  ┌─────▼─────┐
  │ CANCELLED │
  └───────────┘
```

- **Checkpoint recovery** — Paused tasks save their progress (completed test indices, partial results). Resuming picks up exactly where it left off.
- **Exponential backoff** — Retries use configurable `initial_delay` and `backoff_factor` (default: 1s × 2^n).
- **Max retries** — Configurable per task (default: 3).

### Web UI

Enable with `--enable-ui`. A single-page dark-theme dashboard served from static files:

- **Dashboard** — Real-time statistics: total tasks, success rate, pass/fail counters.
- **Task list** — Filterable table with pause/resume/retry actions per task.
- **Submit form** — Agent evaluation submission with model, language, difficulty, and test case inputs.
- **Sandbox debugger** — Write code, pick a language, set timeout, and see stdout/stderr/results inline.
- **Bug reports** — Visual breakdown of detected bugs with severity badges and fix suggestions.

The UI communicates exclusively through the same REST API. It adds no server-side dependencies.

---

## Quick Start

### Installation

```bash
git clone https://github.com/TechnologyStar/CodeBench.git
cd CodeBench
```

Core functionality requires only Python 3.10+ and has no pip dependencies.

For agent API integrations (Claude, Gemini, OpenAI):

```bash
pip install anthropic google-generativeai openai
```

### Starting the Server

```bash
# API server only
python -m opencompass.server --port 8000

# With Web UI
python -m opencompass.server --port 8000 --enable-ui
```

### Running Tests

```bash
python -m pytest tests/test_sandbox.py tests/test_agents.py -v
```

All 30 tests pass with zero external dependencies.

---

## API Reference

### Models

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/models` | List all available model providers and their configurations |

### Evaluation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/evaluate` | Submit a direct model evaluation task |
| POST | `/api/v1/agent/evaluate` | Submit a coding agent evaluation (Claude Code / Codex) |

**Agent evaluation request body:**
```json
{
  "agent_type": "claude",
  "model": "claude-sonnet-4-20250514",
  "api_key": "sk-...",
  "base_url": "https://api.example.com/v1",
  "task": {
    "description": "Implement a function that returns the nth Fibonacci number",
    "language": "python",
    "difficulty": "medium",
    "test_cases": [
      {"code": "assert solution(0) == 0"},
      {"code": "assert solution(10) == 55"}
    ]
  }
}
```

### Sandbox

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/sandbox/execute` | Execute arbitrary code in an isolated sandbox |

**Sandbox request body:**
```json
{
  "code": "print(sum(range(1, 101)))",
  "language": "python",
  "timeout": 10
}
```

### Task Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tasks/{id}` | Get task status and results |
| POST | `/api/v1/tasks/{id}/pause` | Pause a running task (saves checkpoint) |
| POST | `/api/v1/tasks/{id}/resume` | Resume a paused task (restores checkpoint) |
| POST | `/api/v1/tasks/{id}/retry` | Create a retry task from a failed one |
| GET | `/api/v1/tasks/{id}/bugs` | Get automated bug analysis report |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Server health check |

---

## Project Structure

```
CodeBench/
├── opencompass/
│   ├── agents/                    # Coding agent wrappers
│   │   ├── base_agent.py          #   BaseCodingAgent (abstract base)
│   │   ├── claudecode_agent.py    #   Claude Code agent wrapper
│   │   └── codex_agent.py         #   OpenAI Codex agent wrapper
│   ├── sandbox/                   # Isolated code execution
│   │   ├── result.py              #   SandboxResult data class
│   │   ├── subprocess_sandbox.py  #   Subprocess isolation
│   │   └── docker_sandbox.py      #   Docker container isolation
│   ├── models/                    # Model provider implementations
│   │   ├── claude_api/            #   Anthropic Claude (Messages API)
│   │   ├── gemini_api.py          #   Google Gemini (Generative AI)
│   │   ├── openai_responses_api.py#   OpenAI Responses API
│   │   └── ...                    #   40+ OpenCompass original providers
│   ├── bug_detector.py            # Automated error analysis engine
│   ├── task_manager.py            # Task lifecycle and checkpoint management
│   ├── server.py                  # REST API server (stdlib)
│   └── ui/                        # Web UI (optional)
│       ├── index.html
│       ├── style.css
│       └── app.js
├── tests/
│   ├── test_sandbox.py            # 14 sandbox tests
│   └── test_agents.py             # 16 agent tests
├── docs/
│   └── GUIDE.md                   # Detailed development guide (1000+ lines)
├── README.md                      # This file
├── README_zh.md                   # Chinese
├── README_ja.md                   # Japanese
├── README_ru.md                   # Russian
├── README_fr.md                   # French
└── LICENSE                        # Apache 2.0
```

---

## Extending CodeBench

### Adding a New Model Provider

Create a file in `opencompass/models/` implementing `BaseAPIModel`:

```python
from opencompass.models.base_api import BaseAPIModel

class MyProvider(BaseAPIModel):
    def generate(self, inputs, max_out_len):
        # Call your API
        return [{'text': response}]

    def get_token_len(self, text):
        # Return token count
        return len(text)  # or use a proper tokenizer
```

### Adding a New Agent Wrapper

Subclass `BaseCodingAgent` from `opencompass/agents/base_agent.py`:

```python
from opencompass.agents.base_agent import BaseCodingAgent

class MyAgent(BaseCodingAgent):
    @property
    def name(self) -> str:
        return "my-agent"

    def generate_code(self, task):
        # Call your agent's API
        code = ...
        tokens = ...
        return code, tokens

    def run_tests(self, code, test_cases, language, timeout):
        # Execute tests in sandbox
        ...
        return passed, total, error
```

### Adding a New Error Pattern

Add an entry to the `PATTERNS` dict in `opencompass/bug_detector.py`:

```python
r'CustomError[:\s]+(.+)': (
    ErrorCategory.CUSTOM,
    ErrorSeverity.HIGH,
    'Suggested fix for this error.'
),
```

---

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| stdlib HTTP server | Zero deployment complexity. Works on any machine with Python 3.10+. No WSGI/ASGI overhead for the expected request volume. |
| Regex-based bug detection | No external LLM calls needed. Deterministic, fast, and consistent. Confidence scoring handles ambiguity. |
| In-memory checkpoints | Server restarts lose task state by design. Production deployments can swap in a persistent backend without changing the API. |
| Separate agent wrappers | Different coding agents have fundamentally different APIs (Anthropic vs OpenAI vs local). A single abstraction would leak implementation details. |
| Optional Web UI | The UI is a consumer of the API, not part of it. Teams that use CodeBench programmatically (CI/CD, batch evaluation) never load it. |

---

## Acknowledgments

CodeBench is built on [OpenCompass](https://github.com/open-compass/opencompass) ([official site](https://opencompass.org.cn/)), an open-source evaluation framework developed by [Shanghai AI Laboratory](https://www.shlab.org.cn/). We extend our sincere gratitude to the OpenCompass team for their foundational work in LLM evaluation infrastructure, which made this project possible.

---

## License

[Apache License 2.0](LICENSE) — Copyright 2024-2025 Shanghai AI Laboratory. Copyright 2025 Sam.
