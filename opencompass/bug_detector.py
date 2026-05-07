"""Bug 智能检测模块。

自动分析代码执行失败输出，分类错误类型，给出修复建议。
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ErrorSeverity(Enum):
    """错误严重级别。"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class ErrorCategory(Enum):
    """错误类别。"""
    SYNTAX_ERROR = 'syntax_error'
    TYPE_ERROR = 'type_error'
    INDEX_ERROR = 'index_error'
    KEY_ERROR = 'key_error'
    NAME_ERROR = 'name_error'
    VALUE_ERROR = 'value_error'
    IMPORT_ERROR = 'import_error'
    RUNTIME_ERROR = 'runtime_error'
    TIMEOUT = 'timeout'
    MEMORY_ERROR = 'memory_error'
    ATTR_ERROR = 'attribute_error'
    ZERO_DIVISION = 'zero_division'
    RECURSION_ERROR = 'recursion_error'
    FILE_ERROR = 'file_error'
    UNKNOWN = 'unknown'


# 错误模式 → (类别, 严重级别, 修复建议)
ERROR_PATTERNS: Dict[str, tuple] = {
    # 语法错误
    r'SyntaxError[:\s]+\w+': (ErrorCategory.SYNTAX_ERROR, ErrorSeverity.HIGH, 'Check Python syntax. Common causes: missing colon, unmatched parentheses, invalid indentation.'),
    r'IndentationError': (ErrorCategory.SYNTAX_ERROR, ErrorSeverity.MEDIUM, 'Fix indentation. Python uses 4 spaces per level.'),
    r'TabError': (ErrorCategory.SYNTAX_ERROR, ErrorSeverity.MEDIUM, 'Do not mix tabs and spaces. Use consistent indentation.'),

    # 类型错误
    r'TypeError[:\s]+(.+)': (ErrorCategory.TYPE_ERROR, ErrorSeverity.HIGH, None),  # 动态生成建议
    r"'NoneType' object is (not|has no)": (ErrorCategory.TYPE_ERROR, ErrorSeverity.HIGH, 'Check for None values before accessing attributes or calling methods. Add: `if x is not None:`'),
    r"unsupported operand type\(s\) for (.+)": (ErrorCategory.TYPE_ERROR, ErrorSeverity.HIGH, 'Check operand types before operation. Use type conversion: int(), str(), float().'),
    r"'(.+?)' object is not (callable|subscriptable|iterable)": (ErrorCategory.TYPE_ERROR, ErrorSeverity.MEDIUM, None),
    r'missing .+ required positional argument': (ErrorCategory.TYPE_ERROR, ErrorSeverity.MEDIUM, 'Check function signature. Ensure all required arguments are passed.'),

    # 索引错误
    r'IndexError[:\s]+(.+)': (ErrorCategory.INDEX_ERROR, ErrorSeverity.HIGH, None),
    r'list index out of range': (ErrorCategory.INDEX_ERROR, ErrorSeverity.HIGH, 'Add boundary check: `if 0 <= index < len(arr):`'),
    r'string index out of range': (ErrorCategory.INDEX_ERROR, ErrorSeverity.MEDIUM, 'Check string length before accessing index.'),

    # 键错误
    r'KeyError[:\s]+(.+)': (ErrorCategory.KEY_ERROR, ErrorSeverity.MEDIUM, None),
    r"KeyError:\s*'(.+)'": (ErrorCategory.KEY_ERROR, ErrorSeverity.MEDIUM, 'Use dict.get(key, default) or check `if key in dict:` before access.'),

    # 名称错误
    r'NameError[:\s]+name (.+) is not defined': (ErrorCategory.NAME_ERROR, ErrorSeverity.HIGH, None),
    r"name '(.+)' is not defined": (ErrorCategory.NAME_ERROR, ErrorSeverity.HIGH, 'Check variable/function name spelling. Ensure it is defined before use.'),

    # 值错误
    r'ValueError[:\s]+(.+)': (ErrorCategory.VALUE_ERROR, ErrorSeverity.MEDIUM, None),
    r'invalid literal for int\(\)': (ErrorCategory.VALUE_ERROR, ErrorSeverity.LOW, 'Use try/except when parsing user input, or validate format first.'),

    # 导入错误
    r'ModuleNotFoundError[:\s]+No module named': (ErrorCategory.IMPORT_ERROR, ErrorSeverity.MEDIUM, None),
    r"ImportError[:\s]+cannot import name": (ErrorCategory.IMPORT_ERROR, ErrorSeverity.MEDIUM, None),
    r'No module named': (ErrorCategory.IMPORT_ERROR, ErrorSeverity.MEDIUM, 'Install the required module or check spelling.'),

    # 属性错误
    r'AttributeError[:\s]+(.+)': (ErrorCategory.ATTR_ERROR, ErrorSeverity.MEDIUM, None),
    r"'(.+?)' object has no attribute '(.+?)'": (ErrorCategory.ATTR_ERROR, ErrorSeverity.MEDIUM, 'Check attribute name spelling and object type.'),

    # 运行时错误
    r'RuntimeError[:\s]+(.+)': (ErrorCategory.RUNTIME_ERROR, ErrorSeverity.MEDIUM, None),
    r'maximum recursion depth exceeded': (ErrorCategory.RECURSION_ERROR, ErrorSeverity.HIGH, 'Add base case to recursive function or increase recursion limit.'),

    # 除零
    r'ZeroDivisionError[:\s]+(.+)': (ErrorCategory.ZERO_DIVISION, ErrorSeverity.MEDIUM, 'Add check: `if divisor != 0:` before division.'),

    # 文件错误
    r'FileNotFoundError[:\s]+(.+)': (ErrorCategory.FILE_ERROR, ErrorSeverity.LOW, 'Check file path. Use os.path.exists() before opening.'),
    r'PermissionError[:\s]+(.+)': (ErrorCategory.FILE_ERROR, ErrorSeverity.LOW, 'Check file permissions.'),

    # 超时
    r'TimeoutError|timed out|TIMEOUT': (ErrorCategory.TIMEOUT, ErrorSeverity.HIGH, 'Optimize code performance or increase timeout limit.'),

    # 内存
    r'MemoryError|MemoryLimitExceeded|memory_exceeded': (ErrorCategory.MEMORY_ERROR, ErrorSeverity.HIGH, 'Reduce memory usage. Consider streaming or chunked processing.'),
}


@dataclass
class BugReport:
    """单个 Bug 报告。"""
    test_index: int
    error_type: str
    severity: str
    description: str
    suggested_fix: str
    confidence: float
    raw_error: str = ''
    stderr: str = ''


@dataclass
class BugAnalysis:
    """Bug 分析总结。"""
    task_id: str
    bugs: List[BugReport]
    summary: Dict = field(default_factory=dict)


class BugDetector:
    """Bug 智能检测器。

    分析代码执行的错误输出，分类错误类型，给出修复建议。
    """

    def analyze(
        self,
        task_id: str,
        test_results: List[Dict],
    ) -> BugAnalysis:
        """分析测试结果，检测 Bug。

        Args:
            task_id: 任务 ID。
            test_results: 测试结果列表，每个元素为 dict：
                {
                    'test_index': int,
                    'passed': bool,
                    'exit_code': int,
                    'stdout': str,
                    'stderr': str,
                    'timed_out': bool,
                }

        Returns:
            BugAnalysis 分析结果。
        """
        bugs = []

        for result in test_results:
            if result.get('passed', False):
                continue

            bug = self._analyze_single(result)
            if bug:
                bugs.append(bug)

        summary = self._build_summary(bugs)
        return BugAnalysis(task_id=task_id, bugs=bugs, summary=summary)

    def _analyze_single(self, result: Dict) -> Optional[BugReport]:
        """分析单个失败的测试。"""
        stderr = result.get('stderr', '')
        stdout = result.get('stdout', '')
        exit_code = result.get('exit_code', -1)
        timed_out = result.get('timed_out', False)
        test_index = result.get('test_index', -1)

        # 合并 stderr 和 stdout 以便分析
        error_text = f'{stderr}\n{stdout}'

        if timed_out:
            return BugReport(
                test_index=test_index,
                error_type='timeout',
                severity=ErrorSeverity.HIGH.value,
                description='Code execution timed out. Possible infinite loop or inefficient algorithm.',
                suggested_fix='Add loop termination conditions. Consider time complexity optimization.',
                confidence=0.9,
                raw_error='TIMEOUT',
                stderr=error_text[:500],
            )

        # 尝试匹配已知错误模式
        best_match = None
        best_confidence = 0.0

        for pattern, (category, severity, fix) in ERROR_PATTERNS.items():
            match = re.search(pattern, error_text, re.IGNORECASE)
            if match:
                confidence = self._estimate_confidence(match, error_text)
                if confidence > best_confidence:
                    best_confidence = confidence
                    description = match.group(0) if not match.groups() else match.group(1)

                    # 如果 fix 是 None，尝试生成动态建议
                    if fix is None:
                        fix = self._generate_fix(category, match)

                    best_match = BugReport(
                        test_index=test_index,
                        error_type=category.value,
                        severity=severity.value,
                        description=self._clean_description(description, error_text),
                        suggested_fix=fix,
                        confidence=confidence,
                        raw_error=error_text[:500],
                        stderr=stderr[:500],
                    )

        # 未匹配已知模式
        if best_match is None:
            best_match = BugReport(
                test_index=test_index,
                error_type='unknown',
                severity=ErrorSeverity.MEDIUM.value,
                description=self._extract_error_line(error_text),
                suggested_fix='Review the error output and check code logic.',
                confidence=0.3,
                raw_error=error_text[:500],
                stderr=stderr[:500],
            )

        return best_match

    def _estimate_confidence(self, match, full_text: str) -> float:
        """估算匹配置信度。"""
        confidence = 0.7
        matched_text = match.group(0)

        # 错误在 stderr 的前几行，置信度更高
        first_line = full_text.strip().split('\n')[0] if full_text.strip() else ''
        if matched_text in first_line:
            confidence += 0.15

        # 更长的匹配通常更精确
        if len(matched_text) > 20:
            confidence += 0.1

        # 包含 Python traceback 通常更可靠
        if 'Traceback' in full_text:
            confidence += 0.05

        return min(confidence, 1.0)

    def _generate_fix(self, category: ErrorCategory, match) -> str:
        """根据错误类别和匹配内容生成修复建议。"""
        group = match.group(1) if match.lastindex else ''

        fixes = {
            ErrorCategory.TYPE_ERROR: f'Check types. The operation expected a different type. Received: "{group.strip()}"',
            ErrorCategory.INDEX_ERROR: f'Index out of bounds: {group.strip()}. Add boundary check before access.',
            ErrorCategory.KEY_ERROR: f'Key not found: "{group.strip()}". Use dict.get(key, default) or check with `in`.',
            ErrorCategory.NAME_ERROR: f'Variable "{group.strip()}" is not defined. Check spelling and scope.',
            ErrorCategory.VALUE_ERROR: f'Invalid value: {group.strip()}. Validate input before use.',
            ErrorCategory.ATTR_ERROR: f'Attribute not found: {group.strip()}. Check object type and attribute name.',
            ErrorCategory.RUNTIME_ERROR: f'Runtime error: {group.strip()}. Review logic and add error handling.',
            ErrorCategory.IMPORT_ERROR: f'Module not found: {group.strip()}. Install with pip or check import path.',
        }

        return fixes.get(category, 'Review the error and fix accordingly.')

    def _clean_description(self, matched_group: str, full_text: str) -> str:
        """清理错误描述，去掉多余的 trace 信息。"""
        desc = matched_group.strip()
        # 截断过长的描述
        if len(desc) > 200:
            desc = desc[:200] + '...'
        return desc

    def _extract_error_line(self, text: str) -> str:
        """从文本中提取关键错误行。"""
        lines = text.strip().split('\n')
        for line in lines:
            if 'Error' in line or 'error' in line:
                return line.strip()[:200]
        if lines:
            return lines[-1].strip()[:200]
        return 'Unknown error'

    def _build_summary(self, bugs: List[BugReport]) -> Dict:
        """构建 Bug 汇总。"""
        if not bugs:
            return {
                'total_bugs': 0,
                'high_severity': 0,
                'medium_severity': 0,
                'low_severity': 0,
                'common_pattern': 'none',
            }

        severity_counts = {'high': 0, 'medium': 0, 'low': 0, 'critical': 0}
        type_counts = {}
        for bug in bugs:
            severity_counts[bug.severity] = severity_counts.get(bug.severity, 0) + 1
            type_counts[bug.error_type] = type_counts.get(bug.error_type, 0) + 1

        # 找到最常见的错误类型
        common_pattern = 'none'
        if type_counts:
            common_pattern = max(type_counts, key=type_counts.get)

        return {
            'total_bugs': len(bugs),
            'high_severity': severity_counts.get('high', 0) + severity_counts.get('critical', 0),
            'medium_severity': severity_counts.get('medium', 0),
            'low_severity': severity_counts.get('low', 0),
            'common_pattern': common_pattern,
            'error_types': type_counts,
        }
