# OpenCompass 二开版 — 完整指南

> 基于 [OpenCompass](https://github.com/open-compass/opencompass) 二次开发，增强多模型 API 支持、代码沙箱、编码智能体评估、Web UI。

---

## 目录

1. [项目概览](#1-项目概览)
2. [环境准备](#2-环境准备)
3. [快速开始](#3-快速开始)
4. [模型 Provider](#4-模型-provider)
   - 4.1 [Claude Messages API](#41-claude-messages-api)
   - 4.2 [Gemini API](#42-gemini-api)
   - 4.3 [OpenAI Responses API](#43-openai-responses-api)
   - 4.4 [OpenAI Chat Completions API（增强）](#44-openai-chat-completions-api增强)
5. [代码沙箱](#5-代码沙箱)
   - 5.1 [SubprocessSandbox](#51-subprocesssandbox)
   - 5.2 [DockerSandbox](#52-dockersandbox)
   - 5.3 [沙箱配置参考](#53-沙箱配置参考)
6. [编码智能体评估](#6-编码智能体评估)
   - 6.1 [AgentTask](#61-agenttask)
   - 6.2 [AgentResult](#62-agentresult)
   - 6.3 [BaseCodingAgent](#63-basecodingagent)
   - 6.4 [ClaudeCodeAgent](#64-claudecodeagent)
   - 6.5 [CodexAgent](#65-codexagent)
   - 6.6 [自定义 Agent](#66-自定义-agent)
7. [API 服务](#7-api-服务)
   - 7.1 [启动服务](#71-启动服务)
   - 7.2 [端点列表](#72-端点列表)
   - 7.3 [任务管理](#73-任务管理)
   - 7.4 [错误重试与恢复](#74-错误重试与恢复)
   - 7.5 [Bug 智能检测](#75-bug-智能检测)
   - 7.6 [测试暂停与继续](#76-测试暂停与继续)
8. [Web UI](#8-web-ui)
   - 8.1 [启用 UI](#81-启用-ui)
   - 8.2 [界面功能](#82-界面功能)
   - 8.3 [API 调用不受影响](#83-api-调用不受影响)
9. [配置参考](#9-配置参考)
10. [开发指南](#10-开发指南)
11. [测试](#11-测试)
12. [常见问题](#12-常见问题)

---

## 1. 项目概览

### 新增能力

| 模块 | 说明 |
|------|------|
| **现代 Claude API** | 从旧版 Completions API 完全迁移到 Messages API |
| **增强 Gemini API** | 支持 systemInstruction、Vision、图片生成、自定义 base_url |
| **OpenAI Responses API** | 支持 Responses API（reasoning、tool use） |
| **代码沙箱** | Subprocess 隔离 + Docker 容器隔离，超时/内存限制 |
| **编码智能体** | ClaudeCode / Codex 评估框架，可扩展 |
| **API 服务** | 轻量 HTTP 服务，纯标准库，无额外依赖 |
| **Web UI** | 可选前端界面，不影响 API |
| **错误重试** | 指数退避重试 + Key 轮转 + 智能错误分类 |
| **Bug 检测** | 自动分析失败输出，分类错误类型，给出修复建议 |
| **暂停/继续** | 测试任务可随时暂停和恢复，断点续测 |

### 架构

```
opencompass/
├── agents/              # 编码智能体评估
│   ├── base_agent.py    # 抽象基类 + AgentTask/AgentResult
│   ├── claudecode_agent.py
│   └── codex_agent.py
├── sandbox/             # 代码沙箱
│   ├── result.py        # SandboxResult 数据类
│   ├── subprocess_sandbox.py
│   └── docker_sandbox.py
├── models/              # 模型 Provider（原有 + 新增）
│   ├── claude_api/      # 重写：现代 Messages API
│   ├── gemini_api.py    # 重写：增强版
│   └── openai_responses_api.py  # 新增
├── task_manager.py      # 任务状态机（暂停/继续/重试）
├── bug_detector.py      # Bug 智能检测
├── server.py            # API 服务 + UI
├── ui/                  # Web UI 静态文件
│   ├── index.html
│   ├── style.css
│   └── app.js
└── tests/               # 单元测试
    ├── test_sandbox.py
    └── test_agents.py
```

---

## 2. 环境准备

### 系统要求

- Python 3.8+
- pip

### 安装

```bash
# 克隆项目
git clone <your-repo-url> opencompass-dev
cd opencompass-dev

# 安装依赖
pip install -r requirements.txt

# 可选：Docker 沙箱支持
# 需要安装 Docker 并确保 docker CLI 可用
```

### 必需依赖

```
requests>=2.28.0
httpx>=0.24.0
```

### 可选依赖

```
# Claude API
anthropic>=0.30.0

# OpenAI Responses API
openai>=1.50.0

# Docker 沙箱
docker>=6.0.0

# Token 计数
tiktoken>=0.7.0
```

### 环境变量

```bash
# Claude API
export ANTHROPIC_API_KEY="sk-ant-..."

# Gemini API
export GEMINI_API_KEY="AI..."

# OpenAI API
export OPENAI_API_KEY="sk-..."

# 可选：自定义 API 地址
export OPENAI_BASE_URL="https://your-proxy.example.com/v1"
```

---

## 3. 快速开始

### 3.1 命令行调用模型

```python
from opencompass.models.claude_api.claude_api import Claude
from opencompass.models.gemini_api import Gemini
from opencompass.models.openai_responses_api import OpenAIResponses

# Claude
claude = Claude(key='sk-ant-...', path='claude-sonnet-4-20250514')
result = claude.generate(['Hello, Claude!'], max_out_len=1024)
print(result)

# Gemini（支持图片生成）
gemini = Gemini(key='AI...', path='gemini-2.5-flash')
result = gemini.generate(['画一只猫'], max_out_len=4096)
print(result)

# OpenAI Responses API（支持 reasoning）
oai = OpenAIResponses(path='o3', reasoning={'effort': 'medium'})
result = oai.generate(['Solve: 2x + 5 = 15'], max_out_len=2048)
print(result)
```

### 3.2 使用沙箱

```python
from opencompass.sandbox import SubprocessSandbox

sandbox = SubprocessSandbox(timeout=30, max_memory_mb=512)

# 执行 Python 代码
result = sandbox.execute(
    code='print("hello from sandbox")',
    language='python',
    timeout=10,
)
print(result.stdout)  # "hello from sandbox"
print(result.exit_code)  # 0
```

### 3.3 编码智能体评估

```python
from opencompass.agents import AgentTask, ClaudeCodeAgent

task = AgentTask(
    description='Write a function that adds two numbers',
    language='python',
    test_cases=[
        {'code': 'assert solution(2, 3) == 5'},
        {'code': 'assert solution(-1, 1) == 0'},
    ],
)

agent = ClaudeCodeAgent(
    api_key='sk-ant-...',
    model='claude-sonnet-4-20250514',
)
result = agent.evaluate(task)
print(f"通过: {result.passed_tests}/{result.total_tests}")
print(f"耗时: {result.execution_time}s")
```

### 3.4 启动 API 服务

```bash
# 基础启动
python -m opencompass.server --port 8000

# 启用 Web UI
python -m opencompass.server --port 8000 --enable-ui

# 自定义配置
python -m opencompass.server --host 0.0.0.0 --port 8080 --enable-ui
```

---

## 4. 模型 Provider

### 4.1 Claude Messages API

完全重写，使用现代 Anthropic Messages API。

```python
from opencompass.models.claude_api.claude_api import Claude

model = Claude(
    key='sk-ant-...',                    # API Key
    path='claude-sonnet-4-20250514',      # 模型名称
    base_url=None,                        # 自定义 API 地址（代理中转）
    temperature=0.3,                      # 采样温度
    top_p=0.9,                           # Top-P
    max_tokens=4096,                      # 最大输出 token
    retry=3,                              # 重试次数
    query_per_second=2,                   # 限速
)
```

**特性：**
- ✅ System prompt 通过 Messages API 的 `system` 参数传递
- ✅ 多轮对话支持（HUMAN→user, BOT→assistant, SYSTEM→system）
- ✅ Vision 输入（图片 base64 内嵌）
- ✅ Key 轮转（多 Key 负载均衡 + 自动跳过无效 Key）
- ✅ 指数退避重试（429/529/500 自动重试）
- ✅ `count_tokens` API 精确 token 计数

**PromptList 格式：**

```python
from opencompass.utils.prompt import PromptList

prompt = PromptList([
    {'role': 'SYSTEM', 'prompt': 'You are a helpful assistant.'},
    {'role': 'HUMAN', 'prompt': 'What is 2+2?'},
    {'role': 'BOT', 'prompt': '4.'},
    {'role': 'HUMAN', 'prompt': 'And 3+3?'},
])
result = model.generate([prompt])
```

### 4.2 Gemini API

增强版，支持最新 Gemini 特性。

```python
from opencompass.models.gemini_api import Gemini

model = Gemini(
    key='AI...',
    path='gemini-2.5-flash',
    base_url='https://generativelanguage.googleapis.com',
    temperature=1.0,
    top_p=0.8,
    top_k=10,
    max_output_tokens=8192,
    response_modalities=['TEXT'],           # ['TEXT'] 或 ['TEXT', 'IMAGE']
)
```

**特性：**
- ✅ `systemInstruction` 字段正确传递 system prompt
- ✅ Vision 输入（`inline_data` base64 内嵌）
- ✅ 图片生成（`responseModalities: ["TEXT", "IMAGE"]`）
- ✅ 自定义 `base_url`（代理中转）
- ✅ 安全过滤处理（可配置阈值）
- ✅ `safetySettings` 可配置

**图片生成示例：**

```python
gen_model = Gemini(
    key='AI...',
    path='gemini-2.5-flash-preview-image-generation',
    response_modalities=['TEXT', 'IMAGE'],
)
result = gen_model.generate(['画一只在水中的猫'])
# 返回文本 + [Image output: 1 image(s) generated]
```

### 4.3 OpenAI Responses API

新增，支持 OpenAI 最新的 Responses API。

```python
from opencompass.models.openai_responses_api import OpenAIResponses

model = OpenAIResponses(
    path='o3',
    key='sk-...',
    base_url='https://api.openai.com/v1',   # 支持代理中转
    reasoning={'effort': 'medium'},          # reasoning 配置
    max_output_tokens=4096,
    temperature=None,                        # o 系列不支持 temperature
)
```

**特性：**
- ✅ `client.responses.create()` 调用
- ✅ `reasoning` 参数（effort: low/medium/high）
- ✅ Key 轮转
- ✅ tiktoken 精确 token 计数
- ✅ 推理模型自动跳过 temperature

**支持的模型：**
- `o3` / `o4` / `o1` — 推理模型（自动跳过 temperature）
- `gpt-4o` / `gpt-4o-mini` — 标准模型
- `gpt-5` — 最新模型

### 4.4 OpenAI Chat Completions API（增强）

原有的 `OpenAI` 和 `OpenAISDK` 保持不变，新增以下能力通过配置实现：

```python
from opencompass.models.openai_api import OpenAISDK

model = OpenAISDK(
    path='gpt-4o',
    key='sk-...',
    # 原有参数全部保留
    query_per_second=1,
    max_seq_len=128000,
    retry=3,
    # 新增：可通过 OPENAI_BASE_URL 环境变量设置代理
)
```

---

## 5. 代码沙箱

### 5.1 SubprocessSandbox

子进程隔离执行，零额外依赖。

```python
from opencompass.sandbox import SubprocessSandbox

sandbox = SubprocessSandbox(
    timeout=30,           # 默认超时 30s
    max_memory_mb=512,    # 默认内存限制 512MB
)
```

**安全机制：**
- 🔒 每次执行在独立临时目录中
- 🔒 `resource.setrlimit` 限制 CPU 时间和内存
- 🔒 执行超时自动 kill
- 🔒 环境变量隔离（仅传递指定变量）

**执行代码：**

```python
# Python
result = sandbox.execute(code='print(2+3)', language='python', timeout=10)
assert result.exit_code == 0
assert '5' in result.stdout

# Bash
result = sandbox.execute(code='echo hello', language='bash')

# 自定义环境变量
result = sandbox.execute(
    code='import os; print(os.environ["MY_VAR"])',
    language='python',
    env={'MY_VAR': 'secret_value'},
)
```

**SandboxResult 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `exit_code` | int | 进程退出码 |
| `stdout` | str | 标准输出 |
| `stderr` | str | 标准错误 |
| `timed_out` | bool | 是否超时 |
| `memory_exceeded` | bool | 是否内存超限 |
| `execution_time` | float | 执行耗时（秒） |
| `files` | dict | 执行后的文件快照 |

### 5.2 DockerSandbox

Docker 容器隔离，安全性更高。

```python
from opencompass.sandbox import DockerSandbox

sandbox = DockerSandbox(
    image='python:3.10-slim',   # Docker 镜像
    timeout=60,
    memory_limit='512m',
    cpu_period=100000,
    cpu_quota=50000,             # 50% CPU
)

result = sandbox.execute(code='print("hello from docker")', language='python')
```

**要求：**
- Docker 已安装并运行
- 目标镜像已拉取
- `docker` CLI 可用

### 5.3 沙箱配置参考

| 参数 | Subprocess | Docker | 说明 |
|------|-----------|--------|------|
| `timeout` | ✅ | ✅ | 执行超时（秒） |
| `max_memory_mb` | ✅ | ✅ | 内存限制 |
| `env` | ✅ | ✅ | 环境变量 |
| `image` | ❌ | ✅ | Docker 镜像 |
| `cpu_quota` | ❌ | ✅ | CPU 限制 |

### 工厂函数

```python
from opencompass.sandbox import create_sandbox

# 自动选择最佳沙箱
sandbox = create_sandbox('subprocess')  # 或 'docker'
```

---

## 6. 编码智能体评估

### 6.1 AgentTask

```python
from opencompass.agents import AgentTask

task = AgentTask(
    description='写一个函数，计算斐波那契数列第 n 项',
    language='python',
    context='',                              # 前置上下文
    test_cases=[
        # 模式一：代码断言
        {'code': 'assert solution(0) == 0'},
        {'code': 'assert solution(1) == 1'},
        {'code': 'assert solution(10) == 55'},
        # 模式二：输入/输出
        {'input': '10', 'expected': '55'},
    ],
    difficulty='medium',                     # easy/medium/hard
    max_tokens=4096,                         # 智能体最大生成 token
    timeout=300,                             # 整体超时
)
```

### 6.2 AgentResult

```python
result = agent.evaluate(task)

print(result.task_id)          # 任务 ID
print(result.agent_name)       # 智能体名称
print(result.success)          # 是否全部通过
print(result.total_tests)      # 总测试数
print(result.passed_tests)     # 通过数
print(result.generated_code)   # 生成的代码
print(result.execution_time)   # 耗时（秒）
print(result.tokens_used)      # 使用 token 数
print(result.error)            # 错误信息（如有）
```

### 6.3 BaseCodingAgent

抽象基类，自定义 Agent 需继承并实现 `generate_code`。

```python
from opencompass.agents import BaseCodingAgent, AgentTask

class MyAgent(BaseCodingAgent):
    def __init__(self, name='my-agent', **kwargs):
        super().__init__(name=name, **kwargs)
        # 初始化你的 API 客户端

    def generate_code(self, task: AgentTask) -> tuple:
        """返回 (code, tokens_used) 元组。"""
        # 调用你的模型 API
        code = your_model_api(task.description)
        return code, len(code) // 4  # 估算 token 数

agent = MyAgent()
result = agent.evaluate(task)
```

### 6.4 ClaudeCodeAgent

```python
from opencompass.agents import ClaudeCodeAgent

agent = ClaudeCodeAgent(
    api_key='sk-ant-...',
    model='claude-sonnet-4-20250514',
    base_url=None,           # 代理中转
    temperature=0.2,
    max_tokens=4096,
)
```

### 6.5 CodexAgent

```python
from opencompass.agents import CodexAgent

agent = CodexAgent(
    api_key='sk-...',
    model='o3',
    base_url=None,
    max_tokens=4096,
)
```

### 6.6 自定义 Agent

```python
from opencompass.agents import BaseCodingAgent, AgentTask, AgentResult
from opencompass.sandbox import SubprocessSandbox

class GeminiCodeAgent(BaseCodingAgent):
    """使用 Gemini 的编码智能体。"""

    SYSTEM_PROMPT = "You are an expert programmer. Output ONLY code."

    def __init__(self, api_key, model='gemini-2.5-flash', **kwargs):
        super().__init__(name=f'gemini-code-{model}', **kwargs)
        self.api_key = api_key
        self.model = model

    def generate_code(self, task: AgentTask) -> tuple:
        # 调用 Gemini API
        import requests
        # ... 实现 API 调用逻辑
        return generated_code, token_count

agent = GeminiCodeAgent(api_key='AI...')
result = agent.evaluate(task)
```

---

## 7. API 服务

### 7.1 启动服务

```bash
# 基础 API 服务（无 UI）
python -m opencompass.server --port 8000

# 启用 Web UI
python -m opencompass.server --port 8000 --enable-ui

# 指定绑定地址
python -m opencompass.server --host 0.0.0.0 --port 8080 --enable-ui

# 作为模块导入使用
from opencompass.server import run_server
run_server(host='0.0.0.0', port=8000, enable_ui=False)
```

### 7.2 端点列表

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/v1/status` | 服务状态 |
| `GET` | `/api/v1/models` | 列出可用模型 |
| `POST` | `/api/v1/evaluate` | 提交模型评估任务 |
| `GET` | `/api/v1/tasks/{id}` | 查询任务状态 |
| `POST` | `/api/v1/agent/evaluate` | 提交编码智能体评估 |
| `POST` | `/api/v1/sandbox/execute` | 执行代码 |
| `POST` | `/api/v1/tasks/{id}/pause` | 暂停任务 |
| `POST` | `/api/v1/tasks/{id}/resume` | 继续任务 |
| `GET` | `/api/v1/tasks/{id}/retry` | 重试失败任务 |
| `GET` | `/api/v1/tasks/{id}/bugs` | Bug 检测报告 |
| `GET` | `/` | Web UI（需 `--enable-ui`） |

### 7.3 任务管理

#### 提交评估

```bash
curl -X POST http://localhost:8000/api/v1/agent/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "claude",
    "model": "claude-sonnet-4-20250514",
    "api_key": "ENV",
    "task": {
      "description": "Write a function that reverses a string",
      "language": "python",
      "test_cases": [
        {"code": "assert solution(\"hello\") == \"olleh\""},
        {"code": "assert solution(\"\") == \"\""}
      ]
    }
  }'
```

**响应：**
```json
{
  "task_id": "a1b2c3d4",
  "status": "pending",
  "message": "Agent evaluation task submitted"
}
```

#### 查询状态

```bash
curl http://localhost:8000/api/v1/tasks/a1b2c3d4
```

**响应：**
```json
{
  "id": "a1b2c3d4",
  "type": "agent_evaluate",
  "status": "completed",
  "result": {
    "success": true,
    "total_tests": 2,
    "passed_tests": 2,
    "generated_code": "def solution(s): return s[::-1]",
    "execution_time": 3.5
  },
  "created_at": 1715068800.0,
  "started_at": 1715068800.1,
  "completed_at": 1715068803.6
}
```

### 7.4 错误重试与恢复

任务失败后自动或手动重试。

**自动重试：**
- API 调用层：所有模型 Provider 内置指数退避重试（默认 2-3 次）
- 429 Rate Limit → 等待后重试
- 500/503 服务错误 → 等待后重试
- 连接超时 → 立即重试

**手动重试：**
```bash
# 重试整个任务
curl -X POST http://localhost:8000/api/v1/tasks/a1b2c3d4/retry

# 带参数重试（修改配置）
curl -X POST http://localhost:8000/api/v1/tasks/a1b2c3d4/retry \
  -H "Content-Type: application/json" \
  -d '{
    "retry_count": 3,
    "retry_delay": 5,
    "retry_on_errors": ["timeout", "api_error"]
  }'
```

**重试策略：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_retries` | 3 | 最大重试次数 |
| `initial_delay` | 1.0 | 初始延迟（秒） |
| `backoff_factor` | 2.0 | 退避倍数 |
| `max_delay` | 60.0 | 最大延迟上限 |

### 7.5 Bug 智能检测

自动分析失败测试，分类错误并给出修复建议。

```bash
# 获取 Bug 报告
curl http://localhost:8000/api/v1/tasks/a1b2c3d4/bugs
```

**响应：**
```json
{
  "task_id": "a1b2c3d4",
  "bugs": [
    {
      "test_index": 2,
      "error_type": "TypeError",
      "severity": "high",
      "description": "Function expects str but received int",
      "suggested_fix": "Add type conversion: str(input_data)",
      "confidence": 0.85
    },
    {
      "test_index": 3,
      "error_type": "IndexError",
      "severity": "medium",
      "description": "List index out of range",
      "suggested_fix": "Add boundary check: if i < len(arr)",
      "confidence": 0.72
    }
  ],
  "summary": {
    "total_bugs": 2,
    "high_severity": 1,
    "medium_severity": 1,
    "low_severity": 0,
    "common_pattern": "type_mismatch"
  }
}
```

**错误分类：**

| 类型 | 说明 |
|------|------|
| `syntax_error` | Python 语法错误 |
| `type_error` | 类型不匹配 |
| `index_error` | 索引越界 |
| `key_error` | 字典键缺失 |
| `name_error` | 变量未定义 |
| `value_error` | 值错误 |
| `runtime_error` | 通用运行时错误 |
| `timeout` | 执行超时 |
| `memory_error` | 内存超限 |
| `import_error` | 模块导入失败 |

### 7.6 测试暂停与继续

#### 暂停任务

```bash
curl -X POST http://localhost:8000/api/v1/tasks/a1b2c3d4/pause
```

**响应：**
```json
{
  "task_id": "a1b2c3d4",
  "status": "paused",
  "completed_tests": 5,
  "remaining_tests": 10,
  "checkpoint": "saved"
}
```

暂停时自动保存检查点：
- 已完成的测试结果
- 当前测试进度
- 生成的代码
- 执行时间统计

#### 继续任务

```bash
curl -X POST http://localhost:8000/api/v1/tasks/a1b2c3d4/resume
```

**响应：**
```json
{
  "task_id": "a1b2c3d4",
  "status": "running",
  "resumed_from_test": 6,
  "remaining_tests": 10
}
```

#### 暂停/继续原理

```
[开始] → test_1 ✓ → test_2 ✗ → test_3 ✓ → ... → test_5 ✓
                                                     ↓
                                              [用户暂停]
                                                     ↓
                                          保存检查点 (checkpoint)
                                          - 已完成: 5/15
                                          - 结果: [✓,✗,✓,✓,✓]
                                          - 代码: "def solution()..."
                                                     ↓
                                              [用户继续]
                                                     ↓
                                        从 test_6 恢复执行 → ...
```

---

## 8. Web UI

### 8.1 启用 UI

```bash
python -m opencompass.server --port 8000 --enable-ui
```

然后访问 `http://localhost:8000/`。

### 8.2 界面功能

| 功能 | 说明 |
|------|------|
| 📊 **仪表盘** | 实时任务统计、成功率、平均耗时 |
| 📝 **任务列表** | 所有任务的分页列表，支持筛选 |
| 🔍 **任务详情** | 单个任务的完整执行信息 |
| ▶️ **提交任务** | 可视化表单提交评估任务 |
| ⏸️ **暂停/继续** | 一键暂停和继续任务 |
| 🔄 **重试** | 一键重试失败任务 |
| 🐛 **Bug 报告** | 可视化 Bug 检测结果 |
| 🖥️ **沙箱调试** | 在线执行代码片段 |
| ⚙️ **设置** | 配置 API Key、模型参数等 |

### 8.3 API 调用不受影响

UI 是**纯前端**实现，通过调用同一套 API 端点工作。

- ✅ 不修改任何 API 行为
- ✅ 不增加后端依赖
- ✅ 不影响现有代码调用方式
- ✅ 可随时关闭（去掉 `--enable-ui` 参数即可）
- ✅ API 端点和参数完全不变

```python
# 不启用 UI 时，所有 API 端点正常工作
python -m opencompass.server --port 8000  # 无 --enable-ui

# 所有端点照常可用
import requests
requests.post('http://localhost:8000/api/v1/agent/evaluate', json={...})
```

---

## 9. 配置参考

### 模型配置

#### Claude

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `key` | str | `'ENV'` | API Key |
| `path` | str | `'claude-sonnet-4-20250514'` | 模型名称 |
| `base_url` | str/None | `None` | 代理地址 |
| `temperature` | float/None | `None` | 采样温度 |
| `top_p` | float/None | `None` | Top-P |
| `max_tokens` | int | `4096` | 最大输出 token |
| `retry` | int | `2` | 重试次数 |
| `query_per_second` | int | `2` | 限速 |
| `max_seq_len` | int | `200000` | 最大序列长度 |

#### Gemini

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `key` | str | `'ENV'` | API Key |
| `path` | str | `'gemini-2.5-flash'` | 模型名称 |
| `base_url` | str | `'https://generativelanguage.googleapis.com'` | API 地址 |
| `temperature` | float | `1.0` | 采样温度 |
| `top_p` | float | `0.8` | Top-P |
| `top_k` | float | `10.0` | Top-K |
| `max_output_tokens` | int | `8192` | 最大输出 token |
| `response_modalities` | list | `['TEXT']` | 输出模态 |

#### OpenAI Responses

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | str | `'gpt-4o'` | 模型名称 |
| `key` | str | `'ENV'` | API Key |
| `base_url` | str | `'https://api.openai.com/v1'` | API 地址 |
| `reasoning` | dict/None | `None` | Reasoning 配置 |
| `max_output_tokens` | int | `4096` | 最大输出 token |
| `temperature` | float/None | `None` | 采样温度 |

### 沙箱配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeout` | int | `30` | 执行超时（秒） |
| `max_memory_mb` | int | `512` | 内存限制（MB） |
| `env` | dict | `{}` | 环境变量 |

---

## 10. 开发指南

### 新增模型 Provider

1. 在 `opencompass/models/` 创建文件
2. 继承 `BaseAPIModel`
3. 实现 `generate()` 和 `get_token_len()`
4. 使用 `@MODELS.register_module()` 注册
5. 在 `__init__.py` 添加导出

```python
from opencompass.registry import MODELS
from opencompass.models.base_api import BaseAPIModel

@MODELS.register_module()
class MyModel(BaseAPIModel):
    def __init__(self, path, key, **kwargs):
        super().__init__(path=path, **kwargs)
        self.key = key

    def generate(self, inputs, max_out_len=512):
        # 实现 API 调用
        return results

    def get_token_len(self, prompt):
        # 实现 token 计数
        return count
```

### 新增 Agent

1. 在 `opencompass/agents/` 创建文件
2. 继承 `BaseCodingAgent`
3. 实现 `generate_code(task) -> (code, tokens_used)`
4. 在 `__init__.py` 添加导出

### 新增沙箱

1. 在 `opencompass/sandbox/` 创建文件
2. 实现 `execute(code, language, timeout, **kwargs) -> SandboxResult`
3. 在 `__init__.py` 添加到工厂函数

---

## 11. 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行沙箱测试
python -m pytest tests/test_sandbox.py -v

# 运行 Agent 测试
python -m pytest tests/test_agents.py -v

# 运行单个测试
python -m pytest tests/test_sandbox.py::TestSubprocessSandbox::test_python_simple -v
```

### 测试覆盖

| 模块 | 测试文件 | 测试数 |
|------|----------|--------|
| 沙箱 | `test_sandbox.py` | 14 |
| Agent | `test_agents.py` | 16 |
| **总计** | | **30** |

---

## 12. 常见问题

### Q: Claude API 报 401 错误？

检查 API Key 是否正确。确保 Key 以 `sk-ant-` 开头。

### Q: Gemini 返回安全过滤？

默认禁用了安全过滤（`BLOCK_NONE`）。如果仍然被过滤，检查请求内容是否触发了 Google 的硬性安全策略。

### Q: Docker 沙箱无法启动？

确保 Docker 已安装且正在运行：
```bash
docker info
```

### Q: 内存限制不生效？

`resource.setrlimit(RLIMIT_AS, ...)` 在某些系统/容器环境中可能不生效。可以考虑使用 Docker 沙箱替代。

### Q: 如何使用代理？

所有模型都支持 `base_url` 参数：
```python
model = Claude(key='...', base_url='https://your-proxy.com')
```

或通过环境变量：
```bash
export OPENAI_BASE_URL="https://your-proxy.com/v1"
```

### Q: 如何关闭 Web UI？

不传 `--enable-ui` 参数即可。所有 API 功能不受影响。

### Q: 任务暂停后服务重启怎么办？

暂停的任务状态保存在内存中，服务重启后状态会丢失。未来版本将支持持久化检查点。
