"""
DATA-AI 企业级 — 增强 RBAC (Role-Based Access Control) + ABAC 条件策略

企业痛点:
- 简单的 role: admin / user 不够
- 需要细粒度: 谁能在工作时间/不在工作时间改 Agent?
- 资源所有权: 谁能改自己创建的 vs 别人创建的?
- 角色继承: editor 继承 viewer 权限
- ABAC 条件: action=create 只在 IP 段 10.0.0.0/8 允许
- 委托: 临时授权 (1 小时内代审批)
- 审计: 每次鉴权决策都要记录

设计:
- Permission: (resource, action) 对 — 例如 ("agent", "delete")
- Role: 一组 Permission + parent roles (继承)
- Policy: 包含条件的细粒度规则 (ABAC)
- Assignment: user × role × tenant (多租户范围)
- RBACEngine: 鉴权中心,支持 require()/require_any()/enforce()
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

# 资源类型 × 动作 → 构成一个权限点
# resource: agent | memory | rag | skill | tool | team | sandbox | mcp | billing | audit | settings | quota
# action:   create | read | update | delete | run | share | export | * (wildcard)

Action = str  # "create" | "read" | "update" | "delete" | "run" | "share" | "export" | "*"
Resource = str  # "agent" | "memory" | "rag" | ... | "*"


@dataclass
class Permission:
    """(resource, action) 权限点 — 支持通配符"""

    resource: Resource
    action: Action
    effect: Literal["allow", "deny"] = "allow"
    description: str = ""

    def matches(self, resource: Resource, action: Action) -> bool:
        """检查是否覆盖给定的 (resource, action)"""
        r_ok = self.resource == "*" or self.resource == resource
        a_ok = self.action == "*" or self.action == action
        return r_ok and a_ok

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Permission:
        return cls(**d)


@dataclass
class Role:
    """角色 — 一组 Permission,可继承父角色"""

    id: str = field(default_factory=lambda: f"role-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    permissions: list[Permission] = field(default_factory=list)
    parent_roles: list[str] = field(default_factory=list)  # 父角色 ID
    tenant_id: str = ""  # 租户范围,空 = 全局
    is_system: bool = False  # 系统内置不可删
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Role:
        return cls(**d)

    def expand_permissions(self, role_lookup: Callable[[str], Role | None]) -> list[Permission]:
        """递归展开所有父角色权限"""
        all_p = list(self.permissions)
        for pid in self.parent_roles:
            parent = role_lookup(pid)
            if parent:
                all_p.extend(parent.expand_permissions(role_lookup))
        # 去重
        seen = set()
        out = []
        for p in all_p:
            key = (p.resource, p.action, p.effect)
            if key not in seen:
                seen.add(key)
                out.append(p)
        return out


@dataclass
class Policy:
    """ABAC 条件策略 — 在 RBAC 基础上叠加条件判断

    条件字段 (env 指请求上下文):
        env.ip: 客户端 IP
        env.time_of_day: "HH:MM"
        env.day_of_week: "monday" | ...
        env.tenant_id: 租户
        env.user_id: 用户
        resource.owner: 资源所有者
        resource.tags.foo: 资源 tag
    """

    id: str = field(default_factory=lambda: f"pol-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    # 当这些条件全部满足 → 决策
    conditions: list[dict[str, Any]] = field(default_factory=list)  # [{field, op, value}]
    effect: Literal["allow", "deny"] = "allow"
    priority: int = 100  # 数字越小越先匹配
    tenant_id: str = ""
    enabled: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Policy:
        return cls(**d)


@dataclass
class Assignment:
    """用户 → 角色 绑定 (多租户)"""

    id: str = field(default_factory=lambda: f"asg-{uuid.uuid4().hex[:8]}")
    user_id: str = ""
    role_id: str = ""
    tenant_id: str = ""  # 该角色授予的租户范围
    granted_by: str = ""
    granted_at: float = field(default_factory=time.time)
    expires_at: float = 0.0  # 0 = 永不过期
    delegation_from: str = ""  # 如果是临时委托,记录委托来源

    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Assignment:
        return cls(**d)


@dataclass
class Decision:
    """鉴权决策结果"""

    allowed: bool
    reason: str
    matched_role: str = ""
    matched_policy: str = ""
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------- ABAC 条件求值 ----------


def _get_nested(obj: dict[str, Any], path: str) -> Any:
    """支持 a.b.c 嵌套取值"""
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a is not None and b is not None and a > b,
    "<": lambda a, b: a is not None and b is not None and a < b,
    ">=": lambda a, b: a is not None and b is not None and a >= b,
    "<=": lambda a, b: a is not None and b is not None and a <= b,
    "in": lambda a, b: a in (b if isinstance(b, list | tuple) else [b]),
    "not_in": lambda a, b: a not in (b if isinstance(b, list | tuple) else [b]),
    "contains": lambda a, b: b in (a if isinstance(a, str | list) else str(a)),
    "matches": lambda a, b: bool(re.search(str(b), str(a or ""))),
    "cidr_match": lambda a, b: _cidr_match(str(a or ""), str(b)),
}


def _cidr_match(ip: str, cidr: str) -> bool:
    """检查 IP 是否在 CIDR 段内 (仅支持 IPv4 简化版)"""
    try:
        import ipaddress

        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
    except Exception:
        return False


def evaluate_condition(field_path: str, op: str, expected: Any, env: dict[str, Any], resource: dict[str, Any]) -> bool:
    """求值单条 ABAC 条件"""
    # 路径以 env.* / resource.* 开头
    if field_path.startswith("env."):
        value = _get_nested(env, field_path[4:])
    elif field_path.startswith("resource."):
        value = _get_nested(resource, field_path[9:])
    else:
        # 默认从 env 取
        value = _get_nested(env, field_path)

    fn = _OPS.get(op)
    if not fn:
        return False
    return fn(value, expected)


# ============================================================================
# 引擎
# ============================================================================


class RBACEngine:
    """RBAC + ABAC 鉴权引擎"""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._roles: dict[str, Role] = {}
        self._policies: dict[str, Policy] = {}
        self._assignments: list[Assignment] = []
        self._decisions_log: list[Decision] = []  # 最近 1000 条
        self._persist_path = persist_path
        self._bootstrap_system_roles()
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _bootstrap_system_roles(self) -> None:
        """初始化系统内置角色"""
        for name, perms in [
            ("super-admin", [Permission("*", "*", "allow", "超级管理员")]),
            (
                "admin",
                [
                    Permission("agent", "*"),
                    Permission("memory", "*"),
                    Permission("rag", "*"),
                    Permission("skill", "*"),
                    Permission("tool", "*"),
                    Permission("team", "*"),
                    Permission("sandbox", "*"),
                    Permission("mcp", "*"),
                    Permission("quota", "read"),
                    Permission("audit", "read"),
                ],
            ),
            (
                "developer",
                [
                    Permission("agent", "create"),
                    Permission("agent", "read"),
                    Permission("agent", "update"),
                    Permission("agent", "run"),
                    Permission("memory", "*"),
                    Permission("rag", "read"),
                    Permission("rag", "create"),
                    Permission("skill", "*"),
                    Permission("tool", "read"),
                    Permission("tool", "run"),
                ],
            ),
            (
                "viewer",
                [
                    Permission("agent", "read"),
                    Permission("memory", "read"),
                    Permission("rag", "read"),
                    Permission("skill", "read"),
                    Permission("tool", "read"),
                    Permission("team", "read"),
                ],
            ),
            (
                "billing-admin",
                [
                    Permission("billing", "*"),
                    Permission("quota", "*"),
                    Permission("audit", "read"),
                ],
            ),
            (
                "auditor",
                [
                    Permission("audit", "read"),
                    Permission("quota", "read"),
                    Permission("billing", "read"),
                ],
            ),
        ]:
            role = Role(name=name, permissions=perms, is_system=True)
            self._roles[role.id] = role

    # ---------- 角色 CRUD ----------
    def create_role(self, name: str, permissions: list[Permission] | None = None, **kwargs: Any) -> Role:
        with self._lock:
            for r in self._roles.values():
                if r.name == name and r.tenant_id == kwargs.get("tenant_id", ""):
                    raise ValueError(f"role already exists: {name}")
            r = Role(name=name, permissions=permissions or [], **kwargs)
            self._roles[r.id] = r
            self._write_role(r)
            return r

    def get_role(self, role_id: str) -> Role | None:
        return self._roles.get(role_id)

    def get_role_by_name(self, name: str, tenant_id: str = "") -> Role | None:
        for r in self._roles.values():
            if r.name == name and r.tenant_id == tenant_id:
                return r
        return None

    def list_roles(self, tenant_id: str | None = None, include_system: bool = True) -> list[Role]:
        with self._lock:
            out = list(self._roles.values())
            if tenant_id is not None:
                out = [r for r in out if r.tenant_id == tenant_id or r.tenant_id == ""]
            if not include_system:
                out = [r for r in out if not r.is_system]
            return out

    def update_role(self, role_id: str, **kwargs: Any) -> Role | None:
        with self._lock:
            r = self._roles.get(role_id)
            if not r:
                return None
            if r.is_system and "name" in kwargs:
                raise PermissionError("cannot rename system role")
            for k, v in kwargs.items():
                if hasattr(r, k):
                    setattr(r, k, v)
            self._write_role(r)
            return r

    def delete_role(self, role_id: str) -> bool:
        with self._lock:
            r = self._roles.pop(role_id, None)
            if not r:
                return False
            if r.is_system:
                return False
            # 级联:删除 assignment
            self._assignments = [a for a in self._assignments if a.role_id != role_id]
            return True

    # ---------- 策略 CRUD ----------
    def create_policy(
        self, name: str, conditions: list[dict[str, Any]], effect: str = "allow", **kwargs: Any
    ) -> Policy:
        with self._lock:
            p = Policy(name=name, conditions=conditions, effect=effect, **kwargs)
            self._policies[p.id] = p
            return p

    def list_policies(self, tenant_id: str = "") -> list[Policy]:
        with self._lock:
            return [p for p in self._policies.values() if p.tenant_id == tenant_id or p.tenant_id == ""]

    def delete_policy(self, policy_id: str) -> bool:
        with self._lock:
            return self._policies.pop(policy_id, None) is not None

    # ---------- 分配 ----------
    def assign(
        self,
        user_id: str,
        role_id: str,
        tenant_id: str = "",
        granted_by: str = "",
        expires_at: float = 0.0,
        delegation_from: str = "",
    ) -> Assignment:
        with self._lock:
            # 去重: 同 (user, role, tenant)
            for a in self._assignments:
                if a.user_id == user_id and a.role_id == role_id and a.tenant_id == tenant_id and not a.is_expired():
                    return a
            a = Assignment(
                user_id=user_id,
                role_id=role_id,
                tenant_id=tenant_id,
                granted_by=granted_by,
                expires_at=expires_at,
                delegation_from=delegation_from,
            )
            self._assignments.append(a)
            return a

    def revoke(self, user_id: str, role_id: str, tenant_id: str = "") -> bool:
        with self._lock:
            before = len(self._assignments)
            self._assignments = [
                a
                for a in self._assignments
                if not (a.user_id == user_id and a.role_id == role_id and a.tenant_id == tenant_id)
            ]
            return len(self._assignments) < before

    def list_assignments(self, user_id: str = "", tenant_id: str = "") -> list[Assignment]:
        with self._lock:
            out = list(self._assignments)
            if user_id:
                out = [a for a in out if a.user_id == user_id]
            if tenant_id:
                out = [a for a in out if a.tenant_id == tenant_id]
            return out

    def user_roles(self, user_id: str, tenant_id: str = "") -> list[Role]:
        """获取用户在指定租户的所有有效角色 (含跨租户全局角色)"""
        with self._lock:
            result: list[Role] = []
            for a in self._assignments:
                if a.user_id != user_id:
                    continue
                if a.is_expired():
                    continue
                if tenant_id and a.tenant_id and a.tenant_id != tenant_id:
                    continue  # 租户不匹配
                r = self._roles.get(a.role_id)
                if r:
                    result.append(r)
            return result

    # ---------- 鉴权 ----------
    def check(
        self,
        user_id: str,
        resource: Resource,
        action: Action,
        tenant_id: str = "",
        env: dict[str, Any] | None = None,
        resource_ctx: dict[str, Any] | None = None,
    ) -> Decision:
        """核心鉴权检查

        流程:
        1. 收集用户所有有效角色 → 展开所有 permissions
        2. 检查 deny 优先 (显式拒绝)
        3. 检查 allow (任一 allow 命中)
        4. 叠加 ABAC policy (按 priority 升序)
        """
        env = env or {}
        resource_ctx = resource_ctx or {}
        with self._lock:
            roles = self.user_roles(user_id, tenant_id)
            if not roles:
                d = Decision(allowed=False, reason="no roles assigned", evaluated_at=time.time())
                self._log_decision(d)
                return d

            # 1) 展开所有 permissions
            all_perms: list[Permission] = []
            for r in roles:
                all_perms.extend(r.expand_permissions(self.get_role))

            # 2) 命中检查
            has_allow = False
            matched_role_name = ""
            for p in all_perms:
                if p.effect == "deny" and p.matches(resource, action):
                    d = Decision(
                        allowed=False,
                        reason=f"denied by permission {p.resource}.{p.action}",
                        matched_role=",".join(r.name for r in roles),
                    )
                    self._log_decision(d)
                    return d
                if p.effect == "allow" and p.matches(resource, action):
                    has_allow = True
                    matched_role_name = r.name  # type: ignore[possibly-undefined]

            if not has_allow:
                d = Decision(
                    allowed=False,
                    reason=f"no allow permission for {resource}.{action}",
                    matched_role=",".join(r.name for r in roles),
                )
                self._log_decision(d)
                return d

            # 3) ABAC 策略叠加 (按 priority)
            sorted_policies = sorted(
                [p for p in self._policies.values() if p.enabled and (p.tenant_id == "" or p.tenant_id == tenant_id)],
                key=lambda p: p.priority,
            )
            env_full = {**env, "user_id": user_id, "tenant_id": tenant_id}
            for pol in sorted_policies:
                all_ok = True
                for cond in pol.conditions:
                    field_path = cond.get("field", "")
                    op = cond.get("op", "==")
                    expected = cond.get("value")
                    if not evaluate_condition(field_path, op, expected, env_full, resource_ctx):
                        all_ok = False
                        break
                if all_ok:
                    d = Decision(
                        allowed=(pol.effect == "allow"),
                        reason=f"policy {pol.name} matched ({pol.effect})",
                        matched_role=matched_role_name,
                        matched_policy=pol.name,
                    )
                    self._log_decision(d)
                    return d

            # 4) 默认通过 (RBAC 命中 + 无 deny policy)
            d = Decision(allowed=True, reason="rbac allow", matched_role=matched_role_name)
            self._log_decision(d)
            return d

    def enforce(
        self,
        user_id: str,
        resource: Resource,
        action: Action,
        tenant_id: str = "",
        env: dict[str, Any] | None = None,
        resource_ctx: dict[str, Any] | None = None,
    ) -> None:
        """检查不通过抛 PermissionError"""
        d = self.check(user_id, resource, action, tenant_id, env, resource_ctx)
        if not d.allowed:
            raise PermissionError(f"rbac denied: {d.reason}")

    def require_any(self, user_id: str, pairs: list[tuple[Resource, Action]], tenant_id: str = "") -> bool:
        """任一 (resource, action) 通过即返回 True"""
        return any(self.check(user_id, r, a, tenant_id).allowed for r, a in pairs)

    def require_all(self, user_id: str, pairs: list[tuple[Resource, Action]], tenant_id: str = "") -> bool:
        """全部 (resource, action) 通过才返回 True"""
        return all(self.check(user_id, r, a, tenant_id).allowed for r, a in pairs)

    # ---------- 委托 ----------
    def delegate(
        self, from_user: str, to_user: str, role_id: str, tenant_id: str = "", expires_at: float = 0.0
    ) -> Assignment:
        """临时委托角色给另一用户"""
        return self.assign(
            to_user, role_id, tenant_id, granted_by=from_user, expires_at=expires_at, delegation_from=from_user
        )

    # ---------- 决策日志 ----------
    def _log_decision(self, d: Decision) -> None:
        with self._lock:
            self._decisions_log.append(d)
            if len(self._decisions_log) > 1000:
                self._decisions_log = self._decisions_log[-1000:]

    def recent_decisions(self, limit: int = 50) -> list[Decision]:
        return list(self._decisions_log[-limit:])

    # ---------- 持久化 ----------
    def _write_role(self, r: Role) -> None:
        if not self._persist_path:
            return
        try:
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"type": "role", "data": r.to_dict()}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            with self._persist_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") == "role":
                        r = Role.from_dict(rec["data"])
                        if not r.is_system:
                            self._roles[r.id] = r
        except Exception:
            pass


# ============================================================================
# 全局单例
# ============================================================================

_GLOBAL_ENGINE: RBACEngine | None = None
_GLOBAL_LOCK = threading.Lock()


def get_rbac_engine(persist_path: Path | None = None) -> RBACEngine:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        if _GLOBAL_ENGINE is None:
            _GLOBAL_ENGINE = RBACEngine(persist_path=persist_path)
        return _GLOBAL_ENGINE


def reset_rbac_engine() -> None:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        _GLOBAL_ENGINE = None
