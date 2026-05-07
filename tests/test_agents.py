"""Agent Wrappers 单元测试。"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from opencompass.agents.base_agent import AgentTask, AgentResult, BaseCodingAgent
from opencompass.sandbox.result import SandboxResult


class TestAgentTask(unittest.TestCase):
    """AgentTask 数据类测试。"""

    def test_basic_creation(self):
        task = AgentTask(description='Write a hello world function')
        self.assertEqual(task.description, 'Write a hello world function')
        self.assertEqual(task.language, 'python')
        self.assertEqual(task.difficulty, 'medium')
        self.assertEqual(task.max_tokens, 4096)
        self.assertEqual(task.test_cases, [])

    def test_with_test_cases(self):
        task = AgentTask(
            description='Add two numbers',
            test_cases=[
                {'input': '2 3', 'expected': '5'},
                {'input': '10 20', 'expected': '30'},
            ],
        )
        self.assertEqual(len(task.test_cases), 2)

    def test_task_id_auto_generated(self):
        task = AgentTask(description='test')
        self.assertIsNotNone(task.task_id)
        self.assertEqual(len(task.task_id), 8)


class TestAgentResult(unittest.TestCase):
    """AgentResult 数据类测试。"""

    def test_success_result(self):
        result = AgentResult(
            task_id='001',
            agent_name='claude-code',
            success=True,
            total_tests=3,
            passed_tests=3,
            generated_code='def solve(): pass',
            execution_time=2.5,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.passed_tests, 3)
        self.assertIsNone(result.error)

    def test_failure_result(self):
        result = AgentResult(
            task_id='002',
            agent_name='codex',
            success=False,
            total_tests=5,
            passed_tests=3,
            generated_code='def solve(): return 0',
            execution_time=1.2,
            error='Timeout in test 4',
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'Timeout in test 4')


def _make_concrete_agent(name='test-agent', sandbox=None):
    """创建一个可实例化的 BaseCodingAgent 子类。"""
    class ConcreteAgent(BaseCodingAgent):
        def generate_code(self, task):
            return 'def solution(): return 0', 0

    agent = ConcreteAgent(name=name, sandbox=sandbox)
    return agent


class TestBaseCodingAgent(unittest.TestCase):
    """BaseCodingAgent 测试。"""

    def test_cannot_instantiate_abstract(self):
        """测试抽象类不能直接实例化。"""
        with self.assertRaises(TypeError):
            BaseCodingAgent(name='test-agent')

    def test_extract_code_blocks_python(self):
        """测试从 markdown 提取 Python 代码块。"""
        code = BaseCodingAgent.extract_code_blocks(
            '```python\nprint("hello")\n```', 'python'
        )
        self.assertEqual(code, 'print("hello")')

    def test_extract_code_blocks_generic(self):
        """测试提取通用代码块。"""
        code = BaseCodingAgent.extract_code_blocks(
            '```\nprint("world")\n```', 'python'
        )
        self.assertEqual(code, 'print("world")')

    def test_extract_code_blocks_prefer_language(self):
        """测试优先提取匹配语言的代码块。"""
        text = '```javascript\nconsole.log("js")\n```\n```python\nprint("py")\n```'
        code = BaseCodingAgent.extract_code_blocks(text, 'python')
        self.assertEqual(code, 'print("py")')

    def test_extract_code_blocks_bash(self):
        """测试 Bash 代码提取。"""
        code = BaseCodingAgent.extract_code_blocks(
            '```bash\necho hello\n```', 'bash'
        )
        self.assertEqual(code, 'echo hello')

    def test_extract_code_blocks_no_block(self):
        """测试无代码块时返回原文。"""
        code = BaseCodingAgent.extract_code_blocks('print("plain")', 'python')
        self.assertEqual(code, 'print("plain")')

    def test_evaluate_no_tests(self):
        """测试无测试用例的评估。"""
        agent = _make_concrete_agent()
        result = agent.evaluate(AgentTask(description='test', test_cases=[]))
        self.assertTrue(result.success)
        self.assertEqual(result.total_tests, 0)
        self.assertIn('solution', result.generated_code)

    def test_evaluate_generation_error(self):
        """测试代码生成失败的评估。"""

        class FailAgent(BaseCodingAgent):
            def generate_code(self, task):
                raise RuntimeError("API unavailable")

        agent = FailAgent(name='fail-agent')
        agent.sandbox = MagicMock()

        result = agent.evaluate(AgentTask(description='test'))
        self.assertFalse(result.success)
        self.assertIn('API unavailable', result.error)

    def test_evaluate_with_tests_code_mode(self):
        """测试使用 code 模式的测试用例。"""

        class MockAgent(BaseCodingAgent):
            def generate_code(self, task):
                return 'def solution(): return 42', 10

        agent = MockAgent(name='mock')
        agent.sandbox = MagicMock()
        agent.sandbox.execute.return_value = SandboxResult(
            exit_code=0, stdout='', stderr=''
        )

        task = AgentTask(
            description='test',
            test_cases=[
                {'code': 'assert solution() == 42'},
                {'code': 'assert solution() + 1 == 43'},
            ],
        )

        result = agent.evaluate(task)
        self.assertTrue(result.success)
        self.assertEqual(result.passed_tests, 2)
        self.assertEqual(result.tokens_used, 10)

    def test_evaluate_partial_fail(self):
        """测试部分测试失败。"""

        class MockAgent(BaseCodingAgent):
            def generate_code(self, task):
                return 'def solution(): return 42', 10

        agent = MockAgent(name='mock')
        agent.sandbox = MagicMock()
        pass_r = SandboxResult(exit_code=0, stdout='', stderr='')
        fail_r = SandboxResult(exit_code=1, stdout='', stderr='assertion failed')
        agent.sandbox.execute.side_effect = [pass_r, fail_r]

        task = AgentTask(
            description='test',
            test_cases=[
                {'code': 'assert solution() == 42'},
                {'code': 'assert solution() == 99'},
            ],
        )

        result = agent.evaluate(task)
        self.assertFalse(result.success)
        self.assertEqual(result.passed_tests, 1)
        self.assertEqual(result.total_tests, 2)

    def test_evaluate_empty_code(self):
        """测试空代码生成。"""

        class EmptyAgent(BaseCodingAgent):
            def generate_code(self, task):
                return '', 0

        agent = EmptyAgent(name='empty')
        agent.sandbox = MagicMock()

        result = agent.evaluate(AgentTask(description='test'))
        self.assertFalse(result.success)
        self.assertIn('empty', result.error.lower())


if __name__ == '__main__':
    unittest.main()
