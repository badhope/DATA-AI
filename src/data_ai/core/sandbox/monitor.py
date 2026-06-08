"""
沙箱监控模块。

本模块实现了沙箱的资源监控和违规检测功能，
用于实时跟踪资源使用情况并检测潜在的安全违规。

主要类:
- ResourceMonitor: 资源监控器
- ViolationDetector: 违规检测器
- UsageStats: 使用统计
"""

import ast
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .types import (
    Permission,
    ResourceLimit,
    SandboxViolation,
    ViolationSeverity,
)


@dataclass
class UsageStats:
    """
    资源使用统计。

    记录某一时刻的资源使用情况。

    Attributes:
        timestamp: 记录时间
        cpu_percent: CPU 使用百分比
        memory_mb: 内存使用量 (MB)
        open_files: 打开的文件数
        network_connections: 网络连接数
        threads: 线程数
        execution_time: 执行时间（秒）
    """

    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    open_files: int = 0
    network_connections: int = 0
    threads: int = 1
    execution_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_mb": round(self.memory_mb, 2),
            "open_files": self.open_files,
            "network_connections": self.network_connections,
            "threads": self.threads,
            "execution_time": round(self.execution_time, 3),
        }


@dataclass
class LimitCheckResult:
    """
    限制检查结果。

    Attributes:
        within_limits: 是否在限制范围内
        violations: 违规项列表
        warnings: 警告项列表
        usage: 当前使用统计
    """

    within_limits: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    usage: UsageStats | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "within_limits": self.within_limits,
            "violations": self.violations,
            "warnings": self.warnings,
            "usage": self.usage.to_dict() if self.usage else None,
        }


class ResourceMonitor:
    """
    资源监控器。

    实时监控沙箱的资源使用情况，包括 CPU、内存、文件和网络等。

    Attributes:
        limits: 资源限制
        is_monitoring: 是否正在监控
        stats_history: 历史统计记录

    Example:
        >>> monitor = ResourceMonitor(ResourceLimit.moderate())
        >>> monitor.start_monitoring()
        >>> # ... 执行代码 ...
        >>> usage = monitor.get_usage()
        >>> print(f"CPU: {usage.cpu_percent}%")
        >>> monitor.stop_monitoring()
    """

    def __init__(
        self, limits: ResourceLimit | None = None, sample_interval: float = 0.1, history_size: int = 1000
    ) -> None:
        """
        初始化资源监控器。

        Args:
            limits: 资源限制配置
            sample_interval: 采样间隔（秒）
            history_size: 历史记录大小
        """
        self.limits = limits or ResourceLimit()
        self.sample_interval = sample_interval
        self.history_size = history_size

        self.is_monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._start_time: float | None = None
        self._stats_history: deque = deque(maxlen=history_size)
        self._current_stats = UsageStats()
        self._lock = threading.RLock()

        # 回调函数
        self._on_limit_exceeded: Callable[[str, float, float], None] | None = None
        self._on_warning: Callable[[str, float, float], None] | None = None

    def start_monitoring(self) -> None:
        """
        开始监控。

        启动后台线程定期采样资源使用情况。
        """
        with self._lock:
            if self.is_monitoring:
                return

            self.is_monitoring = True
            self._stop_event.clear()
            self._start_time = time.time()

            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ResourceMonitor")
            self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """
        停止监控。

        停止后台监控线程。
        """
        with self._lock:
            if not self.is_monitoring:
                return

            self.is_monitoring = False
            self._stop_event.set()

            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=2.0)

            self._monitor_thread = None

    def _monitor_loop(self) -> None:
        """监控循环。"""
        while not self._stop_event.is_set():
            try:
                stats = self._collect_stats()

                with self._lock:
                    self._current_stats = stats
                    self._stats_history.append(stats)

                # 检查限制
                self._check_limits(stats)

            except Exception:
                # 记录错误但继续监控
                pass

            self._stop_event.wait(self.sample_interval)

    def _collect_stats(self) -> UsageStats:
        """
        收集当前资源使用统计。

        Returns:
            当前使用统计
        """
        stats = UsageStats()

        # 执行时间
        if self._start_time:
            stats.execution_time = time.time() - self._start_time

        # 尝试使用 psutil 获取详细统计
        try:
            import psutil

            process = psutil.Process()

            stats.cpu_percent = process.cpu_percent()
            stats.memory_mb = process.memory_info().rss / (1024 * 1024)

            # 文件描述符数量
            try:
                stats.open_files = len(process.open_files())
            except (psutil.AccessDenied, NotImplementedError):
                stats.open_files = 0

            # 网络连接数
            try:
                stats.network_connections = len(process.connections())
            except (psutil.AccessDenied, NotImplementedError):
                stats.network_connections = 0

            # 线程数
            try:
                stats.threads = process.num_threads()
            except (psutil.AccessDenied, NotImplementedError):
                stats.threads = 1

        except ImportError:
            # psutil 不可用，使用基本方法
            stats.cpu_percent = self._estimate_cpu()
            stats.memory_mb = self._estimate_memory()

        return stats

    def _estimate_cpu(self) -> float:
        """估算 CPU 使用率（不使用 psutil）。"""
        # 简单估算，实际使用时建议安装 psutil
        try:
            import time

            start = time.process_time()
            time.sleep(0.01)
            end = time.process_time()
            return min(100.0, (end - start) / 0.01 * 100)
        except Exception:
            return 0.0

    def _estimate_memory(self) -> float:
        """估算内存使用（不使用 psutil）。"""
        try:
            import resource

            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except Exception:
            return 0.0

    def _check_limits(self, stats: UsageStats) -> None:
        """
        检查资源限制。

        Args:
            stats: 当前使用统计
        """
        # CPU 检查
        if stats.cpu_percent > self.limits.max_cpu_percent:
            if self._on_limit_exceeded:
                self._on_limit_exceeded("cpu", stats.cpu_percent, self.limits.max_cpu_percent)
        elif stats.cpu_percent > self.limits.max_cpu_percent * 0.8:
            if self._on_warning:
                self._on_warning("cpu", stats.cpu_percent, self.limits.max_cpu_percent)

        # 内存检查
        if stats.memory_mb > self.limits.max_memory_mb:
            if self._on_limit_exceeded:
                self._on_limit_exceeded("memory", stats.memory_mb, self.limits.max_memory_mb)
        elif stats.memory_mb > self.limits.max_memory_mb * 0.8:
            if self._on_warning:
                self._on_warning("memory", stats.memory_mb, self.limits.max_memory_mb)

        # 执行时间检查
        if stats.execution_time > self.limits.max_execution_time_seconds:
            if self._on_limit_exceeded:
                self._on_limit_exceeded("execution_time", stats.execution_time, self.limits.max_execution_time_seconds)

        # 打开文件检查
        if stats.open_files > self.limits.max_open_files:
            if self._on_limit_exceeded:
                self._on_limit_exceeded("open_files", stats.open_files, self.limits.max_open_files)

        # 网络连接检查
        if stats.network_connections > self.limits.max_network_connections:
            if self._on_limit_exceeded:
                self._on_limit_exceeded(
                    "network_connections", stats.network_connections, self.limits.max_network_connections
                )

    def get_usage(self) -> UsageStats:
        """
        获取当前资源使用情况。

        Returns:
            当前使用统计
        """
        with self._lock:
            return UsageStats(
                timestamp=self._current_stats.timestamp,
                cpu_percent=self._current_stats.cpu_percent,
                memory_mb=self._current_stats.memory_mb,
                open_files=self._current_stats.open_files,
                network_connections=self._current_stats.network_connections,
                threads=self._current_stats.threads,
                execution_time=self._current_stats.execution_time,
            )

    def get_history(self, count: int | None = None) -> list[UsageStats]:
        """
        获取历史统计记录。

        Args:
            count: 要获取的记录数量，None 表示全部

        Returns:
            历史统计列表
        """
        with self._lock:
            history = list(self._stats_history)
            if count is not None:
                return history[-count:]
            return history

    def check_limits(self) -> LimitCheckResult:
        """
        检查当前使用是否超出限制。

        Returns:
            限制检查结果
        """
        stats = self.get_usage()
        violations = []
        warnings = []

        # CPU
        if stats.cpu_percent > self.limits.max_cpu_percent:
            violations.append(f"CPU usage {stats.cpu_percent:.1f}% exceeds limit {self.limits.max_cpu_percent}%")
        elif stats.cpu_percent > self.limits.max_cpu_percent * 0.8:
            warnings.append(f"CPU usage {stats.cpu_percent:.1f}% approaching limit")

        # 内存
        if stats.memory_mb > self.limits.max_memory_mb:
            violations.append(f"Memory usage {stats.memory_mb:.1f}MB exceeds limit {self.limits.max_memory_mb}MB")
        elif stats.memory_mb > self.limits.max_memory_mb * 0.8:
            warnings.append(f"Memory usage {stats.memory_mb:.1f}MB approaching limit")

        # 执行时间
        if stats.execution_time > self.limits.max_execution_time_seconds:
            violations.append(
                f"Execution time {stats.execution_time:.1f}s exceeds limit {self.limits.max_execution_time_seconds}s"
            )

        # 打开文件
        if stats.open_files > self.limits.max_open_files:
            violations.append(f"Open files {stats.open_files} exceeds limit {self.limits.max_open_files}")

        # 网络连接
        if stats.network_connections > self.limits.max_network_connections:
            violations.append(
                f"Network connections {stats.network_connections} exceeds limit {self.limits.max_network_connections}"
            )

        return LimitCheckResult(
            within_limits=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            usage=stats,
        )

    def set_limit_callback(self, callback: Callable[[str, float, float], None]) -> None:
        """
        设置超出限制回调。

        Args:
            callback: 回调函数，参数为 (资源类型, 当前值, 限制值)
        """
        self._on_limit_exceeded = callback

    def set_warning_callback(self, callback: Callable[[str, float, float], None]) -> None:
        """
        设置警告回调。

        Args:
            callback: 回调函数，参数为 (资源类型, 当前值, 限制值)
        """
        self._on_warning = callback

    def get_summary(self) -> dict[str, Any]:
        """
        获取监控摘要。

        Returns:
            摘要信息字典
        """
        stats = self.get_usage()
        history = self.get_history()

        # 计算平均值
        if history:
            avg_cpu = sum(s.cpu_percent for s in history) / len(history)
            avg_memory = sum(s.memory_mb for s in history) / len(history)
            max_cpu = max(s.cpu_percent for s in history)
            max_memory = max(s.memory_mb for s in history)
        else:
            avg_cpu = avg_memory = max_cpu = max_memory = 0

        return {
            "current": stats.to_dict(),
            "average": {
                "cpu_percent": round(avg_cpu, 2),
                "memory_mb": round(avg_memory, 2),
            },
            "peak": {
                "cpu_percent": round(max_cpu, 2),
                "memory_mb": round(max_memory, 2),
            },
            "limits": self.limits.to_dict(),
            "is_monitoring": self.is_monitoring,
            "sample_count": len(history),
        }

    def reset(self) -> None:
        """重置监控器状态。"""
        with self._lock:
            self._stats_history.clear()
            self._current_stats = UsageStats()
            self._start_time = time.time() if self.is_monitoring else None

    def __enter__(self) -> "ResourceMonitor":
        """上下文管理器入口。"""
        self.start_monitoring()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出。"""
        self.stop_monitoring()


class ViolationDetector:
    """
    违规检测器。

    检测沙箱中的潜在违规行为，包括权限违规、资源滥用和可疑操作。

    Attributes:
        violations: 检测到的违规列表
        rules: 检测规则

    Example:
        >>> detector = ViolationDetector()
        >>> detector.add_rule("no_os_system", check_os_system)
        >>> violations = detector.detect(code)
    """

    def __init__(self) -> None:
        """初始化违规检测器。"""
        self.violations: list[SandboxViolation] = []
        self._rules: dict[str, Callable[[Any], SandboxViolation | None]] = {}
        self._lock = threading.RLock()

        # 添加默认规则
        self._add_default_rules()

    def _add_default_rules(self) -> None:
        """添加默认检测规则。"""
        # 危险模块导入检测
        self.add_rule("dangerous_import", self._check_dangerous_import)

        # 危险函数调用检测
        self.add_rule("dangerous_call", self._check_dangerous_call)

        # 文件操作检测
        self.add_rule("file_operation", self._check_file_operation)

        # 网络操作检测
        self.add_rule("network_operation", self._check_network_operation)

        # 子进程检测
        self.add_rule("subprocess_creation", self._check_subprocess)

    def add_rule(self, name: str, checker: Callable[[Any], SandboxViolation | None]) -> None:
        """
        添加检测规则。

        Args:
            name: 规则名称
            checker: 检查函数，接受代码或操作，返回违规记录或 None
        """
        with self._lock:
            self._rules[name] = checker

    def remove_rule(self, name: str) -> bool:
        """
        移除检测规则。

        Args:
            name: 规则名称

        Returns:
            如果移除成功返回 True
        """
        with self._lock:
            if name in self._rules:
                del self._rules[name]
                return True
            return False

    def detect(self, code: Any) -> list[SandboxViolation]:
        """
        检测违规。

        Args:
            code: 要检测的代码或操作

        Returns:
            检测到的违规列表
        """
        detected = []

        with self._lock:
            for name, checker in self._rules.items():
                try:
                    violation = checker(code)
                    if violation:
                        detected.append(violation)
                        self.violations.append(violation)
                except Exception:
                    # 规则执行错误，跳过
                    pass

        return detected

    def detect_code(self, code: str) -> list[SandboxViolation]:
        """
        检测代码字符串中的违规。

        Args:
            code: 代码字符串

        Returns:
            检测到的违规列表
        """
        violations = []

        try:
            # 解析代码为 AST
            tree = ast.parse(code)

            # 遍历 AST 检测
            for node in ast.walk(tree):
                violation = self._check_ast_node(node)
                if violation:
                    violations.append(violation)

        except SyntaxError:
            # 语法错误，无法分析
            pass

        # 也运行常规检测
        violations.extend(self.detect(code))

        # 存储违规
        with self._lock:
            self.violations.extend(violations)

        return violations

    def _check_ast_node(self, node: ast.AST) -> SandboxViolation | None:
        """
        检查 AST 节点。

        Args:
            node: AST 节点

        Returns:
            如果检测到违规返回违规记录
        """
        # 检查导入
        if isinstance(node, ast.Import):
            for alias in node.names:
                if self._is_dangerous_module(alias.name):
                    return SandboxViolation(
                        permission=Permission.IMPORT_MODULE,
                        action=f"import {alias.name}",
                        severity=ViolationSeverity.HIGH,
                        message=f"Attempt to import dangerous module: {alias.name}",
                    )

        # 检查 from ... import
        elif isinstance(node, ast.ImportFrom):
            if node.module and self._is_dangerous_module(node.module):
                return SandboxViolation(
                    permission=Permission.IMPORT_MODULE,
                    action=f"from {node.module} import ...",
                    severity=ViolationSeverity.HIGH,
                    message=f"Attempt to import from dangerous module: {node.module}",
                )

        # 检查函数调用
        elif isinstance(node, ast.Call):
            call_name = self._get_call_name(node)
            if call_name:
                violation = self._check_dangerous_function(call_name)
                if violation:
                    return violation

        return None

    def _get_call_name(self, node: ast.Call) -> str | None:
        """获取函数调用的名称。"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return None

    def _is_dangerous_module(self, module: str) -> bool:
        """检查是否为危险模块。"""
        dangerous = {
            "os",
            "sys",
            "subprocess",
            "ctypes",
            "multiprocessing",
            "socket",
            "pickle",
            "marshal",
            "shelve",
            "imp",
            "importlib",
            "code",
            "codeop",
            "commands",
        }
        base_module = module.split(".")[0]
        return base_module in dangerous

    def _check_dangerous_function(self, name: str) -> SandboxViolation | None:
        """检查危险函数调用。"""
        dangerous_calls = {
            "os.system": (Permission.SUBPROCESS, ViolationSeverity.CRITICAL),
            "os.popen": (Permission.SUBPROCESS, ViolationSeverity.HIGH),
            "os.spawn": (Permission.SUBPROCESS, ViolationSeverity.HIGH),
            "os.exec": (Permission.EXECUTE, ViolationSeverity.HIGH),
            "os.fork": (Permission.SUBPROCESS, ViolationSeverity.CRITICAL),
            "subprocess.call": (Permission.SUBPROCESS, ViolationSeverity.HIGH),
            "subprocess.run": (Permission.SUBPROCESS, ViolationSeverity.HIGH),
            "subprocess.Popen": (Permission.SUBPROCESS, ViolationSeverity.HIGH),
            "eval": (Permission.EXECUTE, ViolationSeverity.MEDIUM),
            "exec": (Permission.EXECUTE, ViolationSeverity.MEDIUM),
            "compile": (Permission.EXECUTE, ViolationSeverity.MEDIUM),
            "__import__": (Permission.IMPORT_MODULE, ViolationSeverity.MEDIUM),
            "open": (Permission.FILE_WRITE, ViolationSeverity.LOW),
        }

        if name in dangerous_calls:
            perm, severity = dangerous_calls[name]
            return SandboxViolation(
                permission=perm,
                action=f"call {name}()",
                severity=severity,
                message=f"Potentially dangerous function call: {name}()",
            )

        return None

    def _check_dangerous_import(self, code: Any) -> SandboxViolation | None:
        """检查危险导入。"""
        if isinstance(code, str):
            dangerous_modules = ["os", "subprocess", "ctypes", "socket", "multiprocessing", "pickle", "marshal"]
            for module in dangerous_modules:
                if f"import {module}" in code or f"from {module}" in code:
                    return SandboxViolation(
                        permission=Permission.IMPORT_MODULE,
                        action=f"import {module}",
                        severity=ViolationSeverity.HIGH,
                        message=f"Attempt to import dangerous module: {module}",
                    )
        return None

    def _check_dangerous_call(self, code: Any) -> SandboxViolation | None:
        """检查危险函数调用。"""
        if isinstance(code, str):
            dangerous_patterns = [
                ("os.system", Permission.SUBPROCESS),
                ("subprocess.", Permission.SUBPROCESS),
                ("eval(", Permission.EXECUTE),
                ("exec(", Permission.EXECUTE),
            ]
            for pattern, perm in dangerous_patterns:
                if pattern in code:
                    return SandboxViolation(
                        permission=perm,
                        action=f"call {pattern}",
                        severity=ViolationSeverity.HIGH,
                        message=f"Potentially dangerous operation: {pattern}",
                    )
        return None

    def _check_file_operation(self, code: Any) -> SandboxViolation | None:
        """检查文件操作。"""
        if isinstance(code, str):
            sensitive_paths = ["/etc/passwd", "/etc/shadow", "/root/"]
            for path in sensitive_paths:
                if path in code:
                    return SandboxViolation(
                        permission=Permission.FILE_READ,
                        action=f"access {path}",
                        severity=ViolationSeverity.HIGH,
                        message=f"Attempt to access sensitive path: {path}",
                    )
        return None

    def _check_network_operation(self, code: Any) -> SandboxViolation | None:
        """检查网络操作。"""
        if isinstance(code, str):
            network_patterns = [
                "socket.socket",
                "urllib.request",
                "requests.",
                "http.client",
            ]
            for pattern in network_patterns:
                if pattern in code:
                    return SandboxViolation(
                        permission=Permission.NETWORK,
                        action=f"network operation: {pattern}",
                        severity=ViolationSeverity.MEDIUM,
                        message=f"Network operation detected: {pattern}",
                    )
        return None

    def _check_subprocess(self, code: Any) -> SandboxViolation | None:
        """检查子进程创建。"""
        if isinstance(code, str):
            subprocess_patterns = [
                "subprocess.Popen",
                "subprocess.call",
                "subprocess.run",
                "os.system",
                "os.popen",
            ]
            for pattern in subprocess_patterns:
                if pattern in code:
                    return SandboxViolation(
                        permission=Permission.SUBPROCESS,
                        action=f"create subprocess: {pattern}",
                        severity=ViolationSeverity.HIGH,
                        message=f"Subprocess creation detected: {pattern}",
                    )
        return None

    def get_violations(
        self, severity: ViolationSeverity | None = None, resolved: bool | None = None
    ) -> list[SandboxViolation]:
        """
        获取违规记录。

        Args:
            severity: 过滤特定严重程度
            resolved: 过滤已解决/未解决

        Returns:
            违规记录列表
        """
        with self._lock:
            violations = list(self.violations)

        if severity is not None:
            violations = [v for v in violations if v.severity == severity]

        if resolved is not None:
            violations = [v for v in violations if v.resolved == resolved]

        return violations

    def clear_violations(self) -> int:
        """
        清除所有违规记录。

        Returns:
            清除的记录数量
        """
        with self._lock:
            count = len(self.violations)
            self.violations.clear()
            return count

    def get_statistics(self) -> dict[str, Any]:
        """
        获取违规统计。

        Returns:
            统计信息字典
        """
        with self._lock:
            violations = list(self.violations)

        by_severity = {}
        for severity in ViolationSeverity:
            by_severity[severity.value] = len([v for v in violations if v.severity == severity])

        by_permission = {}
        for v in violations:
            perm_name = v.permission.name
            by_permission[perm_name] = by_permission.get(perm_name, 0) + 1

        return {
            "total": len(violations),
            "by_severity": by_severity,
            "by_permission": by_permission,
            "resolved": len([v for v in violations if v.resolved]),
            "unresolved": len([v for v in violations if not v.resolved]),
        }


class MonitoringContext:
    """
    监控上下文管理器。

    提供便捷的资源监控上下文。

    Example:
        >>> with MonitoringContext(limits) as ctx:
        ...     # 执行代码
        ...     pass
        >>> print(ctx.get_usage())
    """

    def __init__(
        self, limits: ResourceLimit | None = None, on_limit_exceeded: Callable[[str, float, float], None] | None = None
    ) -> None:
        """
        初始化监控上下文。

        Args:
            limits: 资源限制
            on_limit_exceeded: 超出限制回调
        """
        self.monitor = ResourceMonitor(limits)
        self.detector = ViolationDetector()

        if on_limit_exceeded:
            self.monitor.set_limit_callback(on_limit_exceeded)

    def __enter__(self) -> "MonitoringContext":
        """进入上下文。"""
        self.monitor.start_monitoring()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文。"""
        self.monitor.stop_monitoring()

    def get_usage(self) -> UsageStats:
        """获取当前使用情况。"""
        return self.monitor.get_usage()

    def check_limits(self) -> LimitCheckResult:
        """检查限制。"""
        return self.monitor.check_limits()

    def detect_violations(self, code: Any) -> list[SandboxViolation]:
        """检测违规。"""
        return self.detector.detect(code)

    def get_summary(self) -> dict[str, Any]:
        """获取摘要。"""
        return {
            "resource": self.monitor.get_summary(),
            "violations": self.detector.get_statistics(),
        }
