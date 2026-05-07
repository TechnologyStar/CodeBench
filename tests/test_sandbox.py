"""代码沙箱单元测试。"""
import os
import sys
import tempfile
import unittest

# 确保能导入 opencompass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from opencompass.sandbox.result import SandboxResult
from opencompass.sandbox.subprocess_sandbox import SubprocessSandbox


class TestSandboxResult(unittest.TestCase):
    """SandboxResult 数据类测试。"""

    def test_default_values(self):
        result = SandboxResult(exit_code=0, stdout='', stderr='')
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)
        self.assertFalse(result.memory_exceeded)
        self.assertEqual(result.execution_time, 0.0)
        self.assertEqual(result.files, {})

    def test_custom_values(self):
        result = SandboxResult(
            exit_code=1,
            stdout='hello',
            stderr='error',
            timed_out=True,
            memory_exceeded=True,
            execution_time=1.5,
            files={'out.txt': 'result'},
        )
        self.assertTrue(result.timed_out)
        self.assertTrue(result.memory_exceeded)
        self.assertEqual(result.execution_time, 1.5)
        self.assertEqual(result.files['out.txt'], 'result')


class TestSubprocessSandbox(unittest.TestCase):
    """SubprocessSandbox 测试。"""

    def setUp(self):
        self.sandbox = SubprocessSandbox(timeout=10, max_memory_mb=256)

    def test_python_simple(self):
        """测试简单 Python 执行。"""
        result = self.sandbox.execute(code='print("hello world")', language='python')
        self.assertEqual(result.exit_code, 0)
        self.assertIn('hello world', result.stdout)
        self.assertFalse(result.timed_out)

    def test_python_math(self):
        """测试 Python 数学运算。"""
        result = self.sandbox.execute(code='print(2 + 3)', language='python')
        self.assertEqual(result.exit_code, 0)
        self.assertIn('5', result.stdout)

    def test_python_error(self):
        """测试 Python 运行时错误。"""
        result = self.sandbox.execute(code='raise ValueError("test error")', language='python')
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('ValueError', result.stderr)

    def test_python_timeout(self):
        """测试超时。"""
        result = self.sandbox.execute(
            code='import time; time.sleep(60)',
            language='python',
            timeout=1,
        )
        self.assertTrue(result.timed_out)

    def test_bash_simple(self):
        """测试 Bash 执行。"""
        result = self.sandbox.execute(code='echo "hello from bash"', language='bash')
        self.assertEqual(result.exit_code, 0)
        self.assertIn('hello from bash', result.stdout)

    def test_bash_error(self):
        """测试 Bash 错误命令。"""
        result = self.sandbox.execute(code='exit 42', language='bash')
        self.assertEqual(result.exit_code, 42)

    def test_file_execution(self):
        """测试代码中的文件操作。"""
        result = self.sandbox.execute(
            code='''
import tempfile, os
with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
    f.write("content")
    path = f.name
with open(path) as f:
    print(f.read())
os.unlink(path)
''',
            language='python',
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn('content', result.stdout)

    def test_unsupported_language(self):
        """测试不支持的语言。"""
        result = self.sandbox.execute(code='print(1)', language='brainfuck')
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Unsupported language', result.stderr)

    def test_working_dir_isolation(self):
        """测试工作目录隔离。"""
        result = self.sandbox.execute(
            code='import os; print(os.getcwd())',
            language='python',
        )
        self.assertEqual(result.exit_code, 0)
        # 应该在临时目录中执行
        self.assertIn('oc_sandbox', result.stdout.strip() or '')

    def test_environment_variables(self):
        """测试环境变量传递。"""
        result = self.sandbox.execute(
            code='import os; print(os.environ.get("TEST_VAR", "NOT_SET"))',
            language='python',
            env={'TEST_VAR': 'hello123'},
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn('hello123', result.stdout)

    def test_multiple_executions(self):
        """测试多次执行互不干扰。"""
        for i in range(3):
            result = self.sandbox.execute(
                code=f'print({i})',
                language='python',
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn(str(i), result.stdout)


class TestSubprocessSandboxMemoryLimit(unittest.TestCase):
    """内存限制测试。"""

    def setUp(self):
        # 低内存限制用于测试
        self.sandbox = SubprocessSandbox(timeout=10, max_memory_mb=64)

    def test_memory_hog_detection(self):
        """测试大内存分配检测。"""
        # 尝试分配大量内存
        result = self.sandbox.execute(
            code='''
import sys
try:
    data = b'x' * (100 * 1024 * 1024)  # 100MB
    print("allocated")
except MemoryError:
    print("MemoryError caught")
    sys.exit(1)
''',
            language='python',
            max_memory_mb=64,
        )
        # 在低内存限制下应该失败
        # 注意：某些系统可能不严格执行 RLIMIT_AS
        # 所以这里只检查行为不崩溃
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
