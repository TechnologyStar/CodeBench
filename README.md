# CodeBench — AI Coding Agent Evaluation Framework

A lightweight, API-first framework for evaluating AI coding agents (Claude Code, OpenAI Codex, etc.) with sandboxed code execution, bug detection, and a built-in Web UI.

Built on top of [OpenCompass](https://github.com/open-compass/opencompass) by [Shanghai AI Laboratory](https://www.shanghaitech.edu.cn/). This project extends the original evaluation infrastructure with modern coding agent workflows, sandboxed execution, and a streamlined API server.

## Features

- **Multi-Provider Support** — Claude API, Gemini API, OpenAI Responses API, OpenAI Chat Completions
- **Coding Agent Wrappers** — Pluggable agent evaluation (Claude Code, Codex, custom)
- **Sandboxed Execution** — Subprocess & Docker isolation with timeout/memory limits
- **Bug Detection** — Regex-based error pattern matching with severity classification and fix suggestions
- **Task Management** — Pause/resume/retry with checkpoint recovery
- **REST API** — Lightweight HTTP server (stdlib only, zero extra dependencies)
- **Web UI** — Optional dark-theme dashboard (`--enable-ui`)
- **Comprehensive Tests** — 30+ unit tests

## Quick Start

```bash
# Install dependencies (only for agent API integrations)
pip install anthropic google-generativeai openai

# Start the API server
python -m opencompass.server --port 8000

# Or with Web UI enabled
python -m opencompass.server --port 8000 --enable-ui
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/models` | List available models |
| POST | `/api/v1/evaluate` | Submit model evaluation |
| POST | `/api/v1/agent/evaluate` | Submit coding agent evaluation |
| POST | `/api/v1/sandbox/execute` | Execute code in sandbox |
| GET | `/api/v1/tasks/{id}` | Query task status |
| POST | `/api/v1/tasks/{id}/pause` | Pause a running task |
| POST | `/api/v1/tasks/{id}/resume` | Resume a paused task |
| POST | `/api/v1/tasks/{id}/retry` | Retry a failed task |
| GET | `/api/v1/tasks/{id}/bugs` | Get bug detection report |
| GET | `/` | Web UI (if `--enable-ui`) |

## Project Structure

```
├── opencompass/
│   ├── agents/          # Coding agent wrappers (Claude Code, Codex)
│   ├── sandbox/         # Sandboxed code execution (subprocess, Docker)
│   ├── models/          # Model providers (Claude, Gemini, OpenAI, etc.)
│   ├── bug_detector.py  # Automated bug analysis
│   ├── task_manager.py  # Task lifecycle management
│   ├── server.py        # REST API server
│   └── ui/              # Web UI (static files)
├── tests/
│   ├── test_sandbox.py
│   └── test_agents.py
└── docs/
    └── GUIDE.md         # Detailed development guide
```

## Testing

```bash
python -m pytest tests/test_sandbox.py tests/test_agents.py -v
```

## Acknowledgments

This project is built on [OpenCompass](https://github.com/open-compass/opencompass), an open-source evaluation framework developed by [Shanghai AI Laboratory (上海人工智能实验室)](https://www.shanghaitech.edu.cn/). We extend our sincere gratitude to the OpenCompass team for their foundational work in LLM evaluation infrastructure.

## License

Apache License 2.0 — See [LICENSE](LICENSE) for details.
