"""OpenAI Codex 编码智能体包装器。"""

import json
import logging
import os
from typing import Optional

from .base_agent import AgentTask, BaseCodingAgent

logger = logging.getLogger(__name__)

# 系统提示模板
_SYSTEM_PROMPT = """\
You are an expert programmer. Write clean, correct, and efficient code based on the user's requirements.

Rules:
1. Output only code, no explanations
2. Code should be complete and runnable
3. Include all necessary import statements
4. Define a function named solution() if the task involves a function
5. Do not use external dependencies unless explicitly required
"""


class CodexAgent(BaseCodingAgent):
    """OpenAI Codex 编码智能体评估。

    通过 OpenAI API 调用模型生成代码。

    用法：
        agent = CodexAgent(
            api_key='sk-xxx',
            model='o3',
        )
        result = agent.evaluate(task)
    """

    def __init__(
        self,
        api_key: str = 'ENV',
        model: str = 'o3',
        base_url: Optional[str] = None,
        sandbox=None,
    ):
        """初始化 Codex Agent。

        Args:
            api_key: API 密钥，'ENV' 表示从环境变量 OPENAI_API_KEY 读取。
            model: 模型名称（如 'o3', 'gpt-4o'）。
            base_url: 自定义 API 基础 URL（可选）。
            sandbox: 代码执行沙箱。
        """
        super().__init__(name=f'codex-{model}', sandbox=sandbox)
        self.model = model
        self.base_url = base_url

        if api_key == 'ENV':
            self.api_key = os.environ.get('OPENAI_API_KEY', '')
        else:
            self.api_key = api_key

    def generate_code(self, task: AgentTask) -> tuple:
        """调用 OpenAI API 生成代码。

        Args:
            task: 编码任务定义。

        Returns:
            (code, tokens_used) 元组。
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                'CodexAgent requires the "openai" Python package. '
                'Install it with: pip install openai'
            )

        if not self.api_key:
            raise ValueError(
                'OpenAI API key is required. '
                'Set OPENAI_API_KEY or pass api_key parameter.'
            )

        # 构建 prompt
        user_message = self._build_prompt(task)

        # 创建客户端
        client_kwargs = {'api_key': self.api_key}
        if self.base_url:
            client_kwargs['base_url'] = self.base_url
        client = OpenAI(**client_kwargs)

        logger.info(
            'Calling OpenAI API: model=%s task=%s',
            self.model, task.task_id,
        )

        # 调用 API
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=task.max_tokens,
            messages=[
                {'role': 'system', 'content': _SYSTEM_PROMPT},
                {'role': 'user', 'content': user_message},
            ],
        )

        # 提取代码
        content = response.choices[0].message.content or ''
        code = self.extract_code_blocks(content, task.language)

        # 计算 token 使用量
        tokens_used = response.usage.total_tokens if response.usage else 0

        return code, tokens_used

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
