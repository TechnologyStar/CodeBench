"""基于子进程的轻量级代码执行沙箱。"""

import logging
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Dict, List, Optional

from .result import SandboxResult

logger = logging.getLogger(__name__)

# 子进程内存限制启动脚本（Python），通过 preexec_fn 设置
_LIMITER_SCRIPT = '''
import os, resource, sys

def set_limits(max_memory_bytes):
    """设置子进程资源限制。"""
    # 内存限制（RLIMIT_AS = 地址空间）
    if max_memory_bytes > 0:
        resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))

if __name__ == '__main__':
    max_memory = int(sys.argv[1])
    set_limits(max_memory)
    exec_path = sys.argv[2]
    exec_args = sys.argv[3:]
    os.execvp(exec_path, [exec_path] + exec_args)
'''


class SubprocessSandbox:
    """基于子进程的轻量级代码执行沙箱。

    功能：
    - 超时控制
    - 内存限制（resource.setrlimit RLIMIT_AS）
    - 工作目录隔离（临时目录）
    - stdout/stderr 捕获
    - 返回执行结果（exit_code, stdout, stderr, timed_out, memory_exceeded）

    用法：
        sandbox = SubprocessSandbox(timeout=30, max_memory_mb=512)
        result = sandbox.execute(code="print('hello')", language='python')
        print(result.stdout)  # "hello\\n"
    """

    # 支持的语言及其执行命令映射
    LANGUAGE_RUNNERS = {
        'python':  ('python3', '.py'),
        'python3': ('python3', '.py'),
        'bash':    ('bash',   '.sh'),
        'javascript': ('node', '.js'),
        'java':    ('java',   '.java'),
        'cpp':     None,  # 需要编译，单独处理
    }

    def __init__(self, timeout: int = 30, max_memory_mb: int = 512):
        """初始化沙箱。

        Args:
            timeout: 默认执行超时时间（秒）。
            max_memory_mb: 默认最大内存限制（MB）。
        """
        self.default_timeout = timeout
        self.default_max_memory_mb = max_memory_mb

    def execute(
        self,
        code: str,
        language: str = 'python',
        timeout: Optional[int] = None,
        max_memory_mb: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        """执行代码片段。

        Args:
            code: 要执行的代码。
            language: 编程语言（python/python3/bash/javascript/java/cpp）。
            timeout: 执行超时时间（秒），None 使用默认值。
            max_memory_mb: 内存限制（MB），None 使用默认值。
            env: 额外环境变量。
            files: 额外文件，{filename: content}。

        Returns:
            SandboxResult 执行结果。
        """
        if timeout is None:
            timeout = self.default_timeout
        if max_memory_mb is None:
            max_memory_mb = self.default_max_memory_mb

        max_memory_bytes = max_memory_mb * 1024 * 1024

        # 创建临时工作目录
        work_dir = tempfile.mkdtemp(prefix='oc_sandbox_')
        logger.debug('Sandbox work directory: %s', work_dir)

        try:
            # 写入额外文件
            if files:
                for fname, content in files.items():
                    fpath = os.path.join(work_dir, fname)
                    os.makedirs(os.path.dirname(fpath), exist_ok=True)
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.write(content)

            # 写入主代码文件
            cmd = self._build_command(code, language, work_dir)
            if cmd is None:
                return SandboxResult(
                    exit_code=-1,
                    stdout='',
                    stderr=f'Unsupported language: {language}',
                )

            # 构建执行环境
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)

            # 准备 preexec_fn：设置内存限制
            def _set_limits():
                if max_memory_bytes > 0:
                    try:
                        resource.setrlimit(
                            resource.RLIMIT_AS,
                            (max_memory_bytes, max_memory_bytes),
                        )
                    except (ValueError, OSError) as e:
                        logger.warning('Failed to set memory limit: %s', e)

            start_time = time.monotonic()

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=exec_env,
                    preexec_fn=_set_limits,
                )
                elapsed = time.monotonic() - start_time
                return SandboxResult(
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    execution_time=round(elapsed, 3),
                )
            except subprocess.TimeoutExpired as e:
                elapsed = time.monotonic() - start_time
                stdout = e.stdout if e.stdout else ''
                stderr = e.stderr if e.stderr else ''
                if isinstance(stdout, bytes):
                    stdout = stdout.decode('utf-8', errors='replace')
                if isinstance(stderr, bytes):
                    stderr = stderr.decode('utf-8', errors='replace')
                return SandboxResult(
                    exit_code=-1,
                    stdout=stdout,
                    stderr=stderr or f'Execution timed out after {timeout}s',
                    timed_out=True,
                    execution_time=round(elapsed, 3),
                )
            except MemoryError:
                elapsed = time.monotonic() - start_time
                return SandboxResult(
                    exit_code=-1,
                    stdout='',
                    stderr=f'Memory limit exceeded ({max_memory_mb}MB)',
                    memory_exceeded=True,
                    execution_time=round(elapsed, 3),
                )
        finally:
            # 清理临时目录
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception as e:
                logger.warning('Failed to cleanup work directory: %s', e)

    def _build_command(
        self, code: str, language: str, work_dir: str
    ) -> Optional[List[str]]:
        """根据语言构建执行命令。

        Args:
            code: 源代码。
            language: 编程语言。
            work_dir: 工作目录路径。

        Returns:
            命令列表，不支持的语言返回 None。
        """
        language = language.lower()
        runner = self.LANGUAGE_RUNNERS.get(language)

        if runner is None and language == 'cpp':
            return self._build_cpp_command(code, work_dir)

        if runner is None:
            return None

        exe, ext = runner

        if language == 'bash':
            # Bash 直接通过 -c 执行
            return ['bash', '-c', code]

        # 其他语言写入文件后执行
        src_file = os.path.join(work_dir, f'main{ext}')
        with open(src_file, 'w', encoding='utf-8') as f:
            f.write(code)

        if language in ('java',):
            # Java 需要文件名与类名匹配；简单处理：用 Main 类名
            main_file = os.path.join(work_dir, 'Main.java')
            with open(main_file, 'w', encoding='utf-8') as f:
                f.write(code)
            # 编译
            compile_result = subprocess.run(
                ['javac', 'Main.java'],
                cwd=work_dir,
                capture_output=True,
                text=True,
            )
            if compile_result.returncode != 0:
                # 编译失败，返回编译错误信息
                # 把编译错误写入 stderr 文件，让调用方读到
                err_file = os.path.join(work_dir, 'compile_error.txt')
                with open(err_file, 'w') as f:
                    f.write(compile_result.stderr)
                # 这里返回的命令会被执行，所以返回 cat 编译错误
                # 实际上我们不应该让它执行，但为了返回错误信息
                # 直接返回一个会失败的命令
                return ['cat', err_file]
            return ['java', '-cp', work_dir, 'Main']

        return [exe, src_file]

    def _build_cpp_command(self, code: str, work_dir: str) -> Optional[List[str]]:
        """构建 C++ 编译和执行命令。

        Args:
            code: C++ 源代码。
            work_dir: 工作目录路径。

        Returns:
            命令列表。
        """
        src_file = os.path.join(work_dir, 'main.cpp')
        bin_file = os.path.join(work_dir, 'main')

        with open(src_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # 编译
        compile_result = subprocess.run(
            ['g++', '-O2', '-o', bin_file, src_file],
            cwd=work_dir,
            capture_output=True,
            text=True,
        )
        if compile_result.returncode != 0:
            # 编译失败
            logger.warning('C++ compilation failed: %s', compile_result.stderr)
            # 返回一个会打印编译错误的命令
            echo_file = os.path.join(work_dir, 'compile_error.txt')
            with open(echo_file, 'w') as f:
                f.write(compile_result.stderr)
            return ['cat', echo_file]

        return [bin_file]
