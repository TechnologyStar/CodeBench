"""
OpenCompass API Server

轻量级 API 服务，替代 CLI，提供 HTTP 接口进行模型评估。
使用 Python 标准库实现，无额外依赖。

启动方式：
    python -m opencompass.server [--host 0.0.0.0] [--port 8000] [--enable-ui]

端点：
    POST /api/v1/evaluate       - 提交评估任务
    GET  /api/v1/tasks/{id}     - 查询任务状态
    GET  /api/v1/models         - 列出可用模型
    POST /api/v1/agent/evaluate - 提交编码智能体评估
    POST /api/v1/sandbox/execute - 直接执行代码（调试用）
"""

import argparse
import json
import logging
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

# 内存中的任务存储
_tasks: Dict[str, Dict[str, Any]] = {}
_tasks_lock = threading.Lock()

# 已注册的模型列表
_registered_models: Dict[str, Dict[str, Any]] = {}
_models_lock = threading.Lock()


def register_model(name: str, model_type: str, config: Optional[Dict] = None):
    """注册一个模型。

    Args:
        name: 模型名称。
        model_type: 模型类型。
        config: 模型配置。
    """
    with _models_lock:
        _registered_models[name] = {
            'name': name,
            'type': model_type,
            'config': config or {},
        }


def _json_response(handler, status: int, data: Any):
    """发送 JSON 响应。

    Args:
        handler: HTTP 请求处理器。
        status: HTTP 状态码。
        data: 响应数据（可序列化为 JSON）。
    """
    body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler) -> bytes:
    """读取请求体。

    Args:
        handler: HTTP 请求处理器。

    Returns:
        请求体字节数据。
    """
    content_length = int(handler.headers.get('Content-Length', 0))
    if content_length > 0:
        return handler.rfile.read(content_length)
    return b''


class APIHandler(BaseHTTPRequestHandler):
    """OpenCompass API 请求处理器。"""

    # 禁用默认日志输出（用自己的 logging）
    def log_message(self, format, *args):
        logger.debug(format, *args)

    def do_GET(self):
        """处理 GET 请求。"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        # Web UI（需 --enable-ui）
        if path == '' or path == '/':
            if self.server.enable_ui:
                self._handle_ui_index()
                return
            _json_response(self, 200, {
                'service': 'OpenCompass API',
                'version': '2.0.0-dev',
                'ui': 'disabled (use --enable-ui)',
            })
        elif path == '/api/v1/models':
            self._handle_list_models()
        elif path.startswith('/api/v1/tasks/'):
            parts = path.split('/')
            task_id = parts[-1]
            if task_id in ('pause', 'resume', 'retry', 'bugs'):
                # GET /api/v1/tasks/{id}/bugs or GET /api/v1/tasks/{id}/retry
                tid = parts[-2]
                if task_id == 'bugs':
                    self._handle_bug_report(tid)
                elif task_id == 'retry':
                    self._handle_retry_task(tid)
                else:
                    _json_response(self, 405, {'error': 'Use POST for pause/resume'})
            else:
                self._handle_get_task(task_id)
        elif path == '/api/v1/health':
            _json_response(self, 200, {'status': 'ok'})
        else:
            _json_response(self, 404, {'error': 'Not found'})

    def do_POST(self):
        """处理 POST 请求。"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path == '/api/v1/evaluate':
            self._handle_evaluate()
        elif path == '/api/v1/agent/evaluate':
            self._handle_agent_evaluate()
        elif path == '/api/v1/sandbox/execute':
            self._handle_sandbox_execute()
        elif path.startswith('/api/v1/tasks/'):
            parts = path.split('/')
            task_id = parts[-2]
            action = parts[-1]
            if action == 'pause':
                self._handle_pause_task(task_id)
            elif action == 'resume':
                self._handle_resume_task(task_id)
            elif action == 'retry':
                self._handle_retry_task(task_id)
            else:
                _json_response(self, 404, {'error': 'Not found'})
        else:
            _json_response(self, 404, {'error': 'Not found'})

    def _handle_list_models(self):
        """列出已注册的模型。"""
        with _models_lock:
            models = list(_registered_models.values())
        _json_response(self, 200, {'models': models})

    def _handle_get_task(self, task_id: str):
        """查询任务状态。"""
        with _tasks_lock:
            task = _tasks.get(task_id)
        if task is None:
            _json_response(self, 404, {'error': f'Task not found: {task_id}'})
        else:
            _json_response(self, 200, {'task': task})

    def _handle_evaluate(self):
        """提交模型评估任务。"""
        try:
            body = _read_body(self)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _json_response(self, 400, {'error': f'Invalid JSON: {e}'})
            return

        model_name = data.get('model')
        dataset = data.get('dataset')

        if not model_name:
            _json_response(self, 400, {'error': 'Missing required field: model'})
            return
        if not dataset:
            _json_response(self, 400, {'error': 'Missing required field: dataset'})
            return

        task_id = str(uuid.uuid4())[:8]
        task = {
            'task_id': task_id,
            'type': 'model_evaluation',
            'status': 'pending',
            'model': model_name,
            'dataset': dataset,
            'config': data.get('config', {}),
            'result': None,
            'created_at': time.time(),
            'updated_at': time.time(),
        }

        with _tasks_lock:
            _tasks[task_id] = task

        # 在后台线程中执行评估
        thread = threading.Thread(
            target=self._run_model_evaluation,
            args=(task_id, model_name, dataset, data.get('config', {})),
            daemon=True,
        )
        thread.start()

        _json_response(self, 202, {
            'task_id': task_id,
            'status': 'pending',
            'message': 'Evaluation task submitted',
        })

    def _handle_agent_evaluate(self):
        """提交编码智能体评估任务。"""
        try:
            body = _read_body(self)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _json_response(self, 400, {'error': f'Invalid JSON: {e}'})
            return

        description = data.get('description')
        agent_type = data.get('agent', 'claude-code')

        if not description:
            _json_response(self, 400, {'error': 'Missing required field: description'})
            return

        task_id = str(uuid.uuid4())[:8]
        task = {
            'task_id': task_id,
            'type': 'agent_evaluation',
            'status': 'pending',
            'agent': agent_type,
            'config': data,
            'result': None,
            'created_at': time.time(),
            'updated_at': time.time(),
        }

        with _tasks_lock:
            _tasks[task_id] = task

        # 在后台线程中执行评估
        thread = threading.Thread(
            target=self._run_agent_evaluation,
            args=(task_id, agent_type, data),
            daemon=True,
        )
        thread.start()

        _json_response(self, 202, {
            'task_id': task_id,
            'status': 'pending',
            'message': 'Agent evaluation task submitted',
        })

    def _handle_sandbox_execute(self):
        """直接执行代码（调试用）。"""
        try:
            body = _read_body(self)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _json_response(self, 400, {'error': f'Invalid JSON: {e}'})
            return

        code = data.get('code', '')
        language = data.get('language', 'python')
        timeout = data.get('timeout', 30)
        max_memory_mb = data.get('max_memory_mb', 512)

        if not code:
            _json_response(self, 400, {'error': 'Missing required field: code'})
            return

        try:
            from opencompass.sandbox import create_sandbox

            sandbox = create_sandbox(type='subprocess')
            result = sandbox.execute(
                code=code,
                language=language,
                timeout=timeout,
                max_memory_mb=max_memory_mb,
            )

            _json_response(self, 200, {
                'exit_code': result.exit_code,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'timed_out': result.timed_out,
                'memory_exceeded': result.memory_exceeded,
                'execution_time': result.execution_time,
            })
        except Exception as e:
            _json_response(self, 500, {'error': str(e)})

    @staticmethod
    def _run_model_evaluation(task_id: str, model_name: str, dataset: str, config: dict):
        """在后台执行模型评估。

        Args:
            task_id: 任务 ID。
            model_name: 模型名称。
            dataset: 数据集名称。
            config: 评估配置。
        """
        with _tasks_lock:
            _tasks[task_id]['status'] = 'running'
            _tasks[task_id]['updated_at'] = time.time()

        try:
            logger.info(
                'Running model evaluation: task=%s model=%s dataset=%s',
                task_id, model_name, dataset,
            )

            # 占位实现：实际评估需要集成 OpenCompass 的评估流程
            # 这里模拟评估过程
            import time as _time
            _time.sleep(1)  # 模拟评估耗时

            with _tasks_lock:
                _tasks[task_id]['status'] = 'completed'
                _tasks[task_id]['result'] = {
                    'model': model_name,
                    'dataset': dataset,
                    'message': 'Evaluation completed (placeholder)',
                }
                _tasks[task_id]['updated_at'] = time.time()

        except Exception as e:
            logger.error('Model evaluation failed: task=%s error=%s', task_id, e)
            with _tasks_lock:
                _tasks[task_id]['status'] = 'failed'
                _tasks[task_id]['error'] = str(e)
                _tasks[task_id]['updated_at'] = time.time()

    @staticmethod
    def _run_agent_evaluation(task_id: str, agent_type: str, config: dict):
        """在后台执行智能体评估。

        Args:
            task_id: 任务 ID。
            agent_type: 智能体类型。
            config: 评估配置。
        """
        with _tasks_lock:
            _tasks[task_id]['status'] = 'running'
            _tasks[task_id]['updated_at'] = time.time()

        try:
            from opencompass.agents import AgentTask
            from opencompass.agents.claudecode_agent import ClaudeCodeAgent
            from opencompass.agents.codex_agent import CodexAgent

            # 创建任务
            task = AgentTask(
                description=config.get('description', ''),
                language=config.get('language', 'python'),
                context=config.get('context', ''),
                test_cases=config.get('test_cases', []),
                difficulty=config.get('difficulty', 'medium'),
                max_tokens=config.get('max_tokens', 4096),
                timeout=config.get('timeout', 300),
            )

            # 选择智能体
            if agent_type == 'codex':
                agent = CodexAgent(
                    api_key=config.get('api_key', 'ENV'),
                    model=config.get('model', 'o3'),
                    base_url=config.get('base_url'),
                )
            else:
                agent = ClaudeCodeAgent(
                    mode=config.get('mode', 'api'),
                    api_key=config.get('api_key', 'ENV'),
                    model=config.get('model', 'claude-sonnet-4-20250514'),
                    base_url=config.get('base_url'),
                )

            # 执行评估
            result = agent.evaluate(task)

            with _tasks_lock:
                _tasks[task_id]['status'] = 'completed'
                _tasks[task_id]['result'] = {
                    'success': result.success,
                    'total_tests': result.total_tests,
                    'passed_tests': result.passed_tests,
                    'execution_time': result.execution_time,
                    'tokens_used': result.tokens_used,
                    'error': result.error,
                }
                _tasks[task_id]['updated_at'] = time.time()

        except Exception as e:
            logger.error('Agent evaluation failed: task=%s error=%s', task_id, e)
            with _tasks_lock:
                _tasks[task_id]['status'] = 'failed'
                _tasks[task_id]['error'] = str(e)
                _tasks[task_id]['updated_at'] = time.time()


    # ---- 暂停 / 继续 / 重试 / Bug 检测 ----

    def _handle_pause_task(self, task_id: str):
        """暂停任务。"""
        from .task_manager import task_manager
        ok = task_manager.pause_task(task_id)
        if ok:
            task = task_manager.get_task(task_id)
            _json_response(self, 200, {
                'task_id': task_id,
                'status': 'paused',
                'completed_tests': len(task.checkpoint.completed_indices),
                'remaining_tests': (
                    len(task.config.get('task', {}).get('test_cases', []))
                    - len(task.checkpoint.completed_indices)
                ),
            })
        else:
            _json_response(self, 404, {'error': f'Task {task_id} not found'})

    def _handle_resume_task(self, task_id: str):
        """继续任务。"""
        from .task_manager import task_manager
        ok = task_manager.resume_task(task_id)
        if ok:
            task = task_manager.get_task(task_id)
            _json_response(self, 200, {
                'task_id': task_id,
                'status': 'running',
                'resumed_from_test': task.checkpoint.next_index,
                'remaining_tests': (
                    len(task.config.get('task', {}).get('test_cases', []))
                    - task.checkpoint.next_index
                ),
            })
        else:
            _json_response(self, 404, {'error': f'Task {task_id} not found'})

    def _handle_retry_task(self, task_id: str):
        """重试失败任务。"""
        from .task_manager import task_manager
        body = self._read_json_body() or {}
        new_task = task_manager.retry_task(task_id, config_override=body)
        if new_task:
            _json_response(self, 200, {
                'task_id': new_task.id,
                'status': 'pending',
                'retry_count': new_task.retry_count,
                'message': 'Retry task created',
            })
        else:
            _json_response(self, 404, {'error': f'Task {task_id} not found'})

    def _handle_bug_report(self, task_id: str):
        """获取 Bug 检测报告。"""
        from .task_manager import task_manager
        from .bug_detector import BugDetector

        task = task_manager.get_task(task_id)
        if not task:
            _json_response(self, 404, {'error': f'Task {task_id} not found'})
            return

        detector = BugDetector()
        test_results = task.checkpoint.results
        analysis = detector.analyze(task_id, test_results)

        _json_response(self, 200, {
            'task_id': task_id,
            'bugs': [
                {
                    'test_index': b.test_index,
                    'error_type': b.error_type,
                    'severity': b.severity,
                    'description': b.description,
                    'suggested_fix': b.suggested_fix,
                    'confidence': b.confidence,
                }
                for b in analysis.bugs
            ],
            'summary': analysis.summary,
        })

    # ---- Web UI ----

    def _handle_ui_index(self):
        """返回 Web UI 页面。"""
        import os
        ui_dir = os.path.join(os.path.dirname(__file__), 'ui')
        index_path = os.path.join(ui_dir, 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        else:
            _json_response(self, 503, {'error': 'UI files not found. Run from project root.'})

    def _read_json_body(self):
        """安全读取 JSON body。"""
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length == 0:
                return None
            body = self.rfile.read(length)
            return json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return None


def create_server(host: str = '0.0.0.0', port: int = 8000, enable_ui: bool = False) -> HTTPServer:
    """创建 API 服务器实例。

    Args:
        host: 监听地址。
        port: 监听端口。
        enable_ui: 是否启用 Web UI。

    Returns:
        HTTPServer 实例。
    """
    server = HTTPServer((host, port), APIHandler)
    server.enable_ui = enable_ui
    return server


def run_server(host: str = '0.0.0.0', port: int = 8000, enable_ui: bool = False):
    """启动 API 服务器。

    Args:
        host: 监听地址。
        port: 监听端口。
        enable_ui: 是否启用 Web UI。
    """
    server = create_server(host, port, enable_ui=enable_ui)
    logger.info('OpenCompass API Server starting on %s:%d (ui=%s)', host, port, enable_ui)
    print(f'OpenCompass API Server running on http://{host}:{port}')
    print('Endpoints:')
    print('  POST /api/v1/evaluate        - Submit evaluation task')
    print('  GET  /api/v1/tasks/{{id}}      - Query task status')
    print('  GET  /api/v1/models           - List available models')
    print('  POST /api/v1/agent/evaluate   - Submit agent evaluation')
    print('  POST /api/v1/sandbox/execute  - Execute code (debug)')
    print('  POST /api/v1/tasks/{{id}}/pause  - Pause task')
    print('  POST /api/v1/tasks/{{id}}/resume - Resume task')
    print('  POST /api/v1/tasks/{{id}}/retry  - Retry failed task')
    print('  GET  /api/v1/tasks/{{id}}/bugs   - Bug detection report')
    print('  GET  /api/v1/health           - Health check')
    if enable_ui:
        print(f'  GET  /                        - Web UI')
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('Server shutting down...')
        server.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OpenCompass API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Bind address')
    parser.add_argument('--port', type=int, default=8000, help='Bind port')
    parser.add_argument('--log-level', default='INFO', help='Log level')
    parser.add_argument('--enable-ui', action='store_true', help='Enable Web UI')
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    run_server(host=args.host, port=args.port, enable_ui=args.enable_ui)
