# Contributing Guide

Contributions to CodeBench are welcome. This document covers the development workflow, coding standards, and submission process.

---

## Development Environment

### Prerequisites

- Python 3.10+
- Git
- pytest (for running tests)

```bash
pip install pytest pytest-timeout
```

Optional (for agent integrations):

```bash
pip install anthropic google-generativeai openai
```

### Getting the Source

```bash
git clone https://github.com/TechnologyStar/CodeBench.git
cd CodeBench
```

### Running Tests

```bash
# Run all CodeBench tests
python -m pytest tests/test_sandbox.py tests/test_agents.py -v

# Run with coverage (if pytest-cov installed)
python -m pytest tests/test_sandbox.py tests/test_agents.py --cov=opencompass --cov-report=term-missing
```

All 30 tests must pass before submitting a PR.

---

## Project Structure

```
opencompass/
├── agents/           # Coding agent wrappers
├── sandbox/          # Code execution isolation
├── models/           # Model provider implementations
├── ui/               # Web UI (static HTML/CSS/JS)
├── bug_detector.py   # Error pattern analysis
├── task_manager.py   # Task lifecycle management
└── server.py         # REST API server
```

### What Goes Where

| Component | Directory | Description |
|-----------|-----------|-------------|
| New model provider | `models/` | One file per provider, implements `BaseAPIModel` |
| New agent wrapper | `agents/` | One file per agent, subclasses `BaseCodingAgent` |
| New sandbox backend | `sandbox/` | One file per backend, implements the sandbox interface |
| New error pattern | `bug_detector.py` | Add entry to `PATTERNS` dict |
| New API endpoint | `server.py` | Add handler method to `APIHandler` class |
| New UI page | `ui/` | HTML section in `index.html`, JS logic in `app.js`, styles in `style.css` |

---

## Coding Standards

### Python

- **Style:** Follow PEP 8. Use 4-space indentation, 88-character line limit.
- **Type hints:** Use type hints for all public function signatures.
- **Docstrings:** Google-style docstrings for all public classes and methods.
- **Imports:** Group imports in order: stdlib, third-party, local. Use absolute imports.
- **Error handling:** Use specific exceptions. Never use bare `except:`. Log errors before re-raising.

```python
# Good
from typing import Optional

def evaluate_task(task_id: str, timeout: int = 30) -> Optional[dict]:
    """Evaluate a task by ID.

    Args:
        task_id: Unique task identifier.
        timeout: Maximum execution time in seconds.

    Returns:
        Result dict if task completed, None if not found.
    """
    try:
        task = task_manager.get_task(task_id)
    except TaskNotFoundError as e:
        logger.error('Task not found: %s', task_id)
        return None

    # ... rest of implementation

# Bad
def evaluate_task(task_id, timeout=30):
    pass
```

### JavaScript (Web UI)

- **Style:** Standard modern JavaScript (ES2020+). No frameworks, no build tools.
- **IIFE wrapper:** All code wrapped in `(function() { ... })();`
- **Naming:** camelCase for variables and functions, PascalCase for constructors.
- **Comments:** JSDoc-style for functions.

### CSS

- **BEM-adjacent:** Use descriptive class names. Prefix component-specific classes with component name.
- **CSS variables:** Define all colors, spacing, and sizes as CSS custom properties in `:root`.
- **No inline styles:** All styling in `style.css`.

---

## Adding a New Model Provider

### Step 1: Create the provider file

Create `opencompass/models/my_provider.py`:

```python
"""MyProvider model implementation."""

import logging
from typing import Dict, List, Optional

from opencompass.models.base_api import BaseAPIModel

logger = logging.getLogger(__name__)


class MyProvider(BaseAPIModel):
    """Model provider for MyProvider API.

    Args:
        api_key: API key for authentication.
        model: Model identifier.
        api_base: Base URL for the API endpoint.
        max_seq_len: Maximum sequence length.
        temperature: Sampling temperature.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = 'my-model',
        api_base: str = 'https://api.myprovider.com/v1',
        max_seq_len: int = 4096,
        temperature: float = 0.0,
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip('/')
        self.max_seq_len = max_seq_len
        self.temperature = temperature
        self.timeout = timeout

    def generate(self, inputs: List[Dict], max_out_len: int) -> List[Dict]:
        """Generate completions for the given inputs.

        Args:
            inputs: List of input dicts with 'prompt' key.
            max_out_len: Maximum output length in tokens.

        Returns:
            List of dicts with 'text' key containing generated text.
        """
        results = []
        for inp in inputs:
            prompt = inp.get('prompt', '')
            try:
                response = self._call_api(prompt, max_out_len)
                results.append({'text': response})
            except Exception as e:
                logger.error('Generation failed: %s', e)
                results.append({'text': f'Error: {e}'})
        return results

    def get_token_len(self, text: str) -> int:
        """Return approximate token count for the text."""
        return len(text) // 4  # rough estimate; use proper tokenizer if available

    def _call_api(self, prompt: str, max_tokens: int) -> str:
        """Make API request. Implement HTTP call here."""
        import urllib.request
        import json

        payload = json.dumps({
            'model': self.model,
            'prompt': prompt,
            'max_tokens': max_tokens,
            'temperature': self.temperature,
        }).encode()

        req = urllib.request.Request(
            f'{self.api_base}/generate',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}',
            },
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read())
            return data['output']
```

### Step 2: Register the model

Add to `opencompass/models/__init__.py`:

```python
from .my_provider import MyProvider  # noqa: F401
```

### Step 3: Add tests

Create test cases in `tests/test_my_provider.py`:

```python
import pytest
from unittest.mock import patch

class TestMyProvider:
    def test_generate_success(self):
        """Test successful generation."""
        # Implementation here
        pass

    def test_generate_api_error(self):
        """Test handling of API errors."""
        # Implementation here
        pass

    def test_token_length(self):
        """Test token counting."""
        # Implementation here
        pass
```

### Step 4: Verify

```bash
python -m pytest tests/test_my_provider.py -v
```

---

## Adding a New Agent Wrapper

### Step 1: Subclass BaseCodingAgent

Create `opencompass/agents/my_agent.py`:

```python
"""MyAgent wrapper for coding evaluation."""

import logging
from typing import Tuple, Optional, List, Dict

from .base_agent import BaseCodingAgent, AgentTask, AgentResult

logger = logging.getLogger(__name__)


class MyCodingAgent(BaseCodingAgent):
    """Wrapper for MyAgent coding service.

    Args:
        api_key: Authentication key.
        model: Model to use.
        base_url: Custom API endpoint.
    """

    @property
    def name(self) -> str:
        return "my-agent"

    def generate_code(self, task: AgentTask) -> Tuple[str, int]:
        """Generate code for the given task.

        Args:
            task: The coding task to solve.

        Returns:
            Tuple of (generated_code, tokens_used).
        """
        # Call your agent's API here
        prompt = self._build_prompt(task)
        code, tokens = self._call_agent_api(prompt)
        return code, tokens

    def run_tests(
        self,
        code: str,
        test_cases: List[Dict],
        language: str,
        timeout: int = 30,
    ) -> Tuple[int, int, Optional[str]]:
        """Run test cases against generated code.

        Args:
            code: Generated source code.
            test_cases: List of test case dicts.
            language: Programming language.
            timeout: Per-test timeout.

        Returns:
            Tuple of (passed, total, error_message).
        """
        from opencompass.sandbox import create_sandbox

        sandbox = create_sandbox()
        passed = 0
        total = len(test_cases)
        last_error = None

        for i, test in enumerate(test_cases):
            test_code = test.get('code', '')
            full_code = f"{code}\n{test_code}"

            result = sandbox.execute(full_code, language=language, timeout=timeout)

            if result.exit_code == 0 and not result.timed_out:
                passed += 1
            else:
                last_error = result.stderr

        return passed, total, last_error

    def _build_prompt(self, task: AgentTask) -> str:
        """Build the prompt for the agent."""
        parts = [
            f"Language: {task.language}",
            f"Difficulty: {task.difficulty}",
            f"\nTask: {task.description}",
        ]
        if task.context:
            parts.append(f"\nContext:\n{task.context}")
        return "\n".join(parts)

    def _call_agent_api(self, prompt: str) -> Tuple[str, int]:
        """Call the agent API. Implement your HTTP logic here."""
        # Return (code, tokens)
        raise NotImplementedError
```

### Step 2: Register

Add to `opencompass/agents/__init__.py`:

```python
from .my_agent import MyCodingAgent  # noqa: F401
```

### Step 3: Test

Add tests to `tests/test_agents.py` following the existing pattern.

---

## Pull Request Process

1. **Fork** the repository and create a feature branch from `main`.
2. **Write code** following the coding standards above.
3. **Add tests** for new functionality. All existing tests must continue to pass.
4. **Update documentation** if adding new features, endpoints, or configuration options.
5. **Commit** with clear, descriptive messages (use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`).
6. **Push** and open a Pull Request.

### PR Checklist

- [ ] All existing tests pass (`python -m pytest tests/test_sandbox.py tests/test_agents.py -v`)
- [ ] New tests added for new functionality
- [ ] Docstrings on all public classes and methods
- [ ] No secrets, API keys, or credentials in code
- [ ] Documentation updated (README, GUIDE.md, or API_REFERENCE.md)

---

## Reporting Issues

When reporting bugs, please include:

1. **Python version** (`python --version`)
2. **OS and version**
3. **Minimal reproduction code**
4. **Expected vs actual behavior**
5. **Full error traceback** (if applicable)

Use the [GitHub Issues](https://github.com/TechnologyStar/CodeBench/issues) page.

---

## License

By contributing to CodeBench, you agree that your contributions will be licensed under the Apache License 2.0.
