# CodeBench — AI 编码智能体评估框架

一个轻量级、API 优先的 AI 编码智能体评估框架，支持沙箱化代码执行、Bug 检测和内置 Web UI。

基于 [OpenCompass](https://github.com/open-compass/opencompass)（[官网](https://opencompass.org.cn/)）由 [上海人工智能实验室](https://www.shlab.org.cn/) 开源。本项目在原有评估基础设施之上，扩展了现代编码智能体工作流、沙箱执行和精简的 API 服务。

中文 | [English](README.md) | [日本語](README_ja.md) | [Русский](README_ru.md) | [Français](README_fr.md)

## 特性

- **多渠道支持** — Claude API、Gemini API、OpenAI Responses API、OpenAI Chat Completions
- **编码智能体封装** — 可插拔的智能体评估（Claude Code、Codex、自定义）
- **沙箱化执行** — 子进程与 Docker 隔离，支持超时和内存限制
- **Bug 智能检测** — 基于正则的错误模式匹配，自动分类严重级别并给出修复建议
- **任务管理** — 暂停/继续/重试，支持检查点断点恢复
- **REST API** — 轻量级 HTTP 服务（仅使用标准库，零额外依赖）
- **Web UI** — 可选的暗色主题仪表盘（`--enable-ui`）
- **完善的测试** — 30+ 单元测试

## 快速开始

```bash
# 安装依赖（仅智能体 API 集成需要）
pip install anthropic google-generativeai openai

# 启动 API 服务
python -m opencompass.server --port 8000

# 或启用 Web UI
python -m opencompass.server --port 8000 --enable-ui
```

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/models` | 列出可用模型 |
| POST | `/api/v1/evaluate` | 提交模型评估 |
| POST | `/api/v1/agent/evaluate` | 提交编码智能体评估 |
| POST | `/api/v1/sandbox/execute` | 在沙箱中执行代码 |
| GET | `/api/v1/tasks/{id}` | 查询任务状态 |
| POST | `/api/v1/tasks/{id}/pause` | 暂停运行中的任务 |
| POST | `/api/v1/tasks/{id}/resume` | 继续已暂停的任务 |
| POST | `/api/v1/tasks/{id}/retry` | 重试失败的任务 |
| GET | `/api/v1/tasks/{id}/bugs` | 获取 Bug 检测报告 |
| GET | `/` | Web UI（需 `--enable-ui`） |

## 项目结构

```
├── opencompass/
│   ├── agents/          # 编码智能体封装（Claude Code、Codex）
│   ├── sandbox/         # 沙箱化代码执行（子进程、Docker）
│   ├── models/          # 模型渠道（Claude、Gemini、OpenAI 等）
│   ├── bug_detector.py  # 自动化 Bug 分析
│   ├── task_manager.py  # 任务生命周期管理
│   ├── server.py        # REST API 服务
│   └── ui/              # Web UI（静态文件）
├── tests/
│   ├── test_sandbox.py
│   └── test_agents.py
└── docs/
    └── GUIDE.md         # 详细开发指南
```

## 测试

```bash
python -m pytest tests/test_sandbox.py tests/test_agents.py -v
```

## 致谢

本项目基于 [OpenCompass](https://github.com/open-compass/opencompass)（[官网](https://opencompass.org.cn/)），由 [上海人工智能实验室](https://www.shlab.org.cn/) 开源的大语言模型评测框架。感谢 OpenCompass 团队在 LLM 评测基础设施方面的奠基性工作。

## 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE)。
