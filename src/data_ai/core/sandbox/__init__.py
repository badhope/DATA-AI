"""
安全沙箱模块。

本模块提供了完整的安全沙箱系统，用于在隔离环境中安全执行代码，
支持权限管理、资源限制、违规检测和多级隔离。

主要组件:
- Sandbox: 安全沙箱，提供代码执行和权限管理
- SandboxPolicy: 沙箱策略，定义权限和资源限制
- Permission: 权限枚举，定义所有可控制的权限
- ResourceLimit: 资源限制，定义 CPU、内存等限制
- PolicyManager: 策略管理器，管理策略的创建和应用
- ResourceMonitor: 资源监控器，实时监控资源使用
- ViolationDetector: 违规检测器，检测潜在违规行为
- IsolationManager: 隔离管理器，管理不同级别的隔离环境

使用示例:
    >>> from data_ai.core.sandbox import Sandbox, SandboxPolicy, Permission
    >>>
    >>> # 创建策略
    >>> policy = SandboxPolicy(
    ...     name="safe_policy",
    ...     permissions={Permission.FILE_READ, Permission.NETWORK_HTTPS},
    ...     resource_limits=ResourceLimit.moderate()
    ... )
    >>>
    >>> # 创建沙箱
    >>> with Sandbox(policy=policy) as sandbox:
    ...     result = sandbox.execute("x = 1 + 1; print(x)")
    ...     print(result.output)  # "2"

预设策略:
    - strict: 严格策略，最小权限集
    - moderate: 中等策略，平衡安全与功能
    - permissive: 宽松策略，适用于可信代码
    - readonly: 只读策略，适用于数据分析
    - network_restricted: 网络受限策略
    - data_processing: 数据处理策略
"""

# 类型定义
# 隔离机制
from .isolation import (
    ContainerIsolatedEnvironment,
    IsolatedEnvironment,
    IsolationConfig,
    IsolationContext,
    IsolationError,
    IsolationLevel,
    IsolationManager,
    ProcessIsolatedEnvironment,
    VMIsolatedEnvironment,
    create_isolation_context,
)

# 监控器
from .monitor import (
    LimitCheckResult,
    MonitoringContext,
    ResourceMonitor,
    UsageStats,
    ViolationDetector,
)

# 策略管理
from .policies import (
    PolicyError,
    PolicyManager,
    PolicyValidator,
    PresetPolicies,
)

# 沙箱核心
from .sandbox import (
    Sandbox,
    SandboxBuilder,
    SandboxException,
)
from .types import (
    ExecutionResult,
    # 枚举类型
    Permission,
    PermissionEntry,
    # 类型别名
    PermissionSet,
    PermissionState,
    PolicyDict,
    # 数据类
    ResourceLimit,
    SandboxConfig,
    SandboxPolicy,
    SandboxStatus,
    SandboxViolation,
    ViolationList,
    ViolationSeverity,
)

__all__ = [
    # 类型定义
    "Permission",
    "PermissionState",
    "ViolationSeverity",
    "SandboxStatus",
    "ResourceLimit",
    "SandboxPolicy",
    "SandboxViolation",
    "SandboxConfig",
    "PermissionEntry",
    "ExecutionResult",
    "PermissionSet",
    "ViolationList",
    "PolicyDict",
    # 沙箱核心
    "Sandbox",
    "SandboxException",
    "SandboxBuilder",
    # 策略管理
    "PolicyManager",
    "PolicyError",
    "PolicyValidator",
    "PresetPolicies",
    # 监控器
    "ResourceMonitor",
    "ViolationDetector",
    "UsageStats",
    "LimitCheckResult",
    "MonitoringContext",
    # 隔离机制
    "IsolationLevel",
    "IsolationConfig",
    "IsolationError",
    "IsolatedEnvironment",
    "ProcessIsolatedEnvironment",
    "ContainerIsolatedEnvironment",
    "VMIsolatedEnvironment",
    "IsolationManager",
    "IsolationContext",
    "create_isolation_context",
]


def create_sandbox(name: str = "default", policy_name: str = "moderate", **kwargs) -> Sandbox:
    """
    快速创建沙箱的便捷函数。

    Args:
        name: 沙箱名称
        policy_name: 预设策略名称 (strict, moderate, permissive, readonly, etc.)
        **kwargs: 额外配置参数

    Returns:
        配置好的沙箱实例

    Example:
        >>> sandbox = create_sandbox("my_sandbox", "strict")
        >>> sandbox.start()
        >>> result = sandbox.execute("print('hello')")
        >>> sandbox.stop()
    """
    # 获取预设策略
    policy = PresetPolicies.get(policy_name)
    if policy is None:
        policy = SandboxPolicy(name=policy_name)

    # 创建配置
    config = SandboxConfig(name=name, policy=policy, **kwargs)

    return Sandbox(config)


def quick_execute(code: str, policy_name: str = "moderate", timeout: float = 30.0) -> ExecutionResult:
    """
    快速执行代码的便捷函数。

    创建临时沙箱执行代码并返回结果。

    Args:
        code: 要执行的代码
        policy_name: 预设策略名称
        timeout: 超时时间

    Returns:
        执行结果

    Example:
        >>> result = quick_execute("x = 1 + 1; x * 2")
        >>> print(result.return_value)  # 4
    """
    sandbox = create_sandbox(name="quick_execute", policy_name=policy_name, timeout=timeout)

    with sandbox:
        return sandbox.execute(code)


# 版本信息
__version__ = "1.0.0"
__author__ = "DATA-AI Team"
