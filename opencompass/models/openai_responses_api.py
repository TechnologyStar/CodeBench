"""OpenAI Responses API 实现。

OpenAI Responses API 是比 Chat Completions 更新的接口（2025 年推出），
支持 reasoning、tool use 等新特性。

使用 OpenAI Python SDK 的 client.responses.create() 方法。
"""
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Union

from opencompass.registry import MODELS
from opencompass.utils.prompt import PromptList

from .base_api import BaseAPIModel

logger = logging.getLogger(__name__)

PromptType = Union[PromptList, str]

OAI_REASONING_MODEL_LIST = ['o1', 'o3', 'o4', 'gpt-5']


@MODELS.register_module()
class OpenAIResponses(BaseAPIModel):
    """Model wrapper around OpenAI Responses API.

    使用 OpenAI 的 Responses API（非 Chat Completions）。

    Args:
        path (str): 模型名称，如 'gpt-4o'、'o3'。
        key (str): API Key. 'ENV' 则从环境变量 OPENAI_API_KEY 读取。
        base_url (str): API Base URL，默认 'https://api.openai.com/v1'。
        query_per_second (int): 每秒最大请求数。
        max_seq_len (int): 最大序列长度。
        meta_template (Dict, optional): 元提示模板。
        retry (int): 失败重试次数。
        max_output_tokens (int): 最大输出 token 数。
        reasoning (dict): Reasoning 配置，如 {'effort': 'medium'}。
        temperature (float, optional): 采样温度。
        timeout (int): 请求超时秒数。
    """

    def __init__(
        self,
        path: str = 'gpt-4o',
        key: str = 'ENV',
        base_url: Optional[str] = None,
        query_per_second: int = 1,
        max_seq_len: int = 128000,
        meta_template: Optional[Dict] = None,
        retry: int = 2,
        max_output_tokens: int = 4096,
        reasoning: Optional[Dict] = None,
        temperature: Optional[float] = None,
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
            if 'OPENAI_API_KEY' not in os.environ:
                raise ValueError('OPENAI_API_KEY is not set.')
            self.keys = os.getenv('OPENAI_API_KEY').split(',')
        else:
            self.keys = [key] if isinstance(key, str) else key

        self.key_ctr = 0
        self.base_url = base_url or os.environ.get(
            'OPENAI_BASE_URL', 'https://api.openai.com/v1'
        )
        self.max_output_tokens = max_output_tokens
        self.reasoning = reasoning
        self.temperature = temperature
        self.timeout = timeout
        self._client = None
        self._tokenizer = None

    def _get_client(self, key: str):
        """创建 OpenAI 客户端。"""
        try:
            from openai import OpenAI
            return OpenAI(
                api_key=key,
                base_url=self.base_url,
            )
        except ImportError:
            raise ImportError(
                'openai package is required. Install with "pip install openai".'
            )

    def _next_key(self) -> str:
        """轮转 API Key。"""
        key = self.keys[self.key_ctr % len(self.keys)]
        self.key_ctr += 1
        return key

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
            input (PromptType): A string or PromptDict.
            max_out_len (int): The maximum length of the output.

        Returns:
            str: The generated string.
        """
        assert isinstance(input, (str, PromptList))

        # 转换为 OpenAI 消息格式
        messages = self._convert_messages(input)

        # Responses API 的 input 参数
        if isinstance(messages, str) and not messages.startswith('['):
            api_input = messages
        elif isinstance(messages, list) and len(messages) == 1 and messages[0].get('role') == 'user':
            api_input = messages[0]['content']
        else:
            api_input = messages

        kwargs = {
            'model': self.path,
            'input': api_input,
            'max_output_tokens': max_out_len or self.max_output_tokens,
        }

        if self.reasoning:
            kwargs['reasoning'] = self.reasoning

        if self.temperature is not None:
            kwargs['temperature'] = self.temperature

        for attempt in range(self.retry):
            self.wait()
            key = self._next_key()

            try:
                client = self._get_client(key)
                response = client.responses.create(**kwargs)

                # 提取输出文本
                output_text = getattr(response, 'output_text', '')
                if not output_text:
                    # 尝试从 output 中提取
                    if hasattr(response, 'output') and response.output:
                        for item in response.output:
                            if hasattr(item, 'content'):
                                for block in item.content:
                                    if hasattr(block, 'text') and block.text:
                                        output_text += block.text
                            elif hasattr(item, 'type') and item.type == 'message':
                                for content_block in item.content:
                                    if hasattr(content_block, 'text') and content_block.text:
                                        output_text += content_block.text

                return output_text.strip()

            except Exception as e:
                error_str = str(e)
                logger.error(
                    f'OpenAI Responses API error (attempt {attempt + 1}/{self.retry}): {error_str}'
                )

                if 'rate_limit' in error_str.lower():
                    time.sleep(5 * (attempt + 1))
                elif 'insufficient_quota' in error_str.lower():
                    raise
                elif 'timeout' in error_str.lower():
                    time.sleep(3)
                else:
                    time.sleep(2)

        raise RuntimeError(
            f'Calling OpenAI Responses API failed after {self.retry} retries. '
            f'Check the logs for details.'
        )

    def _convert_messages(self, input: PromptType):
        """将 OpenCompass 格式转换为 OpenAI 消息格式。"""
        if isinstance(input, str):
            return input

        messages = []
        for item in input:
            role = item.get('role', 'HUMAN')
            content = item.get('prompt', item.get('content', ''))

            if role == 'SYSTEM':
                messages.append({'role': 'system', 'content': content})
            elif role in ('HUMAN', 'user'):
                messages.append({'role': 'user', 'content': content})
            elif role in ('BOT', 'assistant'):
                messages.append({'role': 'assistant', 'content': content})

        return messages

    def get_token_len(self, prompt: str) -> int:
        """获取 token 长度。

        尝试使用 tiktoken，失败则回退到 BaseAPIModel 的默认实现。
        """
        if self._tokenizer is None:
            try:
                import tiktoken
                # 尝试加载模型对应的 tokenizer
                encodings = tiktoken.model.MODEL_TO_ENCODING
                self._tokenizer = tiktoken.encoding_for_model(
                    self.path if self.path in encodings else 'gpt-4'
                )
            except Exception:
                return super().get_token_len(prompt)

        return len(self._tokenizer.encode(prompt, disallowed_special=()))
