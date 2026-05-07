# Bug Detection Reference

Complete reference for the automated bug detection engine in CodeBench.

---

## Overview

The bug detector analyzes stderr and error messages from sandboxed code execution. It uses regex pattern matching to classify errors, assign severity levels, and generate fix suggestions. No external LLM calls are required.

**Module:** `opencompass/bug_detector.py`  
**Class:** `BugDetector`

---

## Usage

### As a Library

```python
from opencompass.bug_detector import BugDetector

detector = BugDetector()

results = [
    {'test_index': 0, 'passed': True, 'exit_code': 0, 'stderr': '', 'stdout': 'ok'},
    {'test_index': 1, 'passed': False, 'exit_code': 1,
     'stderr': "IndexError: list index out of range", 'stdout': ''},
    {'test_index': 2, 'passed': False, 'exit_code': 1,
     'stderr': "TypeError: unsupported operand type(s) for +: 'int' and 'str'", 'stdout': ''},
]

analysis = detector.analyze(task_id='my-task', test_results=results)

print(f"Total bugs: {analysis.summary['total_bugs']}")
for bug in analysis.bugs:
    print(f"  Test #{bug.test_index}: [{bug.severity}] {bug.error_type}")
    print(f"    {bug.description}")
    if bug.suggested_fix:
        print(f"    Fix: {bug.suggested_fix}")
```

### Via API

```
GET /api/v1/tasks/{task_id}/bugs
```

---

## Error Categories

All detected errors are classified into one of the following categories:

| Category | Description |
|----------|-------------|
| `syntax_error` | Python syntax errors detected at parse time |
| `type_error` | Operation applied to incompatible types |
| `index_error` | List/string/tuple index out of bounds |
| `key_error` | Dictionary key not found |
| `name_error` | Variable or function name not defined |
| `value_error` | Correct type but inappropriate value |
| `import_error` | Module or symbol not found on import |
| `runtime_error` | Generic runtime failures |
| `timeout` | Execution exceeded time limit |
| `memory_error` | Execution exceeded memory limit |
| `attribute_error` | Object has no such attribute |
| `zero_division` | Division or modulo by zero |
| `recursion_error` | Maximum recursion depth exceeded |
| `file_error` | File not found or permission denied |

---

## Severity Levels

| Level | Meaning | When Assigned |
|-------|---------|---------------|
| `critical` | Complete failure, no output produced | Sandbox timeout, memory exceeded, import errors that prevent any execution |
| `high` | Definite bug in generated code | NameError, TypeError, IndexError, KeyError on specific test inputs |
| `medium` | Likely bug, may be environment-specific | ValueError, AttributeError, RecursionError |
| `low` | Possible issue, low confidence match | Pattern matched with low specificity, or error message partially matched |

---

## Detected Patterns

### Syntax Errors

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| `SyntaxError: invalid syntax` | HIGH | None (requires code rewrite) |
| `SyntaxError: unexpected EOF` | HIGH | None |
| `IndentationError: unexpected indent` | HIGH | "Check indentation consistency. Python uses 4-space indentation." |
| `IndentationError: expected an indented block` | MEDIUM | "Add the required indented block after the statement (e.g., use `pass` as placeholder)." |

### Type Errors

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| `TypeError: unsupported operand type(s) for` | HIGH | "Check operand types before operation. Use type conversion: int(), str(), float()." |
| `'NoneType' object is not (callable\|subscriptable\|iterable)` | HIGH | "Check for None values before accessing attributes or calling methods. Add: `if x is not None:`" |
| `'(.+?)' object is not (callable\|subscriptable\|iterable)` | MEDIUM | None |
| `missing .+ required positional argument` | MEDIUM | "Check function signature. Ensure all required arguments are passed." |

### Index Errors

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| `IndexError: list index out of range` | HIGH | "Add boundary check: `if 0 <= index < len(arr):`" |
| `IndexError: string index out of range` | MEDIUM | "Check string length before accessing index." |

### Key Errors

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| `KeyError: '(.+)'` | HIGH | "Use `.get()` method or check key existence: `if key in dict:`" |

### Name Errors

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| `NameError: name '(.+)' is not defined` | HIGH | "Variable '{name}' is not defined. Check spelling and scope." |

### Value Errors

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| `ValueError: invalid literal for int()` | MEDIUM | "Ensure the string can be converted. Handle exceptions: `try: int(s) except ValueError:`" |
| `ValueError: math domain error` | MEDIUM | "Check input values. Ensure non-negative for sqrt(), valid range for log()." |

### Import Errors

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| `ModuleNotFoundError: No module named '(.+)'` | HIGH | "Install the required module: `pip install {module}`" |
| `ImportError: cannot import name '(.+)'` | MEDIUM | "The symbol does not exist in this module version. Check the module documentation." |

### Attribute Errors

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| `AttributeError: '(.+)' object has no attribute '(.+)'` | MEDIUM | "Check that the object type is correct and the attribute exists." |

### Runtime Errors

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| `ZeroDivisionError` | HIGH | "Add a check: `if denominator != 0:` before division." |
| `RecursionError: maximum recursion depth exceeded` | MEDIUM | "Add a base case or increase recursion limit with `sys.setrecursionlimit()`." |
| `FileNotFoundError` | HIGH | "Check the file path. Ensure the file exists or create it before accessing." |
| `PermissionError` | MEDIUM | "Check file/directory permissions." |
| `ConnectionError` | HIGH | None (environment issue) |
| `429` / `rate_limit` | HIGH | None (API rate limit) |

### Timeout / Memory

| Pattern | Severity | Auto-Fix |
|---------|----------|----------|
| Timed out (`timed_out=True` in result) | CRITICAL | "Reduce problem complexity or increase timeout limit." |
| Memory exceeded (`memory_exceeded=True` in result) | CRITICAL | "Reduce memory usage. Avoid loading large datasets into memory." |

---

## Confidence Scoring

Each bug match includes a confidence score between 0.0 and 1.0:

| Score Range | Meaning |
|-------------|---------|
| 0.9 - 1.0 | Exact match. The error message directly corresponds to a known pattern. |
| 0.7 - 0.9 | High confidence. The pattern matched with captured groups providing additional context. |
| 0.5 - 0.7 | Medium confidence. Partial match or generic pattern. |
| 0.3 - 0.5 | Low confidence. Broad pattern that could match multiple error types. |

Confidence is calculated based on:
- Pattern specificity (more specific patterns score higher)
- Number of captured groups that matched
- Whether the full error message matched (not just a substring)

---

## Analysis Summary

The `BugAnalysis.summary` object provides aggregate statistics:

```python
{
    "total_bugs": 3,           # Total number of detected bugs
    "high_severity": 2,        # Count of high-severity bugs
    "medium_severity": 1,      # Count of medium-severity bugs
    "low_severity": 0,         # Count of low-severity bugs
    "common_pattern": "name_error",  # Most frequently detected error type
    "error_types": {           # Count by error category
        "name_error": 1,
        "index_error": 1,
        "type_error": 1
    }
}
```

---

## Adding Custom Patterns

To add new error patterns, edit the `PATTERNS` dictionary in `opencompass/bug_detector.py`:

```python
PATTERNS = {
    # ... existing patterns ...

    # Custom pattern
    r'MyCustomError[:\s]+(.+)': (
        ErrorCategory.CUSTOM,
        ErrorSeverity.HIGH,
        'Suggested fix for MyCustomError.'
    ),
}
```

**Pattern format:** Raw string regex. Use `(.+)` capture groups to extract context from the error message.

**Fix suggestions:** If `None`, no auto-fix is suggested (the engine will generate a generic hint from the error message). If a string, it is returned verbatim as the `suggested_fix` field.

---

## Integration with Task Manager

Bug detection is automatically available for any completed task that has test results. The task manager stores test results in `Task.checkpoint.results`, which the bug detector reads directly.

The flow:

1. Agent generates code
2. Code runs in sandbox for each test case
3. Results (stdout, stderr, exit_code, timed_out) are stored in checkpoint
4. `GET /api/v1/tasks/{id}/bugs` triggers on-demand analysis
5. Bug detector scans all failed test results against the pattern database
6. Analysis is returned (not persisted — call again to re-analyze)
