from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SandboxResult:
    """代码执行结果。

    Attributes:
        exit_code: 进程退出码。
        stdout: 标准输出内容。
        stderr: 标准错误内容。
        timed_out: 是否因超时终止。
        memory_exceeded: 是否因内存超限终止。
        execution_time: 执行耗时（秒）。
    """
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    memory_exceeded: bool = False
    execution_time: float = 0.0
    files: dict = field(default_factory=dict)
