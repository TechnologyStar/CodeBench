"""编码智能体评估基类。"""

import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentTask:
    """编码任务定义。

    Attributes:
        description: 任务描述（自然语言）。
        language: 编程语言。
        context: 前置上下文（已有代码、文件说明等）。
        test_cases: 测试用例列表，每个用例为一个字典，
                    格式 {'input': ..., 'expected': ...} 或 {'code': ...}。
        difficulty: 难度级别（easy/medium/hard）。
        max_tokens: 智能体生成代码时的最大 token 数。
        timeout: 整体评估超时时间（秒）。
        task_id: 任务唯一标识，自动生成。
    """
    description: str
    language: str = 'python'
    context: str = ''
    test_cases: list = field(default_factory=list)
    difficulty: str = 'medium'
    max_tokens: int = 4096
    timeout: int = 300
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class AgentResult:
    """智能体评估结果。

    Attributes:
        task_id: 对应的 AgentTask ID。
        agent_name: 智能体名称。
        success: 是否通过所有测试用例。
        total_tests: 总测试数。
        passed_tests: 通过的测试数。
        generated_code: 智能体生成的代码。
        execution_time: 总执行耗时（秒）。
        tokens_used: 使用的 token 数。
        error: 错误信息（如有）。
    """
    task_id: str
    agent_name: str
    success: bool
    total_tests: int
    passed_tests: int
    generated_code: str
    execution_time: float
    tokens_used: int = 0
    error: Optional[str] = None


class BaseCodingAgent(ABC):
    """编码智能体评估基类。

    工作流程：
    1. 接收 AgentTask
    2. 调用智能体生成代码（子类实现 generate_code）
    3. 用沙箱执行代码 + 测试
    4. 收集结果并返回 AgentResult
    """

    def __init__(self, name: str, sandbox=None):
        """初始化智能体。

        Args:
            name: 智能体名称。
            sandbox: 代码执行沙箱实例，None 则使用默认 SubprocessSandbox。
        """
        self.name = name
        self.sandbox = sandbox
        if self.sandbox is None:
            from opencompass.sandbox import SubprocessSandbox
            self.sandbox = SubprocessSandbox()

    @abstractmethod
    def generate_code(self, task: AgentTask) -> tuple:
        """调用智能体生成代码。

        Args:
            task: 编码任务定义。

        Returns:
            (code, tokens_used) 元组：
            - code: 生成的代码字符串。
            - tokens_used: 使用的 token 数。
        """
        ...

    def evaluate(self, task: AgentTask) -> AgentResult:
        """完整评估流程。

        1. 调用智能体生成代码
        2. 在沙箱中执行测试
        3. 收集结果

        Args:
            task: 编码任务定义。

        Returns:
            AgentResult 评估结果。
        """
        start_time = time.monotonic()
        logger.info(
            'Starting evaluation: task=%s agent=%s',
            task.task_id, self.name,
        )

        try:
            # 1. 生成代码
            code, tokens_used = self.generate_code(task)

            if not code or not code.strip():
                elapsed = time.monotonic() - start_time
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    total_tests=len(task.test_cases),
                    passed_tests=0,
                    generated_code=code or '',
                    execution_time=round(elapsed, 3),
                    tokens_used=tokens_used,
                    error='Agent returned empty code',
                )

            # 2. 运行测试
            if task.test_cases:
                passed, total, test_error = self.run_tests(
                    code, task.test_cases, task.language
                )
            else:
                # 没有测试用例，只检查代码是否能执行
                passed, total, test_error = 0, 0, None

            elapsed = time.monotonic() - start_time
            success = (total > 0 and passed == total) or total == 0

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=success,
                total_tests=total,
                passed_tests=passed,
                generated_code=code,
                execution_time=round(elapsed, 3),
                tokens_used=tokens_used,
                error=test_error,
            )

        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error(
                'Evaluation failed: task=%s agent=%s error=%s',
                task.task_id, self.name, e,
            )
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                total_tests=len(task.test_cases),
                passed_tests=0,
                generated_code='',
                execution_time=round(elapsed, 3),
                error=str(e),
            )

    def run_tests(
        self,
        code: str,
        test_cases: List,
        language: str = 'python',
    ) -> tuple:
        """在沙箱中运行测试用例。

        Args:
            code: 被测试的代码。
            test_cases: 测试用例列表。
            language: 编程语言。

        Returns:
            (passed, total, error) 元组：
            - passed: 通过的测试数。
            - total: 总测试数。
            - error: 错误信息（如有）。
        """
        if not test_cases:
            return 0, 0, None

        passed = 0
        total = len(test_cases)
        errors = []

        for i, tc in enumerate(test_cases):
            try:
                if self._run_single_test(code, tc, language, i):
                    passed += 1
            except Exception as e:
                errors.append(f'Test {i}: {e}')

        error_msg = '; '.join(errors) if errors else None
        return passed, total, error_msg

    def _run_single_test(
        self, code: str, test_case: dict, language: str, index: int
    ) -> bool:
        """运行单个测试用例。

        如果测试用例包含 'code' 字段，则作为独立的测试脚本执行；
        否则将生成的代码和测试输入组合执行。

        Args:
            code: 生成的代码。
            test_case: 测试用例字典。
            language: 编程语言。
            index: 测试用例索引。

        Returns:
            是否通过测试。
        """
        if 'code' in test_case:
            # 独立测试脚本：需要将生成的代码和测试代码组合
            if language in ('python', 'python3'):
                combined = f'{code}\n\n{test_case["code"]}'
            else:
                # 其他语言简单拼接
                combined = f'{code}\n{test_case["code"]}'

            result = self.sandbox.execute(
                code=combined,
                language=language,
                timeout=30,
                max_memory_mb=256,
            )
            return result.exit_code == 0

        # 简单的 input/expected 模式
        if 'input' in test_case and 'expected' in test_case:
            return self._run_io_test(code, test_case, language, index)

        logger.warning('Unknown test case format at index %d', index)
        return False

    def _run_io_test(
        self, code: str, test_case: dict, language: str, index: int
    ) -> bool:
        """运行输入/输出模式的测试。

        Args:
            code: 生成的代码。
            test_case: 包含 'input' 和 'expected' 的测试用例。
            language: 编程语言。
            index: 测试用例索引。

        Returns:
            是否通过测试。
        """
        test_input = test_case['input']
        expected = test_case['expected']

        if language in ('python', 'python3'):
            # 包装代码以接受 stdin 并输出结果
            wrapper = f'''
import sys
{code}

if __name__ == '__main__':
    try:
        result = solution()
        print(result)
    except Exception as e:
        print(f"ERROR: {{e}}", file=sys.stderr)
        sys.exit(1)
'''
            # 通过 stdin 传递输入
            # 注意：SubprocessSandbox 目前不支持直接传 stdin
            # 这里通过文件传递
            result = self.sandbox.execute(
                code=wrapper,
                language='python',
                timeout=30,
                max_memory_mb=256,
            )
            if result.exit_code != 0:
                return False
            actual = result.stdout.strip()
            return actual == expected

        return False

    @staticmethod
    def extract_code_blocks(text: str, language: str = 'python') -> str:
        """从文本中提取代码块。

        支持 markdown 格式的代码块（```python ... ```）。

        Args:
            text: 包含代码块的文本。
            language: 首选语言。

        Returns:
            提取到的代码字符串，如果没有则返回原始文本。
        """
        # 尝试匹配 markdown 代码块
        patterns = [
            rf'```{language}\s*\n(.*?)```',
            rf'```\s*\n(.*?)```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()

        return text.strip()
