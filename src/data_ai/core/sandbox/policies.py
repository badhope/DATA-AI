"""
沙箱策略管理模块。

本模块实现了沙箱策略的管理功能，包括策略创建、应用、验证和预设策略。

主要类:
- PolicyManager: 策略管理器
- PresetPolicies: 预设策略集合
- PolicyValidator: 策略验证器
"""

import json
import os
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .types import (
    Permission,
    ResourceLimit,
    SandboxPolicy,
    SandboxViolation,
    ViolationSeverity,
)


class PolicyError(Exception):
    """策略相关错误。"""

    def __init__(self, message: str, code: str = "POLICY_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class PolicyManager:
    """
    策略管理器。

    管理沙箱策略的创建、存储、检索和应用。

    Attributes:
        policies: 策略字典
        default_policy: 默认策略

    Example:
        >>> manager = PolicyManager()
        >>> policy = manager.create_policy(
        ...     name="web_access",
        ...     permissions={Permission.NETWORK_HTTPS},
        ...     resource_limits=ResourceLimit.moderate()
        ... )
        >>> manager.apply_policy(sandbox, policy)
    """

    def __init__(self, storage_path: str | None = None) -> None:
        """
        初始化策略管理器。

        Args:
            storage_path: 策略存储路径（可选）
        """
        self.policies: dict[str, SandboxPolicy] = {}
        self.default_policy: SandboxPolicy | None = None
        self._storage_path = storage_path
        self._validators: list[Callable[[SandboxPolicy], bool]] = []

        # 加载预设策略
        self._load_preset_policies()

        # 从存储加载策略
        if storage_path and os.path.exists(storage_path):
            self._load_from_storage()

    def _load_preset_policies(self) -> None:
        """加载预设策略。"""
        for policy in PresetPolicies.all():
            self.policies[policy.policy_id] = policy
            if policy.is_default:
                self.default_policy = policy

    def _load_from_storage(self) -> None:
        """从存储加载策略。"""
        try:
            with open(self._storage_path, encoding="utf-8") as f:
                data = json.load(f)
                for policy_data in data.get("policies", []):
                    policy = SandboxPolicy.from_dict(policy_data)
                    self.policies[policy.policy_id] = policy
        except Exception as e:
            raise PolicyError(f"Failed to load policies: {e}", "LOAD_ERROR")

    def _save_to_storage(self) -> None:
        """保存策略到存储。"""
        if not self._storage_path:
            return

        try:
            data = {
                "policies": [p.to_dict() for p in self.policies.values()],
                "updated_at": datetime.now().isoformat(),
            }
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise PolicyError(f"Failed to save policies: {e}", "SAVE_ERROR")

    def create_policy(
        self,
        name: str,
        description: str = "",
        permissions: set[Permission] | None = None,
        denied_permissions: set[Permission] | None = None,
        resource_limits: ResourceLimit | None = None,
        allowed_paths: list[str] | None = None,
        denied_paths: list[str] | None = None,
        allowed_domains: list[str] | None = None,
        allowed_modules: list[str] | None = None,
        denied_modules: list[str] | None = None,
        is_default: bool = False,
        priority: int = 0,
    ) -> SandboxPolicy:
        """
        创建新策略。

        Args:
            name: 策略名称
            description: 策略描述
            permissions: 授予的权限集合
            denied_permissions: 拒绝的权限集合
            resource_limits: 资源限制
            allowed_paths: 允许的路径
            denied_paths: 拒绝的路径
            allowed_domains: 允许的域名
            allowed_modules: 允许的模块
            denied_modules: 拒绝的模块
            is_default: 是否为默认策略
            priority: 优先级

        Returns:
            创建的策略

        Raises:
            PolicyError: 如果策略名称已存在或验证失败
        """
        # 检查名称是否已存在
        for policy in self.policies.values():
            if policy.name == name:
                raise PolicyError(f"Policy with name '{name}' already exists", "DUPLICATE_NAME")

        # 创建策略
        policy = SandboxPolicy(
            name=name,
            description=description,
            permissions=permissions or set(),
            denied_permissions=denied_permissions or set(),
            resource_limits=resource_limits or ResourceLimit(),
            allowed_paths=allowed_paths or [],
            denied_paths=denied_paths or [],
            allowed_domains=allowed_domains or [],
            allowed_modules=allowed_modules or [],
            denied_modules=denied_modules or [],
            is_default=is_default,
            priority=priority,
        )

        # 验证策略
        self._validate_policy(policy)

        # 存储策略
        self.policies[policy.policy_id] = policy

        # 更新默认策略
        if is_default:
            self._set_default_policy(policy)

        # 保存到存储
        self._save_to_storage()

        return policy

    def _validate_policy(self, policy: SandboxPolicy) -> bool:
        """
        验证策略。

        Args:
            policy: 要验证的策略

        Returns:
            如果验证通过返回 True

        Raises:
            PolicyError: 如果验证失败
        """
        # 检查权限冲突
        conflicts = policy.permissions & policy.denied_permissions
        if conflicts:
            raise PolicyError(f"Permission conflict: {conflicts} are both granted and denied", "PERMISSION_CONFLICT")

        # 运行自定义验证器
        for validator in self._validators:
            if not validator(policy):
                raise PolicyError("Policy failed custom validation", "VALIDATION_FAILED")

        return True

    def _set_default_policy(self, policy: SandboxPolicy) -> None:
        """设置默认策略。"""
        # 清除其他默认标记
        for p in self.policies.values():
            if p.policy_id != policy.policy_id:
                p.is_default = False

        self.default_policy = policy

    def get_policy(self, policy_id: str) -> SandboxPolicy | None:
        """
        获取策略。

        Args:
            policy_id: 策略 ID

        Returns:
            策略实例，如果不存在返回 None
        """
        return self.policies.get(policy_id)

    def get_policy_by_name(self, name: str) -> SandboxPolicy | None:
        """
        按名称获取策略。

        Args:
            name: 策略名称

        Returns:
            策略实例，如果不存在返回 None
        """
        for policy in self.policies.values():
            if policy.name == name:
                return policy
        return None

    def update_policy(self, policy_id: str, **kwargs) -> SandboxPolicy:
        """
        更新策略。

        Args:
            policy_id: 策略 ID
            **kwargs: 要更新的字段

        Returns:
            更新后的策略

        Raises:
            PolicyError: 如果策略不存在或更新失败
        """
        if policy_id not in self.policies:
            raise PolicyError(f"Policy '{policy_id}' not found", "NOT_FOUND")

        policy = self.policies[policy_id]

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
            else:
                raise PolicyError(f"Unknown policy field: {key}", "UNKNOWN_FIELD")

        # 更新时间戳
        policy.updated_at = datetime.now()

        # 重新验证
        self._validate_policy(policy)

        # 保存
        self._save_to_storage()

        return policy

    def delete_policy(self, policy_id: str) -> bool:
        """
        删除策略。

        Args:
            policy_id: 策略 ID

        Returns:
            如果删除成功返回 True
        """
        if policy_id not in self.policies:
            return False

        del self.policies[policy_id]
        self._save_to_storage()
        return True

    def list_policies(self, include_presets: bool = True) -> list[SandboxPolicy]:
        """
        列出所有策略。

        Args:
            include_presets: 是否包含预设策略

        Returns:
            策略列表
        """
        policies = list(self.policies.values())

        if not include_presets:
            preset_ids = {p.policy_id for p in PresetPolicies.all()}
            policies = [p for p in policies if p.policy_id not in preset_ids]

        return sorted(policies, key=lambda p: p.priority, reverse=True)

    def apply_policy(self, sandbox: Any, policy: str | SandboxPolicy) -> None:
        """
        将策略应用到沙箱。

        Args:
            sandbox: 沙箱实例
            policy: 策略 ID 或策略实例

        Raises:
            PolicyError: 如果策略不存在或应用失败
        """
        # 获取策略
        if isinstance(policy, str):
            policy = self.get_policy(policy) or self.get_policy_by_name(policy)
            if policy is None:
                raise PolicyError(f"Policy '{policy}' not found", "NOT_FOUND")

        # 应用策略到沙箱
        if hasattr(sandbox, "config"):
            sandbox.config.policy = policy

            # 更新权限
            if hasattr(sandbox, "_init_permissions_from_policy"):
                sandbox._init_permissions_from_policy()
        else:
            raise PolicyError("Invalid sandbox object", "INVALID_SANDBOX")

    def validate_action(
        self,
        policy: str | SandboxPolicy,
        action: str,
        resource: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, SandboxViolation | None]:
        """
        验证动作是否符合策略。

        Args:
            policy: 策略 ID 或策略实例
            action: 动作类型
            resource: 相关资源
            context: 上下文信息

        Returns:
            (是否允许, 违规记录) 元组
        """
        # 获取策略
        if isinstance(policy, str):
            policy = self.get_policy(policy) or self.get_policy_by_name(policy)
            if policy is None:
                return False, SandboxViolation(
                    permission=Permission.EXECUTE,
                    action=action,
                    severity=ViolationSeverity.HIGH,
                    message=f"Policy '{policy}' not found",
                )

        # 解析动作
        action_permission = self._map_action_to_permission(action)

        if action_permission is None:
            return True, None

        # 检查权限
        if not policy.has_permission(action_permission):
            return False, SandboxViolation(
                permission=action_permission,
                action=action,
                severity=ViolationSeverity.MEDIUM,
                message=f"Action '{action}' requires permission {action_permission.name}",
                context=context or {},
            )

        # 检查资源限制
        if resource:
            if action_permission in Permission.file_permissions():
                if not policy.is_path_allowed(resource):
                    return False, SandboxViolation(
                        permission=action_permission,
                        action=action,
                        severity=ViolationSeverity.HIGH,
                        message=f"Path '{resource}' is not allowed",
                        context=context or {},
                    )
            elif action_permission in Permission.network_permissions():
                if not policy.is_domain_allowed(resource):
                    return False, SandboxViolation(
                        permission=action_permission,
                        action=action,
                        severity=ViolationSeverity.HIGH,
                        message=f"Domain '{resource}' is not allowed",
                        context=context or {},
                    )

        return True, None

    def _map_action_to_permission(self, action: str) -> Permission | None:
        """
        将动作映射到权限。

        Args:
            action: 动作名称

        Returns:
            对应的权限，如果无法映射返回 None
        """
        action_map = {
            "file_read": Permission.FILE_READ,
            "file_write": Permission.FILE_WRITE,
            "file_delete": Permission.FILE_DELETE,
            "file_execute": Permission.FILE_EXECUTE,
            "network": Permission.NETWORK,
            "network_http": Permission.NETWORK_HTTP,
            "network_https": Permission.NETWORK_HTTPS,
            "network_socket": Permission.NETWORK_SOCKET,
            "execute": Permission.EXECUTE,
            "subprocess": Permission.SUBPROCESS,
            "import": Permission.IMPORT_MODULE,
            "native_call": Permission.NATIVE_CALL,
        }
        return action_map.get(action.lower())

    def add_validator(self, validator: Callable[[SandboxPolicy], bool]) -> None:
        """
        添加自定义验证器。

        Args:
            validator: 验证函数，接受策略并返回布尔值
        """
        self._validators.append(validator)

    def remove_validator(self, validator: Callable[[SandboxPolicy], bool]) -> bool:
        """
        移除验证器。

        Args:
            validator: 要移除的验证函数

        Returns:
            如果移除成功返回 True
        """
        try:
            self._validators.remove(validator)
            return True
        except ValueError:
            return False

    def merge_policies(self, policy_ids: list[str], name: str | None = None) -> SandboxPolicy:
        """
        合并多个策略。

        Args:
            policy_ids: 要合并的策略 ID 列表
            name: 新策略名称

        Returns:
            合并后的策略

        Raises:
            PolicyError: 如果任何策略不存在
        """
        policies = []
        for pid in policy_ids:
            if pid not in self.policies:
                raise PolicyError(f"Policy '{pid}' not found", "NOT_FOUND")
            policies.append(self.policies[pid])

        if not policies:
            raise PolicyError("No policies to merge", "EMPTY_LIST")

        # 合并策略
        result = policies[0]
        for p in policies[1:]:
            result = result.merge(p)

        # 设置名称
        if name:
            result.name = name

        return result

    def export_policy(self, policy_id: str) -> str:
        """
        导出策略为 JSON 字符串。

        Args:
            policy_id: 策略 ID

        Returns:
            JSON 字符串
        """
        if policy_id not in self.policies:
            raise PolicyError(f"Policy '{policy_id}' not found", "NOT_FOUND")

        return json.dumps(self.policies[policy_id].to_dict(), indent=2, ensure_ascii=False)

    def import_policy(self, json_str: str) -> SandboxPolicy:
        """
        从 JSON 字符串导入策略。

        Args:
            json_str: JSON 字符串

        Returns:
            导入的策略
        """
        try:
            data = json.loads(json_str)
            policy = SandboxPolicy.from_dict(data)

            # 生成新 ID 避免冲突
            policy.policy_id = str(uuid.uuid4())

            # 验证并存储
            self._validate_policy(policy)
            self.policies[policy.policy_id] = policy
            self._save_to_storage()

            return policy
        except Exception as e:
            raise PolicyError(f"Failed to import policy: {e}", "IMPORT_ERROR")


class PresetPolicies:
    """
    预设策略集合。

    提供常用的预设安全策略。
    """

    @staticmethod
    def strict() -> SandboxPolicy:
        """
        严格策略。

        最小权限集，适用于不可信代码执行。
        """
        return SandboxPolicy(
            name="strict",
            description="严格安全策略，最小权限集，适用于不可信代码",
            permissions=set(),  # 无默认权限
            denied_permissions=Permission.dangerous_permissions(),
            resource_limits=ResourceLimit.strict(),
            denied_paths=["/etc", "/root", "/home", "/var", "/usr"],
            denied_modules=["os", "sys", "subprocess", "socket", "ctypes", "multiprocessing", "threading"],
            is_default=False,
            priority=100,
        )

    @staticmethod
    def moderate() -> SandboxPolicy:
        """
        中等策略。

        平衡的安全策略，适用于一般用途。
        """
        return SandboxPolicy(
            name="moderate",
            description="中等安全策略，平衡安全性与功能性",
            permissions={
                Permission.FILE_READ,
                Permission.NETWORK_HTTP,
                Permission.NETWORK_HTTPS,
                Permission.IMPORT_MODULE,
            },
            denied_permissions={
                Permission.FILE_DELETE,
                Permission.NETWORK_SOCKET,
                Permission.SUBPROCESS,
                Permission.NATIVE_CALL,
            },
            resource_limits=ResourceLimit.moderate(),
            allowed_modules=[
                "json",
                "re",
                "datetime",
                "math",
                "random",
                "collections",
                "itertools",
                "functools",
                "typing",
                "dataclasses",
                "pathlib",
            ],
            denied_modules=[
                "ctypes",
                "multiprocessing",
            ],
            is_default=True,
            priority=50,
        )

    @staticmethod
    def permissive() -> SandboxPolicy:
        """
        宽松策略。

        较宽松的限制，适用于可信代码。
        """
        return SandboxPolicy(
            name="permissive",
            description="宽松安全策略，适用于可信代码执行",
            permissions={
                Permission.FILE_READ,
                Permission.FILE_WRITE,
                Permission.NETWORK,
                Permission.NETWORK_HTTP,
                Permission.NETWORK_HTTPS,
                Permission.EXECUTE,
                Permission.IMPORT_MODULE,
                Permission.ENVIRONMENT,
            },
            denied_permissions={
                Permission.FILE_DELETE,
                Permission.NATIVE_CALL,
            },
            resource_limits=ResourceLimit.permissive(),
            denied_modules=["ctypes"],
            is_default=False,
            priority=10,
        )

    @staticmethod
    def readonly() -> SandboxPolicy:
        """
        只读策略。

        仅允许读取操作，适用于数据分析。
        """
        return SandboxPolicy(
            name="readonly",
            description="只读策略，适用于数据分析场景",
            permissions={
                Permission.FILE_READ,
                Permission.NETWORK_HTTP,
                Permission.NETWORK_HTTPS,
                Permission.IMPORT_MODULE,
            },
            denied_permissions={
                Permission.FILE_WRITE,
                Permission.FILE_DELETE,
                Permission.FILE_EXECUTE,
                Permission.SUBPROCESS,
                Permission.NATIVE_CALL,
            },
            resource_limits=ResourceLimit.moderate(),
            allowed_modules=[
                "json",
                "re",
                "datetime",
                "math",
                "random",
                "collections",
                "itertools",
                "functools",
                "typing",
                "dataclasses",
                "pathlib",
                "pandas",
                "numpy",
                "csv",
            ],
            is_default=False,
            priority=60,
        )

    @staticmethod
    def network_restricted() -> SandboxPolicy:
        """
        网络受限策略。

        禁止所有网络访问，适用于离线处理。
        """
        return SandboxPolicy(
            name="network_restricted",
            description="网络受限策略，禁止所有网络访问",
            permissions={
                Permission.FILE_READ,
                Permission.FILE_WRITE,
                Permission.IMPORT_MODULE,
            },
            denied_permissions=Permission.network_permissions()
            | {
                Permission.SUBPROCESS,
                Permission.NATIVE_CALL,
            },
            resource_limits=ResourceLimit.moderate(),
            is_default=False,
            priority=70,
        )

    @staticmethod
    def data_processing() -> SandboxPolicy:
        """
        数据处理策略。

        适用于数据处理和转换任务。
        """
        return SandboxPolicy(
            name="data_processing",
            description="数据处理策略，适用于数据处理和转换任务",
            permissions={
                Permission.FILE_READ,
                Permission.FILE_WRITE,
                Permission.IMPORT_MODULE,
                Permission.MEMORY_INTENSIVE,
                Permission.CPU_INTENSIVE,
            },
            denied_permissions=Permission.network_permissions()
            | {
                Permission.FILE_DELETE,
                Permission.FILE_EXECUTE,
                Permission.SUBPROCESS,
                Permission.NATIVE_CALL,
            },
            resource_limits=ResourceLimit(
                max_cpu_percent=80.0,
                max_memory_mb=2048,
                max_execution_time_seconds=600.0,
                max_file_size_mb=500,
            ),
            allowed_modules=[
                "json",
                "re",
                "datetime",
                "math",
                "collections",
                "itertools",
                "functools",
                "typing",
                "dataclasses",
                "pathlib",
                "pandas",
                "numpy",
                "csv",
                "io",
            ],
            is_default=False,
            priority=55,
        )

    @staticmethod
    def all() -> list[SandboxPolicy]:
        """
        获取所有预设策略。

        Returns:
            预设策略列表
        """
        return [
            PresetPolicies.strict(),
            PresetPolicies.moderate(),
            PresetPolicies.permissive(),
            PresetPolicies.readonly(),
            PresetPolicies.network_restricted(),
            PresetPolicies.data_processing(),
        ]

    @staticmethod
    def get(name: str) -> SandboxPolicy | None:
        """
        按名称获取预设策略。

        Args:
            name: 策略名称

        Returns:
            策略实例，如果不存在返回 None
        """
        policies = {
            "strict": PresetPolicies.strict,
            "moderate": PresetPolicies.moderate,
            "permissive": PresetPolicies.permissive,
            "readonly": PresetPolicies.readonly,
            "network_restricted": PresetPolicies.network_restricted,
            "data_processing": PresetPolicies.data_processing,
        }

        factory = policies.get(name.lower())
        return factory() if factory else None


class PolicyValidator:
    """
    策略验证器。

    提供策略验证的实用方法。
    """

    @staticmethod
    def validate_permission_conflicts(policy: SandboxPolicy) -> list[str]:
        """
        验证权限冲突。

        Args:
            policy: 要验证的策略

        Returns:
            冲突描述列表
        """
        conflicts = []

        # 检查授予和拒绝的权限是否有交集
        overlap = policy.permissions & policy.denied_permissions
        if overlap:
            conflicts.append(f"Permissions both granted and denied: {overlap}")

        return conflicts

    @staticmethod
    def validate_resource_limits(policy: SandboxPolicy) -> list[str]:
        """
        验证资源限制。

        Args:
            policy: 要验证的策略

        Returns:
            问题列表
        """
        issues = []
        limits = policy.resource_limits

        if limits.max_cpu_percent <= 0 or limits.max_cpu_percent > 100:
            issues.append(f"Invalid CPU limit: {limits.max_cpu_percent}%")

        if limits.max_memory_mb <= 0:
            issues.append(f"Invalid memory limit: {limits.max_memory_mb}MB")

        if limits.max_execution_time_seconds <= 0:
            issues.append(f"Invalid time limit: {limits.max_execution_time_seconds}s")

        return issues

    @staticmethod
    def validate_path_rules(policy: SandboxPolicy) -> list[str]:
        """
        验证路径规则。

        Args:
            policy: 要验证的策略

        Returns:
            问题列表
        """
        issues = []

        # 检查路径是否同时出现在允许和拒绝列表中
        for allowed in policy.allowed_paths:
            for denied in policy.denied_paths:
                if allowed.startswith(denied) or denied.startswith(allowed):
                    issues.append(f"Path conflict: '{allowed}' and '{denied}' overlap")

        return issues

    @staticmethod
    def validate_module_rules(policy: SandboxPolicy) -> list[str]:
        """
        验证模块规则。

        Args:
            policy: 要验证的策略

        Returns:
            问题列表
        """
        issues = []

        # 检查模块是否同时出现在允许和拒绝列表中
        for allowed in policy.allowed_modules:
            for denied in policy.denied_modules:
                if allowed == denied or allowed.startswith(f"{denied}."):
                    issues.append(f"Module conflict: '{allowed}' is both allowed and denied")

        return issues

    @staticmethod
    def full_validation(policy: SandboxPolicy) -> dict[str, list[str]]:
        """
        执行完整验证。

        Args:
            policy: 要验证的策略

        Returns:
            各类问题的字典
        """
        return {
            "permission_conflicts": PolicyValidator.validate_permission_conflicts(policy),
            "resource_limit_issues": PolicyValidator.validate_resource_limits(policy),
            "path_rule_issues": PolicyValidator.validate_path_rules(policy),
            "module_rule_issues": PolicyValidator.validate_module_rules(policy),
        }

    @staticmethod
    def is_valid(policy: SandboxPolicy) -> bool:
        """
        检查策略是否有效。

        Args:
            policy: 要验证的策略

        Returns:
            如果有效返回 True
        """
        results = PolicyValidator.full_validation(policy)
        return all(len(issues) == 0 for issues in results.values())
