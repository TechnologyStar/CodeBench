"""任务状态机 — 支持暂停、继续、重试。

任务生命周期：
  pending → running → completed
                  → failed
                  → paused → resumed → running → ...
                  → paused → cancelled
  failed → retrying → running → ...

每个任务维护一个 checkpoint，记录已完成的进度。
"""
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态。"""
    PENDING = 'pending'
    RUNNING = 'running'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLING = 'cancelling'
    CANCELLED = 'cancelled'
    RETRYING = 'retrying'


@dataclass
class Checkpoint:
    """任务检查点，用于暂停/恢复。"""
    completed_indices: List[int] = field(default_factory=list)
    next_index: int = 0
    passed_count: int = 0
    failed_count: int = 0
    results: List[Dict] = field(default_factory=list)
    generated_code: str = ''
    tokens_used: int = 0
    start_time: float = 0.0
    elapsed_before_pause: float = 0.0


@dataclass
class RetryConfig:
    """重试配置。"""
    max_retries: int = 3
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    retry_on_errors: List[str] = field(default_factory=lambda: [
        'timeout', 'api_error', 'connection_error', 'rate_limit',
    ])

    def get_delay(self, attempt: int) -> float:
        """计算第 N 次重试的延迟（指数退避）。"""
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)


class Task:
    """任务实例。"""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        config: Dict,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.id = task_id
        self.type = task_type
        self.config = config
        self.retry_config = retry_config or RetryConfig()

        self.status = TaskStatus.PENDING
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None

        self.checkpoint = Checkpoint()
        self.result: Optional[Dict] = None
        self.error: Optional[str] = None
        self.retry_count = 0
        self.retry_errors: List[str] = []

        # 暂停控制
        self._pause_event = threading.Event()
        self._pause_event.set()  # 默认不暂停
        self._cancel_flag = False

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_flag

    def pause(self):
        """暂停任务。"""
        if self.status == TaskStatus.RUNNING:
            self.status = TaskStatus.PAUSED
            self._pause_event.clear()
            self.checkpoint.elapsed_before_pause = (
                time.time() - (self.started_at or time.time())
                + self.checkpoint.elapsed_before_pause
            )
            logger.info(f'Task {self.id} paused at index {self.checkpoint.next_index}')

    def resume(self):
        """继续任务。"""
        if self.status == TaskStatus.PAUSED:
            self.status = TaskStatus.RUNNING
            self._pause_event.set()
            logger.info(f'Task {self.id} resumed from index {self.checkpoint.next_index}')

    def cancel(self):
        """取消任务。"""
        self._cancel_flag = True
        if self.status in (TaskStatus.RUNNING, TaskStatus.PAUSED):
            self.status = TaskStatus.CANCELLING
            self._pause_event.set()  # 解除暂停以允许退出

    def wait_if_paused(self, timeout: float = None):
        """如果任务被暂停，等待直到恢复。"""
        self._pause_event.wait(timeout)

    def save_checkpoint(self, index: int, result: Dict):
        """保存执行进度。"""
        self.checkpoint.results.append(result)
        self.checkpoint.completed_indices.append(index)
        self.checkpoint.next_index = index + 1
        if result.get('passed', False):
            self.checkpoint.passed_count += 1
        else:
            self.checkpoint.failed_count += 1

    def get_retry_delay(self) -> float:
        """获取重试延迟。"""
        return self.retry_config.get_delay(self.retry_count)

    def can_retry(self, error_type: str = '') -> bool:
        """检查是否可以重试。"""
        if self.retry_count >= self.retry_config.max_retries:
            return False
        if error_type and error_type not in self.retry_config.retry_on_errors:
            return False
        return True

    def to_dict(self) -> Dict:
        """序列化为字典。"""
        return {
            'id': self.id,
            'type': self.type,
            'status': self.status.value,
            'config': self.config,
            'result': self.result,
            'error': self.error,
            'retry_count': self.retry_count,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'checkpoint': {
                'completed_tests': len(self.checkpoint.completed_indices),
                'next_test_index': self.checkpoint.next_index,
                'passed': self.checkpoint.passed_count,
                'failed': self.checkpoint.failed_count,
                'total_tests': len(self.config.get('task', {}).get('test_cases', [])),
            },
        }


class TaskManager:
    """任务管理器。

    管理任务的生命周期，支持暂停、继续、重试。

    Args:
        max_concurrent: 最大并发任务数。
    """

    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._executor: Optional[threading.Thread] = None

    def create_task(
        self,
        task_type: str,
        config: Dict,
        retry_config: Optional[RetryConfig] = None,
    ) -> Task:
        """创建新任务。"""
        task_id = str(uuid.uuid4())[:8]
        task = Task(task_id=task_id, task_type=task_type, config=config,
                    retry_config=retry_config)
        with self._lock:
            self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务。"""
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """列出任务。"""
        with self._lock:
            tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        return tasks

    def pause_task(self, task_id: str) -> bool:
        """暂停任务。"""
        task = self._tasks.get(task_id)
        if task:
            task.pause()
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        """继续任务。"""
        task = self._tasks.get(task_id)
        if task:
            task.resume()
            return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        """取消任务。"""
        task = self._tasks.get(task_id)
        if task:
            task.cancel()
            return True
        return False

    def retry_task(self, task_id: str, config_override: Optional[Dict] = None) -> Optional[Task]:
        """重试失败的任务。

        创建新任务，继承原任务的检查点和配置。

        Args:
            task_id: 原任务 ID。
            config_override: 配置覆盖（可选）。

        Returns:
            新创建的任务，如果原任务不存在则返回 None。
        """
        original = self._tasks.get(task_id)
        if not original:
            return None

        # 合并配置
        new_config = {**original.config}
        if config_override:
            new_config.update(config_override)

        # 创建新任务
        retry_config = RetryConfig(
            max_retries=(config_override or {}).get('retry_count', original.retry_config.max_retries),
            initial_delay=(config_override or {}).get('retry_delay', original.retry_config.initial_delay),
        )

        new_task = self.create_task(
            task_type=original.type,
            config=new_config,
            retry_config=retry_config,
        )

        # 继承检查点
        new_task.checkpoint = original.checkpoint
        new_task.retry_count = original.retry_count + 1
        new_task.retry_errors = original.retry_errors + (original.error and [original.error] or [])

        return new_task

    def run_with_pause_support(
        self,
        task: Task,
        executor: Callable,
        items: List,
    ) -> Dict:
        """运行任务，支持暂停和继续。

        Args:
            task: 任务实例。
            executor: 执行函数，签名 executor(item, index) -> Dict。
            items: 要处理的项目列表（如测试用例）。

        Returns:
            执行结果摘要。
        """
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        results = task.checkpoint.results
        passed = task.checkpoint.passed_count
        failed = task.checkpoint.failed_count

        try:
            for i in range(task.checkpoint.next_index, len(items)):
                # 检查暂停
                task.wait_if_paused()

                # 检查取消
                if task.is_cancelled:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = time.time()
                    return self._build_result(task, passed, failed)

                # 执行
                try:
                    item_result = executor(items[i], i)
                except Exception as e:
                    item_result = {
                        'test_index': i,
                        'passed': False,
                        'error': str(e),
                    }

                # 保存检查点
                task.save_checkpoint(i, item_result)

                if item_result.get('passed', False):
                    passed += 1
                else:
                    failed += 1

                # 错误重试逻辑
                if not item_result.get('passed', False):
                    error_type = self._classify_error(item_result)
                    if task.can_retry(error_type) and not task.is_cancelled:
                        delay = task.get_retry_delay()
                        logger.info(
                            f'Task {task.id} test {i} failed ({error_type}), '
                            f'retrying in {delay}s (attempt {task.retry_count + 1})'
                        )
                        task.wait_if_paused()  # 重试等待期间也支持暂停
                        if not task.is_cancelled:
                            time.sleep(delay)
                            try:
                                retry_result = executor(items[i], i)
                                if retry_result.get('passed', False):
                                    # 重试成功，覆盖之前的失败记录
                                    task.checkpoint.results[-1] = retry_result
                                    passed += 1
                                    failed -= 1
                            except Exception:
                                pass

            # 全部完成
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()

        except Exception as e:
            if task.is_cancelled:
                task.status = TaskStatus.CANCELLED
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
            task.completed_at = time.time()

        return self._build_result(task, passed, failed)

    def _build_result(self, task: Task, passed: int, failed: int) -> Dict:
        """构建任务结果。"""
        return {
            'task_id': task.id,
            'status': task.status.value,
            'passed': passed,
            'failed': failed,
            'total': passed + failed,
            'success': failed == 0 and task.status == TaskStatus.COMPLETED,
            'elapsed': task.completed_at and (task.completed_at - task.created_at) or 0,
        }

    @staticmethod
    def _classify_error(result: Dict) -> str:
        """分类错误类型。"""
        stderr = result.get('stderr', '')
        error = result.get('error', '')

        if result.get('timed_out'):
            return 'timeout'
        if '429' in error or 'rate_limit' in error.lower():
            return 'rate_limit'
        if 'connection' in error.lower() or 'timeout' in error.lower():
            return 'connection_error'
        if 'api' in error.lower():
            return 'api_error'

        error_lower = (stderr + error).lower()
        if 'timeout' in error_lower:
            return 'timeout'
        if 'memory' in error_lower:
            return 'memory_error'

        return 'runtime_error'


# 模块级单例
task_manager = TaskManager()
