"""基于 Docker 的强隔离代码执行沙箱。"""

import logging
import time
from typing import Dict, List, Optional

from .result import SandboxResult

logger = logging.getLogger(__name__)

# 各语言对应的 Docker 镜像及文件扩展名
_LANGUAGE_CONFIG = {
    'python':     {'image': 'python:3.11-slim',  'ext': '.py',  'cmd': 'python3 {file}'},
    'python3':    {'image': 'python:3.11-slim',  'ext': '.py',  'cmd': 'python3 {file}'},
    'bash':       {'image': 'bash:5',            'ext': '.sh',  'cmd': 'bash {file}'},
    'javascript': {'image': 'node:20-slim',      'ext': '.js',  'cmd': 'node {file}'},
    'java':       {'image': 'openjdk:21-slim',   'ext': '.java','cmd': None},  # 特殊处理
    'cpp':        {'image': 'gcc:13',            'ext': '.cpp', 'cmd': None},  # 特殊处理
}


class DockerSandbox:
    """基于 Docker 的强隔离代码执行沙箱。

    功能：
    - 完全的进程/网络/文件系统隔离
    - CPU 和内存资源限制
    - 可选网络禁用
    - 预构建镜像支持

    用法：
        sandbox = DockerSandbox(mem_limit='512m', network_disabled=True)
        result = sandbox.execute(code="print('hello')", language='python')
        print(result.stdout)

    注意：
        需要安装 docker Python 包（pip install docker），
        以及运行中的 Docker daemon。
    """

    def __init__(
        self,
        timeout: int = 30,
        mem_limit: str = '512m',
        cpu_limit: float = 1.0,
        network_disabled: bool = True,
    ):
        """初始化 Docker 沙箱。

        Args:
            timeout: 默认执行超时时间（秒）。
            mem_limit: Docker 内存限制（如 '512m', '1g'）。
            cpu_limit: CPU 核心数限制。
            network_disabled: 是否禁用网络。

        Raises:
            ImportError: 如果 docker 包未安装。
        """
        try:
            import docker
            self._docker = docker.from_env()
        except ImportError:
            raise ImportError(
                'Docker sandbox requires the "docker" Python package. '
                'Install it with: pip install docker'
            )

        self.default_timeout = timeout
        self.mem_limit = mem_limit
        self.cpu_limit = cpu_limit
        self.network_disabled = network_disabled

    def execute(
        self,
        code: str,
        language: str = 'python',
        image: Optional[str] = None,
        timeout: Optional[int] = None,
        mem_limit: Optional[str] = None,
        cpu_limit: Optional[float] = None,
        network_disabled: Optional[bool] = None,
        env: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        """在 Docker 容器中执行代码。

        Args:
            code: 要执行的代码。
            language: 编程语言。
            image: Docker 镜像名，None 使用语言默认镜像。
            timeout: 执行超时时间（秒）。
            mem_limit: 内存限制。
            cpu_limit: CPU 限制。
            network_disabled: 是否禁用网络。
            env: 额外环境变量。
            files: 额外文件，{filename: content}。

        Returns:
            SandboxResult 执行结果。
        """
        if timeout is None:
            timeout = self.default_timeout
        if mem_limit is None:
            mem_limit = self.mem_limit
        if cpu_limit is None:
            cpu_limit = self.cpu_limit
        if network_disabled is None:
            network_disabled = self.network_disabled

        language = language.lower()
        config = _LANGUAGE_CONFIG.get(language)
        if config is None:
            return SandboxResult(
                exit_code=-1,
                stdout='',
                stderr=f'Unsupported language: {language}',
            )

        if image is None:
            image = config['image']

        ext = config['ext']
        main_file = f'main{ext}'
        exec_cmd = config['cmd']

        # 构建容器内的文件列表
        container_files = {}
        if files:
            container_files.update(files)
        container_files[main_file] = code

        # 处理 Java 编译
        if language == 'java':
            container_files['run.sh'] = (
                f'javac {main_file} && java -cp /workspace Main\n'
            )
            exec_cmd = 'bash /workspace/run.sh'

        # 处理 C++ 编译
        if language == 'cpp':
            container_files['run.sh'] = (
                f'g++ -O2 -o /workspace/main_bin /workspace/{main_file} '
                f'&& /workspace/main_bin\n'
            )
            exec_cmd = 'bash /workspace/run.sh'

        start_time = time.monotonic()
        container = None

        try:
            # 创建容器
            container = self._docker.containers.create(
                image=image,
                command=['bash', '-c', exec_cmd],
                mem_limit=mem_limit,
                nano_cpus=int(cpu_limit * 1e9),
                network_disabled=network_disabled,
                environment=env or {},
                detach=True,
                # 设置临时文件系统
                tmpfs={'/workspace': 'size=100m'},
            )

            # 写入文件到容器
            for fname, content in container_files.items():
                container.put_archive(
                    '/workspace',
                    self._make_tar_bytes(fname, content),
                )

            # 启动容器并等待完成
            container.start()

            try:
                result = container.wait(timeout=timeout)
            except Exception:
                # 超时
                container.stop(timeout=2)
                container.remove(force=True)
                elapsed = time.monotonic() - start_time
                return SandboxResult(
                    exit_code=-1,
                    stdout='',
                    stderr=f'Container timed out after {timeout}s',
                    timed_out=True,
                    execution_time=round(elapsed, 3),
                )

            # 获取输出
            stdout = container.logs(stdout=True, stderr=False).decode(
                'utf-8', errors='replace'
            )
            stderr = container.logs(stdout=False, stderr=True).decode(
                'utf-8', errors='replace'
            )

            elapsed = time.monotonic() - start_time
            exit_code = result.get('StatusCode', -1)

            return SandboxResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time=round(elapsed, 3),
            )

        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error('Docker sandbox error: %s', e)
            return SandboxResult(
                exit_code=-1,
                stdout='',
                stderr=str(e),
                execution_time=round(elapsed, 3),
            )
        finally:
            # 确保容器被清理
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception as e:
                    logger.warning('Failed to remove container: %s', e)

    @staticmethod
    def _make_tar_bytes(filename: str, content: str) -> bytes:
        """创建一个简单的 tar 归档（仅含单个文件）。

        Args:
            filename: 文件名。
            content: 文件内容。

        Returns:
            tar 归档的字节数据。
        """
        import io
        import tarfile

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as tar:
            data = content.encode('utf-8')
            info = tarfile.TarInfo(name=filename)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        buf.seek(0)
        return buf.read()
