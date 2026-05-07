# flake8: noqa: E501
"""Gemini API 实现（增强版）。

支持：
- 自定义 base_url（代理中转）
- systemInstruction 字段（正确传递 system prompt）
- Vision 输入（图片）
- responseModalities（文本/图片生成）
- 更好的错误处理
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Union

import requests

from opencompass.utils.prompt import PromptList

from .base_api import BaseAPIModel

PromptType = Union[PromptList, str]


class Gemini(BaseAPIModel):
    """Model wrapper around Gemini models.

    使用 Gemini 原生 API 格式（generateContent endpoint）。

    Args:
        path (str): 模型名称，如 'gemini-2.5-flash'。
        key (str): API Key. 'ENV' 则从环境变量 GEMINI_API_KEY 读取。
        query_per_second (int): 每秒最大请求数。
        max_seq_len (int): 最大序列长度。
        meta_template (Dict, optional): 元提示模板。
        retry (int): 失败重试次数。
        temperature (float): 采样温度。
        top_p (float): Top-P 采样。
        top_k (float): Top-K 采样。
        base_url (str): API Base URL，默认 'https://generativelanguage.googleapis.com'。
        max_output_tokens (int): 最大输出 token 数。
        response_modalities (list): 输出模态，如 ['TEXT'] 或 ['TEXT', 'IMAGE']。
    """

    def __init__(
        self,
        key: str = 'ENV',
        path: str = 'gemini-2.5-flash',
        query_per_second: int = 2,
        max_seq_len: int = 1000000,
        meta_template: Optional[Dict] = None,
        retry: int = 2,
        temperature: float = 1.0,
        top_p: float = 0.8,
        top_k: float = 10.0,
        base_url: str = 'https://generativelanguage.googleapis.com',
        max_output_tokens: int = 8192,
        response_modalities: Optional[List[str]] = None,
    ):
        super().__init__(
            path=path,
            max_seq_len=max_seq_len,
            query_per_second=query_per_second,
            meta_template=meta_template,
            retry=retry,
        )

        if key == 'ENV':
            if 'GEMINI_API_KEY' not in os.environ:
                raise ValueError('GEMINI API key is not set.')
            key = os.environ.get('GEMINI_API_KEY')

        self.key = key
        self.base_url = base_url.rstrip('/')
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_output_tokens = max_output_tokens
        self.response_modalities = response_modalities or ['TEXT']

        self.headers = {
            'content-type': 'application/json',
            'x-goog-api-key': self.key,
        }

    @property
    def url(self) -> str:
        """构建 API URL。"""
        return f'{self.base_url}/v1beta/models/{self.path}:generateContent'

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
        self.flush()
        return results

    def _generate(
        self,
        input: PromptType,
        max_out_len: int = 512,
    ) -> str:
        """Generate results given an input.

        Args:
            input (PromptType): A string or PromptDict.
            max_out_len (int): The maximum length of the output.

        Returns:
            str: The generated string.
        """
        assert isinstance(input, (str, PromptList))

        contents, system_instruction = self._convert_input(input)
        data = self._build_request(contents, system_instruction, max_out_len)

        for attempt in range(self.retry):
            self.wait()
            try:
                raw_response = requests.post(
                    self.url,
                    headers=self.headers,
                    data=json.dumps(data),
                    timeout=120,
                )

                try:
                    response = raw_response.json()
                except requests.JSONDecodeError:
                    self.logger.error(
                        f'JSON decode error, status={raw_response.status_code}, '
                        f'body={raw_response.content[:500]}'
                    )
                    time.sleep(2)
                    continue

                if raw_response.status_code == 200:
                    return self._parse_response(response)

                # 错误处理
                error_msg = ''
                if 'error' in response:
                    error_msg = response['error'].get('message', str(response['error']))
                    error_code = response['error'].get('code', '')
                    self.logger.error(f'Gemini API error [{error_code}]: {error_msg}')

                    if error_code == 429 or 'RESOURCE_EXHAUSTED' in error_msg:
                        time.sleep(5 * (attempt + 1))
                        continue
                    elif error_code == 400:
                        # Bad request，可能 prompt 有问题
                        continue
                    elif error_code in (500, 503):
                        time.sleep(10)
                        continue

                self.logger.error(f'Gemini API request failed: {response}')
                time.sleep(5)

            except requests.ConnectionError:
                self.logger.error('Connection error, retrying...')
                time.sleep(5)
            except requests.Timeout:
                self.logger.error('Request timed out, retrying...')
                time.sleep(5)

        raise RuntimeError(
            f'Calling Gemini API failed after {self.retry} retries. '
            f'Check the logs for details.'
        )

    def _convert_input(self, input: PromptType) -> tuple:
        """将 OpenCompass 格式转换为 Gemini API 格式。

        Args:
            input: 字符串或 PromptList。

        Returns:
            (contents, system_instruction) 元组。
        """
        if isinstance(input, str):
            contents = [{'role': 'user', 'parts': [{'text': input}]}]
            return contents, None

        # PromptList 格式
        contents = []
        system_instruction = None

        for item in input:
            role = item.get('role', 'HUMAN')
            content = item.get('prompt', item.get('content', ''))

            if role == 'SYSTEM':
                if system_instruction is None:
                    system_instruction = content
                else:
                    system_instruction += '\n' + content
                continue

            if isinstance(content, list):
                # 多模态内容（vision）
                parts = []
                for c in content:
                    if isinstance(c, dict):
                        if c.get('type') == 'image':
                            parts.append({
                                'inline_data': {
                                    'mime_type': c.get('media_type', 'image/png'),
                                    'data': c.get('data', ''),
                                },
                            })
                        else:
                            parts.append({'text': c.get('text', str(c))})
                    else:
                        parts.append({'text': str(c)})
            else:
                parts = [{'text': content}]

            gemini_role = 'user' if role in ('HUMAN', 'user') else 'model'
            contents.append({'role': gemini_role, 'parts': parts})

        return contents, system_instruction

    def _build_request(self, contents, system_instruction, max_out_len) -> dict:
        """构建 API 请求体。"""
        data = {
            'contents': contents,
            'safetySettings': [
                {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'},
                {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
                {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
                {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
            ],
            'generationConfig': {
                'temperature': self.temperature,
                'maxOutputTokens': min(max_out_len, self.max_output_tokens),
                'topP': self.top_p,
                'topK': self.top_k,
                'responseModalities': self.response_modalities,
            },
        }

        if system_instruction:
            data['systemInstruction'] = {
                'parts': [{'text': system_instruction}]
            }

        return data

    def _parse_response(self, response: dict) -> str:
        """解析 API 响应。"""
        if 'candidates' not in response:
            self.logger.error(f'No candidates in response: {response}')
            return ''

        candidate = response['candidates'][0]

        # 检查是否被安全策略阻断
        if candidate.get('finishReason') in ('SAFETY', 'BLOCK'):
            return "Response blocked due to safety policies."

        content = candidate.get('content')
        if not content:
            return ''

        parts = content.get('parts', [])
        if not parts:
            return ''

        # 提取所有文本部分
        text_parts = []
        image_parts = []
        for part in parts:
            if 'text' in part:
                text_parts.append(part['text'])
            elif 'inlineData' in part:
                # 图片输出 — 返回 base64 编码
                image_parts.append({
                    'mime_type': part['inlineData'].get('mimeType', 'image/png'),
                    'data': part['inlineData'].get('data', ''),
                })

        result = '\n'.join(text_parts).strip()

        # 如果有图片输出，附加提示
        if image_parts:
            result += '\n[Image output: ' + str(len(image_parts)) + ' image(s) generated]'

        return result
