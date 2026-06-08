"""
安全沙箱核心模块。

本模块实现了安全沙箱的核心功能，用于在隔离环境中安全执行代码，
并提供权限管理、违规检测和资源监控等功能。

主要类:
- Sandbox: 安全沙箱，提供代码执行和权限管理
- SandboxException: 沙箱异常
"""

import contextlib
import importlib
import io
import os
import signal
import threading
import time
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from typing import Any

from .types import (
    ExecutionResult,
    Permission,
    PermissionEntry,
    PermissionState,
    ResourceLimit,
    SandboxConfig,
    SandboxPolicy,
    SandboxStatus,
    SandboxViolation,
    ViolationSeverity,
)


class SandboxException(Exception):
    """
    沙箱异常类。

    用于表示沙箱操作过程中发生的各种错误。

    Attributes:
        message: 错误消息
        code: 错误代码
        details: 详细错误信息
    """

    def __init__(self, message: str, code: str = "SANDBOX_ERROR", details: dict[str, Any] | None = None) -> None:
        """
        初始化沙箱异常。

        Args:
            message: 错误消息
            code: 错误代码
            details: 详细错误信息
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """将异常转换为字典格式。"""
        return {
            "message": self.message,
            "code": self.code,
            "details": self.details,
        }


class Sandbox:
    """
    安全沙箱类。

    提供安全的代码执行环境，支持权限管理、资源限制和违规检测。

    Attributes:
        config: 沙箱配置
        status: 沙箱状态
        violations: 违规记录列表
        permissions: 权限条目字典
        _start_time: 启动时间
        _execution_count: 执行计数

    Example:
        >>> config = SandboxConfig(
        ...     name="my_sandbox",
        ...     policy=SandboxPolicy(
        ...         name="safe_policy",
        ...         permissions={Permission.FILE_READ}
        ...     )
        ... )
        >>> sandbox = Sandbox(config)
        >>> sandbox.start()
        >>> result = sandbox.execute("x = 1 + 1; print(x)")
        >>> print(result.output)  # "2"
        >>> sandbox.stop()
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """
        初始化沙箱。

        Args:
            config: 沙箱配置，如果为 None 则使用默认配置
        """
        self.config = config or SandboxConfig()
        self.status = SandboxStatus.CREATED
        self.violations: list[SandboxViolation] = []
        self.permissions: dict[Permission, PermissionEntry] = {}
        self._start_time: datetime | None = None
        self._execution_count: int = 0
        self._lock = threading.RLock()
        self._local_storage: dict[str, Any] = {}

        # 从策略初始化权限
        self._init_permissions_from_policy()

    def _init_permissions_from_policy(self) -> None:
        """从策略初始化权限状态。"""
        policy = self.config.policy

        # 授予策略中的权限
        for permission in policy.permissions:
            self.permissions[permission] = PermissionEntry(
                permission=permission,
                state=PermissionState.GRANTED,
                granted_at=datetime.now(),
                granted_by="policy",
            )

        # 拒绝策略中明确拒绝的权限
        for permission in policy.denied_permissions:
            self.permissions[permission] = PermissionEntry(
                permission=permission,
                state=PermissionState.DENIED,
                granted_by="policy",
            )

    @property
    def sandbox_id(self) -> str:
        """获取沙箱 ID。"""
        return self.config.sandbox_id

    @property
    def name(self) -> str:
        """获取沙箱名称。"""
        return self.config.name

    @property
    def policy(self) -> SandboxPolicy:
        """获取当前策略。"""
        return self.config.policy

    @property
    def is_running(self) -> bool:
        """检查沙箱是否正在运行。"""
        return self.status == SandboxStatus.RUNNING

    def start(self) -> None:
        """
        启动沙箱。

        Raises:
            SandboxException: 如果沙箱已经在运行或处于终止状态
        """
        with self._lock:
            if self.status == SandboxStatus.RUNNING:
                raise SandboxException("Sandbox is already running", code="SANDBOX_ALREADY_RUNNING")

            if self.status.is_terminal():
                raise SandboxException("Cannot restart a terminated sandbox", code="SANDBOX_TERMINATED")

            self.status = SandboxStatus.INITIALIZING

            try:
                # 初始化沙箱环境
                self._setup_environment()
                self.status = SandboxStatus.RUNNING
                self._start_time = datetime.now()
            except Exception as e:
                self.status = SandboxStatus.ERROR
                raise SandboxException(
                    f"Failed to initialize sandbox: {e}", code="SANDBOX_INIT_FAILED", details={"error": str(e)}
                )

    def stop(self, reason: str | None = None) -> None:
        """
        停止沙箱。

        Args:
            reason: 停止原因（可选）
        """
        with self._lock:
            if self.status.is_terminal():
                return

            self.status = SandboxStatus.STOPPING

            try:
                # 清理资源
                self._cleanup()
                self.status = SandboxStatus.STOPPED
            except Exception as e:
                self.status = SandboxStatus.ERROR
                raise SandboxException(f"Error stopping sandbox: {e}", code="SANDBOX_STOP_FAILED")

    def terminate(self, reason: str = "Manual termination") -> None:
        """
        终止沙箱。

        Args:
            reason: 终止原因
        """
        with self._lock:
            if self.status.is_terminal():
                return

            self.status = SandboxStatus.STOPPING

            try:
                self._cleanup()

                # 记录终止原因
                self._local_storage["termination_reason"] = reason
                self.status = SandboxStatus.TERMINATED
            except Exception:
                self.status = SandboxStatus.ERROR

    def pause(self) -> None:
        """暂停沙箱。"""
        with self._lock:
            if self.status == SandboxStatus.RUNNING:
                self.status = SandboxStatus.PAUSED

    def resume(self) -> None:
        """恢复沙箱。"""
        with self._lock:
            if self.status == SandboxStatus.PAUSED:
                self.status = SandboxStatus.RUNNING

    def _setup_environment(self) -> None:
        """设置沙箱环境。"""
        # 设置工作目录
        if self.config.working_directory:
            os.makedirs(self.config.working_directory, exist_ok=True)

        # 初始化本地存储
        self._local_storage = {
            "globals": {},
            "locals": {},
            "imported_modules": set(),
        }

    def _cleanup(self) -> None:
        """清理沙箱资源。"""
        self._local_storage.clear()

    def grant_permission(
        self,
        permission: Permission,
        granted_by: str | None = None,
        expires_at: datetime | None = None,
        conditions: dict[str, Any] | None = None,
    ) -> bool:
        """
        授权权限。

        Args:
            permission: 要授予的权限
            granted_by: 授权来源
            expires_at: 过期时间
            conditions: 授权条件

        Returns:
            如果授权成功返回 True
        """
        with self._lock:
            # 检查是否在拒绝列表中
            if permission in self.config.policy.denied_permissions:
                return False

            self.permissions[permission] = PermissionEntry(
                permission=permission,
                state=PermissionState.GRANTED,
                granted_at=datetime.now(),
                granted_by=granted_by or "manual",
                expires_at=expires_at,
                conditions=conditions or {},
            )
            return True

    def revoke_permission(self, permission: Permission) -> bool:
        """
        撤销权限。

        Args:
            permission: 要撤销的权限

        Returns:
            如果撤销成功返回 True
        """
        with self._lock:
            if permission in self.permissions:
                self.permissions[permission].state = PermissionState.REVOKED
                return True
            return False

    def check_permission(self, permission: Permission) -> bool:
        """
        检查是否拥有指定权限。

        Args:
            permission: 要检查的权限

        Returns:
            如果拥有权限返回 True
        """
        # 检查是否在策略拒绝列表中
        if permission in self.config.policy.denied_permissions:
            return False

        # 检查权限条目
        if permission in self.permissions:
            return self.permissions[permission].is_valid()

        # 检查策略权限
        return self.config.policy.has_permission(permission)

    def get_permissions(self) -> dict[Permission, PermissionEntry]:
        """
        获取所有权限状态。

        Returns:
            权限条目字典
        """
        return dict(self.permissions)

    def record_violation(
        self,
        permission: Permission,
        action: str,
        severity: ViolationSeverity,
        message: str,
        context: dict[str, Any] | None = None,
        stack_trace: str | None = None,
    ) -> SandboxViolation:
        """
        记录违规行为。

        Args:
            permission: 相关权限
            action: 尝试执行的动作
            severity: 违规严重程度
            message: 违规消息
            context: 违规上下文
            stack_trace: 堆栈跟踪

        Returns:
            创建的违规记录
        """
        violation = SandboxViolation(
            permission=permission,
            action=action,
            severity=severity,
            message=message,
            context=context or {},
            stack_trace=stack_trace,
        )

        with self._lock:
            self.violations.append(violation)

            # 检查是否需要终止
            if self.config.auto_terminate_on_violation and severity.should_terminate():
                self.terminate(f"Violation: {message}")
            elif len(self.violations) >= self.config.max_violations:
                self.terminate(f"Maximum violations ({self.config.max_violations}) exceeded")

        return violation

    def get_violations(
        self, resolved: bool | None = None, severity: ViolationSeverity | None = None
    ) -> list[SandboxViolation]:
        """
        获取违规记录。

        Args:
            resolved: 过滤已解决/未解决的违规
            severity: 过滤特定严重程度的违规

        Returns:
            违规记录列表
        """
        violations = self.violations

        if resolved is not None:
            violations = [v for v in violations if v.resolved == resolved]

        if severity is not None:
            violations = [v for v in violations if v.severity == severity]

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

    def execute(
        self,
        code: str | Callable,
        timeout: float | None = None,
        capture_output: bool = True,
        globals_dict: dict[str, Any] | None = None,
        locals_dict: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        在沙箱中执行代码。

        Args:
            code: 要执行的代码（字符串或可调用对象）
            timeout: 执行超时时间（秒）
            capture_output: 是否捕获输出
            globals_dict: 全局命名空间
            locals_dict: 局部命名空间

        Returns:
            执行结果

        Raises:
            SandboxException: 如果沙箱未运行或执行失败
        """
        with self._lock:
            if not self.status.can_execute():
                raise SandboxException(
                    f"Cannot execute code: sandbox status is {self.status.value}", code="SANDBOX_NOT_RUNNING"
                )

            self._execution_count += 1

        # 使用配置的超时或参数指定的超时
        timeout = timeout or self.config.timeout

        # 准备执行环境
        exec_globals = globals_dict or self._create_safe_globals()
        exec_locals = locals_dict or {}

        # 执行结果
        result = ExecutionResult(success=False)
        start_time = time.time()

        # 输出捕获
        stdout_capture = io.StringIO() if capture_output else None
        stderr_capture = io.StringIO() if capture_output else None

        # 超时处理
        def timeout_handler(signum, frame):
            raise TimeoutError("Execution timed out")

        # 设置超时（仅在 Unix 系统上）
        old_handler = None
        if timeout and hasattr(signal, "SIGALRM"):
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, timeout)

        try:
            # 捕获输出 — 嵌套 redirect_stdout / redirect_stderr
            with contextlib.ExitStack() as _stack:
                if capture_output:
                    if stdout_capture:
                        _stack.enter_context(redirect_stdout(stdout_capture))
                    if stderr_capture:
                        _stack.enter_context(redirect_stderr(stderr_capture))

                if isinstance(code, str):
                    # 编译并执行字符串代码
                    compiled = compile(code, "<sandbox>", "exec")
                    exec(compiled, exec_globals, exec_locals)
                    result.return_value = exec_locals.get("__return__", None)
                elif callable(code):
                    # 执行可调用对象
                    result.return_value = code()
                else:
                    raise SandboxException("Code must be a string or callable", code="INVALID_CODE_TYPE")

            result.success = True

        except TimeoutError as e:
            result.error = str(e)
            self.record_violation(
                permission=Permission.EXECUTE,
                action="execute_code",
                severity=ViolationSeverity.HIGH,
                message=f"Execution timed out after {timeout} seconds",
            )
        except PermissionError as e:
            result.error = str(e)
            self.record_violation(
                permission=Permission.FILE_READ,
                action="file_access",
                severity=ViolationSeverity.MEDIUM,
                message=f"Permission denied: {e}",
            )
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            result.success = False
        finally:
            # 取消超时
            if old_handler is not None:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old_handler)

            # 记录执行时间
            result.execution_time = time.time() - start_time

            # 获取输出
            if capture_output:
                if stdout_capture:
                    result.output = stdout_capture.getvalue()
                if stderr_capture:
                    result.error = stderr_capture.getvalue() or result.error

            # 添加执行期间的违规
            result.violations = [v for v in self.violations if v.timestamp >= datetime.fromtimestamp(start_time)]

        return result

    def _create_safe_globals(self) -> dict[str, Any]:
        """
        创建安全的全局命名空间。

        Returns:
            安全的全局命名空间字典
        """
        # 基础内置函数
        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "chr": chr,
            "dict": dict,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "frozenset": frozenset,
            "hex": hex,
            "int": int,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "iter": iter,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "next": next,
            "oct": oct,
            "ord": ord,
            "pow": pow,
            "print": print,
            "range": range,
            "repr": repr,
            "reversed": reversed,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "type": type,
            "zip": zip,
            "True": True,
            "False": False,
            "None": None,
        }

        # 根据权限添加更多内置函数
        if self.check_permission(Permission.IMPORT_MODULE):
            safe_builtins["__import__"] = self._safe_import

        if self.check_permission(Permission.EXECUTE):
            safe_builtins["exec"] = exec
            safe_builtins["eval"] = eval
            safe_builtins["compile"] = compile

        if self.check_permission(Permission.ENVIRONMENT):
            safe_builtins["globals"] = globals
            safe_builtins["locals"] = locals

        return {
            "__builtins__": safe_builtins,
            "__name__": "__sandbox__",
            "__doc__": None,
        }

    def _safe_import(self, name: str, *args, **kwargs) -> Any:
        """
        安全导入模块。

        Args:
            name: 模块名

        Returns:
            导入的模块

        Raises:
            ImportError: 如果模块被禁止导入
        """
        # 检查模块是否被允许
        if not self.config.policy.is_module_allowed(name):
            self.record_violation(
                permission=Permission.IMPORT_MODULE,
                action=f"import('{name}')",
                severity=ViolationSeverity.HIGH,
                message=f"Import of module '{name}' is not allowed",
            )
            raise ImportError(f"Import of module '{name}' is not allowed by sandbox policy")

        # 记录导入的模块
        self._local_storage.setdefault("imported_modules", set()).add(name)

        return importlib.import_module(name, *args, **kwargs)

    def validate_path(self, path: str, permission: Permission) -> bool:
        """
        验证文件路径访问权限。

        Args:
            path: 文件路径
            permission: 所需权限

        Returns:
            如果允许访问返回 True
        """
        # 规范化路径
        abs_path = os.path.abspath(path)

        # 检查权限
        if not self.check_permission(permission):
            self.record_violation(
                permission=permission,
                action=f"file_access('{path}')",
                severity=ViolationSeverity.MEDIUM,
                message=f"Missing permission {permission.name} for path access",
            )
            return False

        # 检查路径是否被允许
        if not self.config.policy.is_path_allowed(abs_path):
            self.record_violation(
                permission=permission,
                action=f"file_access('{path}')",
                severity=ViolationSeverity.HIGH,
                message=f"Path '{path}' is not allowed by sandbox policy",
            )
            return False

        return True

    def validate_network_access(self, host: str, port: int) -> bool:
        """
        验证网络访问权限。

        Args:
            host: 目标主机
            port: 目标端口

        Returns:
            如果允许访问返回 True
        """
        # 检查网络权限
        if not self.check_permission(Permission.NETWORK):
            self.record_violation(
                permission=Permission.NETWORK,
                action=f"network_connect('{host}', {port})",
                severity=ViolationSeverity.HIGH,
                message="Network access is not allowed",
            )
            return False

        # 检查域名是否被允许
        if not self.config.policy.is_domain_allowed(host):
            self.record_violation(
                permission=Permission.NETWORK,
                action=f"network_connect('{host}', {port})",
                severity=ViolationSeverity.HIGH,
                message=f"Domain '{host}' is not allowed by sandbox policy",
            )
            return False

        return True

    def get_status_info(self) -> dict[str, Any]:
        """
        获取沙箱状态信息。

        Returns:
            状态信息字典
        """
        return {
            "sandbox_id": self.sandbox_id,
            "name": self.name,
            "status": self.status.value,
            "is_running": self.is_running,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "execution_count": self._execution_count,
            "violation_count": len(self.violations),
            "permissions": {p.name: entry.state.value for p, entry in self.permissions.items()},
        }

    def __enter__(self) -> "Sandbox":
        """上下文管理器入口。"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出。"""
        self.stop()

    def __repr__(self) -> str:
        """字符串表示。"""
        return f"Sandbox(id={self.sandbox_id}, name={self.name}, status={self.status.value})"


class nullcontext:
    """空上下文管理器，用于 Python 3.6 兼容性。"""

    def __enter__(self):
        return None

    def __exit__(self, *excinfo):
        pass


class SandboxBuilder:
    """
    沙箱构建器。

    提供流畅的 API 来构建和配置沙箱。

    Example:
        >>> sandbox = (SandboxBuilder()
        ...     .with_name("my_sandbox")
        ...     .with_permission(Permission.FILE_READ)
        ...     .with_resource_limit(max_memory_mb=512)
        ...     .build())
    """

    def __init__(self) -> None:
        """初始化构建器。"""
        self._name = "default_sandbox"
        self._permissions: set[Permission] = set()
        self._denied_permissions: set[Permission] = set()
        self._resource_limit = ResourceLimit()
        self._allowed_paths: list[str] = []
        self._denied_paths: list[str] = []
        self._allowed_domains: list[str] = []
        self._allowed_modules: list[str] = []
        self._denied_modules: list[str] = []
        self._timeout: float = 300.0
        self._max_violations: int = 10

    def with_name(self, name: str) -> "SandboxBuilder":
        """设置沙箱名称。"""
        self._name = name
        return self

    def with_permission(self, *permissions: Permission) -> "SandboxBuilder":
        """添加权限。"""
        self._permissions.update(permissions)
        return self

    def deny_permission(self, *permissions: Permission) -> "SandboxBuilder":
        """拒绝权限。"""
        self._denied_permissions.update(permissions)
        return self

    def with_resource_limit(self, **kwargs) -> "SandboxBuilder":
        """设置资源限制。"""
        current = self._resource_limit.to_dict()
        current.update(kwargs)
        self._resource_limit = ResourceLimit.from_dict(current)
        return self

    def allow_path(self, *paths: str) -> "SandboxBuilder":
        """允许路径访问。"""
        self._allowed_paths.extend(paths)
        return self

    def deny_path(self, *paths: str) -> "SandboxBuilder":
        """拒绝路径访问。"""
        self._denied_paths.extend(paths)
        return self

    def allow_domain(self, *domains: str) -> "SandboxBuilder":
        """允许域名访问。"""
        self._allowed_domains.extend(domains)
        return self

    def allow_module(self, *modules: str) -> "SandboxBuilder":
        """允许模块导入。"""
        self._allowed_modules.extend(modules)
        return self

    def deny_module(self, *modules: str) -> "SandboxBuilder":
        """拒绝模块导入。"""
        self._denied_modules.extend(modules)
        return self

    def with_timeout(self, timeout: float) -> "SandboxBuilder":
        """设置超时时间。"""
        self._timeout = timeout
        return self

    def with_max_violations(self, max_violations: int) -> "SandboxBuilder":
        """设置最大违规次数。"""
        self._max_violations = max_violations
        return self

    def build(self) -> Sandbox:
        """
        构建沙箱实例。

        Returns:
            配置好的沙箱实例
        """
        policy = SandboxPolicy(
            name=f"{self._name}_policy",
            permissions=self._permissions,
            denied_permissions=self._denied_permissions,
            resource_limits=self._resource_limit,
            allowed_paths=self._allowed_paths,
            denied_paths=self._denied_paths,
            allowed_domains=self._allowed_domains,
            allowed_modules=self._allowed_modules,
            denied_modules=self._denied_modules,
        )

        config = SandboxConfig(
            name=self._name,
            policy=policy,
            timeout=self._timeout,
            max_violations=self._max_violations,
        )

        return Sandbox(config)
