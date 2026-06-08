"""
安全沙箱类型定义模块。

本模块定义了安全沙箱系统所需的所有核心类型和数据结构，
用于权限控制、资源限制、违规记录和沙箱状态管理。

主要类型:
- Permission: 权限枚举
- ResourceLimit: 资源限制
- SandboxPolicy: 沙箱策略
- SandboxViolation: 违规记录
- SandboxStatus: 沙箱状态
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class Permission(Enum):
    """
    权限枚举类。

    定义沙箱中可授予或撤销的所有权限类型。

    Attributes:
        FILE_READ: 文件读取权限
        FILE_WRITE: 文件写入权限
        FILE_DELETE: 文件删除权限
        FILE_EXECUTE: 文件执行权限
        NETWORK: 网络访问权限
        NETWORK_HTTP: HTTP 网络访问权限
        NETWORK_HTTPS: HTTPS 网络访问权限
        NETWORK_SOCKET: 原始套接字权限
        EXECUTE: 代码执行权限
        SUBPROCESS: 子进程创建权限
        ENVIRONMENT: 环境变量访问权限
        SYSTEM_INFO: 系统信息访问权限
        MEMORY_INTENSIVE: 内存密集操作权限
        CPU_INTENSIVE: CPU 密集操作权限
        IMPORT_MODULE: 模块导入权限
        NATIVE_CALL: 原生调用权限
    """

    # 文件系统权限
    FILE_READ = auto()
    FILE_WRITE = auto()
    FILE_DELETE = auto()
    FILE_EXECUTE = auto()

    # 网络权限
    NETWORK = auto()
    NETWORK_HTTP = auto()
    NETWORK_HTTPS = auto()
    NETWORK_SOCKET = auto()

    # 执行权限
    EXECUTE = auto()
    SUBPROCESS = auto()

    # 系统权限
    ENVIRONMENT = auto()
    SYSTEM_INFO = auto()

    # 资源权限
    MEMORY_INTENSIVE = auto()
    CPU_INTENSIVE = auto()

    # 高级权限
    IMPORT_MODULE = auto()
    NATIVE_CALL = auto()

    @classmethod
    def file_permissions(cls) -> set["Permission"]:
        """获取所有文件相关权限。"""
        return {cls.FILE_READ, cls.FILE_WRITE, cls.FILE_DELETE, cls.FILE_EXECUTE}

    @classmethod
    def network_permissions(cls) -> set["Permission"]:
        """获取所有网络相关权限。"""
        return {cls.NETWORK, cls.NETWORK_HTTP, cls.NETWORK_HTTPS, cls.NETWORK_SOCKET}

    @classmethod
    def dangerous_permissions(cls) -> set["Permission"]:
        """获取所有危险权限。"""
        return {
            cls.FILE_DELETE,
            cls.FILE_EXECUTE,
            cls.NETWORK_SOCKET,
            cls.EXECUTE,
            cls.SUBPROCESS,
            cls.NATIVE_CALL,
        }


class PermissionState(Enum):
    """
    权限状态枚举。

    Attributes:
        GRANTED: 已授权
        DENIED: 已拒绝
        REVOKED: 已撤销
        PENDING: 待审批
    """

    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    PENDING = "pending"


@dataclass
class ResourceLimit:
    """
    资源限制配置。

    定义沙箱中可使用的资源上限，用于防止资源滥用。

    Attributes:
        max_cpu_percent: 最大 CPU 使用百分比 (0-100)
        max_memory_mb: 最大内存使用量 (MB)
        max_execution_time_seconds: 最大执行时间 (秒)
        max_file_size_mb: 最大文件大小 (MB)
        max_open_files: 最大打开文件数
        max_network_connections: 最大网络连接数
        max_subprocesses: 最大子进程数
        max_output_size_mb: 最大输出大小 (MB)

    Example:
        >>> limits = ResourceLimit(
        ...     max_cpu_percent=50,
        ...     max_memory_mb=512,
        ...     max_execution_time_seconds=60
        ... )
    """

    max_cpu_percent: float = 80.0
    max_memory_mb: int = 1024
    max_execution_time_seconds: float = 300.0
    max_file_size_mb: int = 100
    max_open_files: int = 100
    max_network_connections: int = 10
    max_subprocesses: int = 5
    max_output_size_mb: int = 50

    def to_dict(self) -> dict[str, Any]:
        """将资源限制转换为字典格式。"""
        return {
            "max_cpu_percent": self.max_cpu_percent,
            "max_memory_mb": self.max_memory_mb,
            "max_execution_time_seconds": self.max_execution_time_seconds,
            "max_file_size_mb": self.max_file_size_mb,
            "max_open_files": self.max_open_files,
            "max_network_connections": self.max_network_connections,
            "max_subprocesses": self.max_subprocesses,
            "max_output_size_mb": self.max_output_size_mb,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceLimit":
        """从字典创建资源限制实例。"""
        return cls(
            max_cpu_percent=data.get("max_cpu_percent", 80.0),
            max_memory_mb=data.get("max_memory_mb", 1024),
            max_execution_time_seconds=data.get("max_execution_time_seconds", 300.0),
            max_file_size_mb=data.get("max_file_size_mb", 100),
            max_open_files=data.get("max_open_files", 100),
            max_network_connections=data.get("max_network_connections", 10),
            max_subprocesses=data.get("max_subprocesses", 5),
            max_output_size_mb=data.get("max_output_size_mb", 50),
        )

    @classmethod
    def strict(cls) -> "ResourceLimit":
        """创建严格资源限制。"""
        return cls(
            max_cpu_percent=25.0,
            max_memory_mb=256,
            max_execution_time_seconds=30.0,
            max_file_size_mb=10,
            max_open_files=20,
            max_network_connections=2,
            max_subprocesses=1,
            max_output_size_mb=10,
        )

    @classmethod
    def moderate(cls) -> "ResourceLimit":
        """创建中等资源限制。"""
        return cls(
            max_cpu_percent=50.0,
            max_memory_mb=512,
            max_execution_time_seconds=120.0,
            max_file_size_mb=50,
            max_open_files=50,
            max_network_connections=5,
            max_subprocesses=3,
            max_output_size_mb=30,
        )

    @classmethod
    def permissive(cls) -> "ResourceLimit":
        """创建宽松资源限制。"""
        return cls(
            max_cpu_percent=90.0,
            max_memory_mb=2048,
            max_execution_time_seconds=600.0,
            max_file_size_mb=500,
            max_open_files=200,
            max_network_connections=20,
            max_subprocesses=10,
            max_output_size_mb=100,
        )


class ViolationSeverity(Enum):
    """
    违规严重程度枚举。

    Attributes:
        LOW: 低严重程度，仅记录
        MEDIUM: 中等严重程度，发出警告
        HIGH: 高严重程度，终止操作
        CRITICAL: 严重违规，终止沙箱
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def should_terminate(self) -> bool:
        """判断是否应终止执行。"""
        return self in (ViolationSeverity.HIGH, ViolationSeverity.CRITICAL)

    def should_warn(self) -> bool:
        """判断是否应发出警告。"""
        return self in (ViolationSeverity.MEDIUM, ViolationSeverity.HIGH, ViolationSeverity.CRITICAL)


@dataclass
class SandboxViolation:
    """
    沙箱违规记录。

    记录沙箱中发生的违规行为，包括违规类型、时间、严重程度等信息。

    Attributes:
        violation_id: 违规记录唯一标识
        permission: 相关权限
        action: 尝试执行的动作
        severity: 违规严重程度
        message: 违规消息
        timestamp: 违规发生时间
        context: 违规上下文信息
        stack_trace: 堆栈跟踪（可选）
        resolved: 是否已处理
        resolution: 处理结果

    Example:
        >>> violation = SandboxViolation(
        ...     permission=Permission.FILE_READ,
        ...     action="read('/etc/passwd')",
        ...     severity=ViolationSeverity.HIGH,
        ...     message="Attempted to read restricted file"
        ... )
    """

    permission: Permission
    action: str
    severity: ViolationSeverity
    message: str
    violation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    context: dict[str, Any] = field(default_factory=dict)
    stack_trace: str | None = None
    resolved: bool = False
    resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """将违规记录转换为字典格式。"""
        return {
            "violation_id": self.violation_id,
            "permission": self.permission.name,
            "action": self.action,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "stack_trace": self.stack_trace,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SandboxViolation":
        """从字典创建违规记录实例。"""
        return cls(
            violation_id=data["violation_id"],
            permission=Permission[data["permission"]],
            action=data["action"],
            severity=ViolationSeverity(data["severity"]),
            message=data["message"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            context=data.get("context", {}),
            stack_trace=data.get("stack_trace"),
            resolved=data.get("resolved", False),
            resolution=data.get("resolution"),
        )

    def resolve(self, resolution: str) -> None:
        """
        标记违规已处理。

        Args:
            resolution: 处理结果说明
        """
        self.resolved = True
        self.resolution = resolution


class SandboxStatus(Enum):
    """
    沙箱状态枚举。

    定义沙箱可能处于的所有状态。

    Attributes:
        CREATED: 已创建，尚未启动
        INITIALIZING: 正在初始化
        RUNNING: 正在运行
        PAUSED: 已暂停
        STOPPING: 正在停止
        STOPPED: 已停止
        ERROR: 发生错误
        TERMINATED: 已终止（违规或其他原因）
    """

    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    TERMINATED = "terminated"

    def is_active(self) -> bool:
        """检查沙箱是否处于活动状态。"""
        return self in (SandboxStatus.RUNNING, SandboxStatus.PAUSED)

    def is_terminal(self) -> bool:
        """检查沙箱是否处于终止状态。"""
        return self in (SandboxStatus.STOPPED, SandboxStatus.ERROR, SandboxStatus.TERMINATED)

    def can_execute(self) -> bool:
        """检查沙箱是否可以执行代码。"""
        return self == SandboxStatus.RUNNING


@dataclass
class PermissionEntry:
    """
    权限条目。

    记录单个权限的授权状态和相关信息。

    Attributes:
        permission: 权限类型
        state: 权限状态
        granted_at: 授权时间
        granted_by: 授权来源
        expires_at: 过期时间（可选）
        conditions: 授权条件
    """

    permission: Permission
    state: PermissionState = PermissionState.PENDING
    granted_at: datetime | None = None
    granted_by: str | None = None
    expires_at: datetime | None = None
    conditions: dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """检查权限是否有效。"""
        if self.state != PermissionState.GRANTED:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """将权限条目转换为字典格式。"""
        return {
            "permission": self.permission.name,
            "state": self.state.value,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "granted_by": self.granted_by,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "conditions": self.conditions,
        }


@dataclass
class SandboxPolicy:
    """
    沙箱策略配置。

    定义沙箱的完整安全策略，包括权限集合、资源限制和特殊规则。

    Attributes:
        policy_id: 策略唯一标识
        name: 策略名称
        description: 策略描述
        permissions: 授予的权限集合
        denied_permissions: 明确拒绝的权限集合
        resource_limits: 资源限制
        allowed_paths: 允许访问的文件路径
        denied_paths: 禁止访问的文件路径
        allowed_domains: 允许访问的网络域名
        allowed_modules: 允许导入的模块
        denied_modules: 禁止导入的模块
        created_at: 创建时间
        updated_at: 更新时间
        is_default: 是否为默认策略
        priority: 策略优先级（数值越高优先级越高）

    Example:
        >>> policy = SandboxPolicy(
        ...     name="web_scraper",
        ...     description="Policy for web scraping tasks",
        ...     permissions={Permission.FILE_READ, Permission.NETWORK_HTTPS},
        ...     resource_limits=ResourceLimit.moderate()
        ... )
    """

    name: str = "default_policy"
    description: str = ""
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    permissions: set[Permission] = field(default_factory=set)
    denied_permissions: set[Permission] = field(default_factory=set)
    resource_limits: ResourceLimit = field(default_factory=ResourceLimit)
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=list)
    allowed_domains: list[str] = field(default_factory=list)
    allowed_modules: list[str] = field(default_factory=list)
    denied_modules: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_default: bool = False
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        """将策略转换为字典格式。"""
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.name for p in self.permissions],
            "denied_permissions": [p.name for p in self.denied_permissions],
            "resource_limits": self.resource_limits.to_dict(),
            "allowed_paths": self.allowed_paths,
            "denied_paths": self.denied_paths,
            "allowed_domains": self.allowed_domains,
            "allowed_modules": self.allowed_modules,
            "denied_modules": self.denied_modules,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_default": self.is_default,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SandboxPolicy":
        """从字典创建策略实例。"""
        return cls(
            policy_id=data["policy_id"],
            name=data["name"],
            description=data.get("description", ""),
            permissions={Permission[p] for p in data.get("permissions", [])},
            denied_permissions={Permission[p] for p in data.get("denied_permissions", [])},
            resource_limits=ResourceLimit.from_dict(data.get("resource_limits", {})),
            allowed_paths=data.get("allowed_paths", []),
            denied_paths=data.get("denied_paths", []),
            allowed_domains=data.get("allowed_domains", []),
            allowed_modules=data.get("allowed_modules", []),
            denied_modules=data.get("denied_modules", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            is_default=data.get("is_default", False),
            priority=data.get("priority", 0),
        )

    def has_permission(self, permission: Permission) -> bool:
        """
        检查策略是否包含指定权限。

        Args:
            permission: 要检查的权限

        Returns:
            如果权限被授予且未被拒绝则返回 True
        """
        if permission in self.denied_permissions:
            return False
        return permission in self.permissions

    def is_path_allowed(self, path: str) -> bool:
        """
        检查路径是否被允许访问。

        Args:
            path: 要检查的文件路径

        Returns:
            如果路径被允许则返回 True
        """
        # 首先检查拒绝列表
        for denied in self.denied_paths:
            if path.startswith(denied):
                return False

        # 如果允许列表为空，则允许所有未被拒绝的路径
        if not self.allowed_paths:
            return True

        # 检查允许列表
        for allowed in self.allowed_paths:
            if path.startswith(allowed):
                return True

        return False

    def is_domain_allowed(self, domain: str) -> bool:
        """
        检查域名是否被允许访问。

        Args:
            domain: 要检查的域名

        Returns:
            如果域名被允许则返回 True
        """
        if not self.allowed_domains:
            return True
        return domain in self.allowed_domains

    def is_module_allowed(self, module: str) -> bool:
        """
        检查模块是否被允许导入。

        Args:
            module: 要检查的模块名

        Returns:
            如果模块被允许则返回 True
        """
        # 检查拒绝列表
        for denied in self.denied_modules:
            if module == denied or module.startswith(f"{denied}."):
                return False

        # 如果允许列表为空，则允许所有未被拒绝的模块
        if not self.allowed_modules:
            return True

        # 检查允许列表
        for allowed in self.allowed_modules:
            if module == allowed or module.startswith(f"{allowed}."):
                return True

        return False

    def merge(self, other: "SandboxPolicy") -> "SandboxPolicy":
        """
        合并两个策略。

        Args:
            other: 要合并的另一个策略

        Returns:
            合并后的新策略
        """
        # 使用较高优先级的策略作为基础

        return SandboxPolicy(
            name=f"{self.name}+{other.name}",
            description=f"Merged policy: {self.description} | {other.description}",
            permissions=self.permissions | other.permissions,
            denied_permissions=self.denied_permissions | other.denied_permissions,
            resource_limits=ResourceLimit(
                max_cpu_percent=min(self.resource_limits.max_cpu_percent, other.resource_limits.max_cpu_percent),
                max_memory_mb=min(self.resource_limits.max_memory_mb, other.resource_limits.max_memory_mb),
                max_execution_time_seconds=min(
                    self.resource_limits.max_execution_time_seconds, other.resource_limits.max_execution_time_seconds
                ),
                max_file_size_mb=min(self.resource_limits.max_file_size_mb, other.resource_limits.max_file_size_mb),
                max_open_files=min(self.resource_limits.max_open_files, other.resource_limits.max_open_files),
                max_network_connections=min(
                    self.resource_limits.max_network_connections, other.resource_limits.max_network_connections
                ),
                max_subprocesses=min(self.resource_limits.max_subprocesses, other.resource_limits.max_subprocesses),
                max_output_size_mb=min(
                    self.resource_limits.max_output_size_mb, other.resource_limits.max_output_size_mb
                ),
            ),
            allowed_paths=list(set(self.allowed_paths + other.allowed_paths)),
            denied_paths=list(set(self.denied_paths + other.denied_paths)),
            allowed_domains=list(set(self.allowed_domains + other.allowed_domains)),
            allowed_modules=list(set(self.allowed_modules + other.allowed_modules)),
            denied_modules=list(set(self.denied_modules + other.denied_modules)),
            priority=max(self.priority, other.priority),
        )


@dataclass
class SandboxConfig:
    """
    沙箱配置。

    配置沙箱的行为参数。

    Attributes:
        sandbox_id: 沙箱唯一标识
        name: 沙箱名称
        policy: 沙箱策略
        enable_monitoring: 是否启用监控
        enable_logging: 是否启用日志
        log_level: 日志级别
        max_violations: 最大违规次数（超过后终止）
        auto_terminate_on_violation: 严重违规时是否自动终止
        working_directory: 工作目录
        environment_variables: 环境变量
        timeout: 默认超时时间
    """

    name: str = "default_sandbox"
    sandbox_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    policy: SandboxPolicy = field(default_factory=SandboxPolicy)
    enable_monitoring: bool = True
    enable_logging: bool = True
    log_level: str = "INFO"
    max_violations: int = 10
    auto_terminate_on_violation: bool = True
    working_directory: str | None = None
    environment_variables: dict[str, str] = field(default_factory=dict)
    timeout: float = 300.0

    def to_dict(self) -> dict[str, Any]:
        """将配置转换为字典格式。"""
        return {
            "sandbox_id": self.sandbox_id,
            "name": self.name,
            "policy": self.policy.to_dict(),
            "enable_monitoring": self.enable_monitoring,
            "enable_logging": self.enable_logging,
            "log_level": self.log_level,
            "max_violations": self.max_violations,
            "auto_terminate_on_violation": self.auto_terminate_on_violation,
            "working_directory": self.working_directory,
            "environment_variables": self.environment_variables,
            "timeout": self.timeout,
        }


@dataclass
class ExecutionResult:
    """
    执行结果。

    记录沙箱中代码执行的结果。

    Attributes:
        success: 是否成功
        output: 标准输出
        error: 标准错误
        return_value: 返回值
        execution_time: 执行时间（秒）
        violations: 执行期间的违规记录
        resource_usage: 资源使用情况
    """

    success: bool
    output: str = ""
    error: str = ""
    return_value: Any = None
    execution_time: float = 0.0
    violations: list[SandboxViolation] = field(default_factory=list)
    resource_usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """将结果转换为字典格式。"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "return_value": str(self.return_value) if self.return_value is not None else None,
            "execution_time": self.execution_time,
            "violations": [v.to_dict() for v in self.violations],
            "resource_usage": self.resource_usage,
        }


# 类型别名
PermissionSet = set[Permission]
"""权限集合类型。"""

ViolationList = list[SandboxViolation]
"""违规记录列表类型。"""

PolicyDict = dict[str, SandboxPolicy]
"""策略字典类型。"""
