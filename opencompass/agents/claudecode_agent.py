"""Claude Code 编码智能体包装器。"""

import json
import logging
import os
import subprocess
from typing import Optional

from .base_agent import AgentTask, BaseCodingAgent

logger = logging.getLogger(__name__)

# 系统提示模板
_SYSTEM_PROMPT = """\
你是一个专业的编程助手。请根据用户的要求编写高质量的代码。

要求：
1. 只输出代码，不要解释
2. 代码应该完整可运行
3. 包含必要的 import 语句
4. 如果需要定义一个函数，请将其命名为 solution()
5. 不要使用任何外部依赖（除非明确要求）
"""


class ClaudeCodeAgent(BaseCodingAgent):
    """Claude Code 编码智能体评估。

    支持两种模式：
    1. API 模式：直接调用 Anthropic Messages API（默认）
    2. CLI 模式：调用 claude 命令行工具

    用法：
        # API 模式
        agent = ClaudeCodeAgent(
            mode='api',
            api_key='sk-xxx',
            model='claude-sonnet-4-20250514',
        )
        result = agent.evaluate(task)

        # CLI 模式
        agent = ClaudeCodeAgent(mode='cli')
    """

    def __init__(
        self,
        mode: str = 'api',
        api_key: str = 'ENV',
        model: str = 'claude-sonnet-4-20250514',
        base_url: Optional[str] = None,
        sandbox=None,
    ):
        """初始化 Claude Code Agent。

        Args:
            mode: 运行模式，'api' 或 'cli'。
            api_key: API 密钥，'ENV' 表示从环境变量 ANTHROPIC_API_KEY 读取。
            model: 模型名称。
            base_url: 自定义 API 基础 URL（可选）。
            sandbox: 代码执行沙箱。
        """
        super().__init__(name=f'claude-code-{model}', sandbox=sandbox)
        self.mode = mode
        self.model = model
        self.base_url = base_url

        if api_key == 'ENV':
            self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        else:
            self.api_key = api_key

    def generate_code(self, task: AgentTask) -> tuple:
        """调用 Claude 生成代码。

        Args:
            task: 编码任务定义。

        Returns:
            (code, tokens_used) 元组。
        """
        if self.mode == 'cli':
            return self._generate_via_cli(task)
        else:
            return self._generate_via_api(task)

    def _generate_via_api(self, task: AgentTask) -> tuple:
        """通过 Anthropic Messages API 生成代码。

        Args:
            task: 编码任务定义。

        Returns:
            (code, tokens_used) 元组。
        """
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                'Claude API mode requires the "anthropic" Python package. '
                'Install it with: pip install anthropic'
            )

        if not self.api_key:
            raise ValueError(
                'Anthropic API key is required. '
                'Set ANTHROPIC_API_KEY or pass api_key parameter.'
            )

        # 构建 prompt
        user_message = self._build_prompt(task)

        # 创建客户端
        client_kwargs = {'api_key': self.api_key}
        if self.base_url:
            client_kwargs['base_url'] = self.base_url
        client = anthropic.Anthropic(**client_kwargs)

        logger.info(
            'Calling Claude API: model=%s task=%s',
            self.model, task.task_id,
        )

        # 调用 API
        response = client.messages.create(
            model=self.model,
            max_tokens=task.max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': user_message}],
        )

        # 提取代码
        content = response.content[0].text
        code = self.extract_code_blocks(content, task.language)

        # 计算 token 使用量
        tokens_used = (
            response.usage.input_tokens + response.usage.output_tokens
        )

        return code, tokens_used

    def _generate_via_cli(self, task: AgentTask) -> tuple:
        """通过 Claude CLI 生成代码。

        Args:
            task: 编码任务定义。

        Returns:
            (code, tokens_used) 元组。CLI 模式下 tokens_used 为 0。
        """
        prompt = self._build_prompt(task)

        try:
            result = subprocess.run(
                ['claude', '-p', prompt, '--model', self.model],
                capture_output=True,
                text=True,
                timeout=task.timeout,
            )
            if result.returncode != 0:
                logger.error('Claude CLI failed: %s', result.stderr)
                return '', 0

            code = self.extract_code_blocks(result.stdout, task.language)
            return code, 0

        except subprocess.TimeoutExpired:
            logger.error('Claude CLI timed out')
            return '', 0
        except FileNotFoundError:
            logger.error('claude CLI not found')
            raise ImportError(
                'Claude CLI is not installed. '
                'Install it from: https://docs.anthropic.com/en/docs/claude-code'
            )

    def _build_prompt(self, task: AgentTask) -> str:
        """构建发送给智能体的 prompt。

        Args:
            task: 编码任务定义。

        Returns:
            完整的 prompt 字符串。
        """
        parts = [
            f'Language: {task.language}',
            f'Difficulty: {task.difficulty}',
            f'\nTask:\n{task.description}',
        ]

        if task.context:
            parts.append(f'\nContext:\n{task.context}')

        if task.test_cases:
            parts.append('\nTest cases:')
            for i, tc in enumerate(task.test_cases):
                parts.append(f'  Test {i + 1}: {json.dumps(tc, ensure_ascii=False)}')

        return '\n'.join(parts)
