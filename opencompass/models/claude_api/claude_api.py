"""现代 Claude Messages API 实现。"""
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Union

from opencompass.registry import MODELS
from opencompass.utils.prompt import PromptList

from ..base_api import BaseAPIModel

logger = logging.getLogger(__name__)

PromptType = Union[PromptList, str]


@MODELS.register_module()
class Claude(BaseAPIModel):
    """Model wrapper around Claude Messages API.

    使用现代 Anthropic Messages API（非旧版 Completions API）。

    Args:
        key (str): Anthropic API Key. 'ENV' 则从环境变量 ANTHROPIC_API_KEY 读取。
        path (str): 模型名称，如 'claude-sonnet-4-20250514'。
        query_per_second (int): 每秒最大请求数。
        max_seq_len (int): 最大序列长度。
        meta_template (Dict, optional): 元提示模板。
        retry (int): 失败重试次数。
        base_url (str, optional): 自定义 API Base URL（用于代理中转）。
        temperature (float, optional): 采样温度。
        top_p (float, optional): Top-P 采样。
        max_tokens (int): 最大输出 token 数。默认 4096。
        timeout (int): 请求超时秒数。默认 3600。
    """

    def __init__(
        self,
        key: str = 'ENV',
        path: str = 'claude-sonnet-4-20250514',
        query_per_second: int = 2,
        max_seq_len: int = 200000,
        meta_template: Optional[Dict] = None,
        retry: int = 2,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: int = 4096,
        timeout: int = 3600,
    ):
        super().__init__(
            path=path,
            max_seq_len=max_seq_len,
            query_per_second=query_per_second,
            meta_template=meta_template,
            retry=retry,
        )

        if key == 'ENV':
            key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not key:
            raise ValueError('Anthropic API key is required.')

        self.key = key
        self.model = path
        self.base_url = base_url or 'https://api.anthropic.com'
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        """懒加载 Anthropic 客户端。"""
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(
                    api_key=self.key,
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
            except ImportError:
                raise ImportError(
                    'anthropic package is required. '
                    'Install with "pip install anthropic".'
                )
        return self._client

    def generate(
        self,
        inputs: List[PromptType],
        max_out_len: int = 512,
    ) -> List[str]:
        """Generate results given a list of inputs.

        Args:
            inputs (List[PromptType]): A list of strings or PromptDicts.
            max_out_len (int): The maximum length of the output.

        Returns:
            List[str]: A list of generated strings.
        """
        with ThreadPoolExecutor() as executor:
            results = list(
                executor.map(self._generate, inputs,
                             [max_out_len] * len(inputs)))
        return results

    def _generate(self, input: PromptType, max_out_len: int = 512) -> str:
        """Generate result given an input.

        Args:
            input (PromptType): A string or PromptList.
            max_out_len (int): The maximum length of the output.

        Returns:
            str: The generated string.
        """
        assert isinstance(input, (str, PromptList))

        messages, system = self._convert_messages(input)

        kwargs = {
            'model': self.model,
            'max_tokens': max_out_len or self.max_tokens,
            'messages': messages,
        }
        if system:
            kwargs['system'] = system
        if self.temperature is not None:
            kwargs['temperature'] = self.temperature
        if self.top_p is not None:
            kwargs['top_p'] = self.top_p

        client = self._get_client()

        for attempt in range(self.retry):
            self.wait()
            try:
                response = client.messages.create(**kwargs)

                # 提取文本内容
                result_text = ''
                for block in response.content:
                    if block.type == 'text':
                        result_text += block.text
                    elif block.type == 'thinking':
                        # 可选：包含思考内容
                        pass

                return result_text.strip()

            except Exception as e:
                error_str = str(e)
                logger.error(f'Claude API error (attempt {attempt + 1}/{self.retry}): {error_str}')

                # 检查是否可重试
                if 'rate_limit' in error_str.lower():
                    time.sleep(2 ** attempt)
                elif 'overloaded' in error_str.lower():
                    time.sleep(5)
                else:
                    raise

        raise RuntimeError(
            f'Calling Claude API failed after {self.retry} retries. '
            f'Check the logs for details.'
        )

    def _convert_messages(self, input: PromptType) -> tuple:
        """将 OpenCompass 格式的输入转换为 Claude Messages API 格式。

        Args:
            input: 字符串或 PromptList。

        Returns:
            (messages, system_prompt) 元组。
        """
        if isinstance(input, str):
            return [{'role': 'user', 'content': input}], None

        # PromptList 格式
        messages = []
        system = None

        for item in input:
            role = item.get('role', 'HUMAN')
            content = item.get('prompt', item.get('content', ''))

            if role == 'SYSTEM':
                if system is None:
                    system = content
                else:
                    system += '\n' + content
            elif role in ('HUMAN', 'user'):
                # 检查是否有 vision 内容
                if isinstance(content, list):
                    # 多模态内容
                    parts = []
                    for c in content:
                        if isinstance(c, dict) and c.get('type') == 'image':
                            parts.append({
                                'type': 'image',
                                'source': {
                                    'type': 'base64',
                                    'media_type': c.get('media_type', 'image/png'),
                                    'data': c.get('data', ''),
                                },
                            })
                        elif isinstance(c, dict):
                            parts.append({
                                'type': 'text',
                                'text': c.get('text', str(c)),
                            })
                        else:
                            parts.append({'type': 'text', 'text': str(c)})
                    messages.append({'role': 'user', 'content': parts})
                else:
                    # 纯文本
                    messages.append({'role': 'user', 'content': content})
            elif role in ('BOT', 'assistant'):
                messages.append({'role': 'assistant', 'content': content})

        return messages, system

    def get_token_len(self, prompt: str) -> int:
        """获取 token 长度。

        使用 Anthropic 的 tokenizer（如果可用），否则回退到字符估算。
        """
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.key)
            # 使用 count_tokens API
            response = client.messages.count_tokens(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
            )
            return response.input_tokens
        except Exception:
            # 回退到 BaseAPIModel 的默认实现
            return super().get_token_len(prompt)
