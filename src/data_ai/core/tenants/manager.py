"""多租户模块 — 资源隔离与归属追踪

企业级核心痛点:
- 同一 DATA-AI 实例服务多个客户 (子品牌 / 部门 / 客户)
- 数据必须硬隔离:Agent/Memory/RAG/Skill 归属不同租户
- 计费: 每个租户单独计算 token / 请求 / 成本
- 合规: GDPR / 行业法规要求 data residency

设计:
- Tenant: 租户对象 (id/name/plan/region/status/limits)
- TenantMember: 用户在租户里的角色 (owner/admin/member/viewer)
- TenantContext: 当前请求的租户上下文 (middleware 注入)
- TenantStore: 内存 + JSONL 持久化
- enforce_tenant(): 检查资源是否归属当前租户,防止跨租户访问
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

PlanTier = Literal["free", "starter", "pro", "enterprise"]
TenantStatus = Literal["active", "suspended", "archived"]
MemberRole = Literal["owner", "admin", "member", "viewer"]


@dataclass
class Tenant:
    """租户 — 企业/部门/子品牌"""

    id: str = field(default_factory=lambda: f"tnt-{uuid.uuid4().hex[:12]}")
    name: str = ""
    slug: str = ""  # URL 安全标识
    plan: PlanTier = "free"
    status: TenantStatus = "active"
    region: str = "default"  # 数据驻留区域
    contact_email: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=lambda: {
        "max_users": 5,
        "max_agents": 10,
        "max_tokens_per_day": 100_000,
        "max_storage_mb": 1024,
    })
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Tenant:
        return cls(**d)

    def is_active(self) -> bool:
        return self.status == "active"

    def check_limit(self, key: str, current_value: int) -> tuple[bool, str]:
        """检查是否超过限制。返回 (ok, reason)"""
        max_val = self.limits.get(key)
        if max_val is None:
            return True, ""
        if current_value > max_val:
            return False, f"tenant limit exceeded: {key}={current_value} > {max_val}"
        return True, ""


@dataclass
class TenantMember:
    """租户成员 — 用户在租户内的角色"""

    tenant_id: str = ""
    user_id: str = ""  # 外部 user id (sso_id / email)
    role: MemberRole = "member"
    invited_by: str = ""
    joined_at: float = field(default_factory=time.time)
    last_active_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TenantMember:
        return cls(**d)


class TenantStore:
    """租户存储 — 内存索引 + JSONL 持久化"""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._tenants: dict[str, Tenant] = {}
        self._members: list[TenantMember] = []
        self._persist_path = persist_path
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    # ---------- 租户 CRUD ----------
    def create(self, name: str, slug: str = "", plan: PlanTier = "free", **kwargs: Any) -> Tenant:
        with self._lock:
            if not slug:
                slug = name.lower().replace(" ", "-")[:32]
            # 唯一性
            for t in self._tenants.values():
                if t.slug == slug:
                    raise ValueError(f"tenant slug already exists: {slug}")
            t = Tenant(name=name, slug=slug, plan=plan, **kwargs)
            self._tenants[t.id] = t
            self._write_tenant(t)
            return t

    def get(self, tenant_id: str) -> Tenant | None:
        return self._tenants.get(tenant_id)

    def get_by_slug(self, slug: str) -> Tenant | None:
        for t in self._tenants.values():
            if t.slug == slug:
                return t
        return None

    def list(self, status: TenantStatus | None = None, plan: PlanTier | None = None) -> list[Tenant]:
        with self._lock:
            out = list(self._tenants.values())
            if status:
                out = [t for t in out if t.status == status]
            if plan:
                out = [t for t in out if t.plan == plan]
            return out

    def update(self, tenant_id: str, **kwargs: Any) -> Tenant | None:
        with self._lock:
            t = self._tenants.get(tenant_id)
            if not t:
                return None
            for k, v in kwargs.items():
                if hasattr(t, k):
                    setattr(t, k, v)
            t.updated_at = time.time()
            self._write_tenant(t)
            return t

    def delete(self, tenant_id: str) -> bool:
        with self._lock:
            t = self._tenants.pop(tenant_id, None)
            if not t:
                return False
            # 级联:删除成员
            self._members = [m for m in self._members if m.tenant_id != tenant_id]
            return True

    def suspend(self, tenant_id: str) -> Tenant | None:
        return self.update(tenant_id, status="suspended")

    def activate(self, tenant_id: str) -> Tenant | None:
        return self.update(tenant_id, status="active")

    # ---------- 成员 ----------
    def add_member(self, tenant_id: str, user_id: str, role: MemberRole = "member", invited_by: str = "") -> TenantMember:
        with self._lock:
            # 重复检查
            for m in self._members:
                if m.tenant_id == tenant_id and m.user_id == user_id:
                    # 更新角色
                    m.role = role
                    return m
            m = TenantMember(tenant_id=tenant_id, user_id=user_id, role=role, invited_by=invited_by)
            self._members.append(m)
            return m

    def remove_member(self, tenant_id: str, user_id: str) -> bool:
        with self._lock:
            before = len(self._members)
            self._members = [m for m in self._members if not (m.tenant_id == tenant_id and m.user_id == user_id)]
            return len(self._members) < before

    def list_members(self, tenant_id: str) -> list[TenantMember]:
        return [m for m in self._members if m.tenant_id == tenant_id]

    def get_membership(self, tenant_id: str, user_id: str) -> TenantMember | None:
        for m in self._members:
            if m.tenant_id == tenant_id and m.user_id == user_id:
                return m
        return None

    def list_user_tenants(self, user_id: str) -> list[Tenant]:
        """列出用户所属的所有租户"""
        tenant_ids = {m.tenant_id for m in self._members if m.user_id == user_id}
        return [t for t in self._tenants.values() if t.id in tenant_ids]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            by_plan: dict[str, int] = {}
            by_status: dict[str, int] = {}
            for t in self._tenants.values():
                by_plan[t.plan] = by_plan.get(t.plan, 0) + 1
                by_status[t.status] = by_status.get(t.status, 0) + 1
            return {
                "total_tenants": len(self._tenants),
                "total_members": len(self._members),
                "by_plan": by_plan,
                "by_status": by_status,
            }

    # ---------- 持久化 ----------
    def _write_tenant(self, t: Tenant) -> None:
        if not self._persist_path:
            return
        try:
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"type": "tenant", "data": t.to_dict()}, ensure_ascii=False) + "\n")
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
                    if rec.get("type") == "tenant":
                        t = Tenant.from_dict(rec["data"])
                        self._tenants[t.id] = t
                    elif rec.get("type") == "member":
                        m = TenantMember.from_dict(rec["data"])
                        self._members.append(m)
        except Exception:
            pass


# ============================================================================
# 全局单例 + 上下文
# ============================================================================

_GLOBAL_STORE: TenantStore | None = None
_GLOBAL_LOCK = threading.Lock()


def get_tenant_store(persist_path: Path | None = None) -> TenantStore:
    global _GLOBAL_STORE
    with _GLOBAL_LOCK:
        if _GLOBAL_STORE is None:
            _GLOBAL_STORE = TenantStore(persist_path=persist_path)
        return _GLOBAL_STORE


def reset_tenant_store() -> None:
    global _GLOBAL_STORE
    with _GLOBAL_LOCK:
        _GLOBAL_STORE = None


# ---------- 上下文 (FastAPI request.state.tenant) ----------

@dataclass
class TenantContext:
    """当前请求的租户上下文"""

    tenant_id: str = ""
    user_id: str = ""
    role: MemberRole = "viewer"
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    started_at: float = field(default_factory=time.time)

    def is_authenticated(self) -> bool:
        return bool(self.tenant_id and self.user_id)

    def has_role(self, *roles: MemberRole) -> bool:
        return self.role in roles


# ---------- 跨租户访问防护 ----------

def enforce_tenant(resource_tenant_id: str, ctx: TenantContext) -> None:
    """强制资源归属当前租户。跨租户访问抛 PermissionError。"""
    if not ctx.is_authenticated():
        raise PermissionError("no tenant context")
    if resource_tenant_id and resource_tenant_id != ctx.tenant_id:
        from data_ai.utils.logging import get_logger
        get_logger("tenants").warning(
            f"cross-tenant access blocked: ctx={ctx.tenant_id} resource={resource_tenant_id} "
            f"user={ctx.user_id}"
        )
        raise PermissionError(
            f"cross-tenant access denied: resource belongs to {resource_tenant_id}, "
            f"current tenant is {ctx.tenant_id}"
        )


def resolve_tenant_from_request(
    headers: dict[str, str],
    query_params: dict[str, str] | None = None,
    default_tenant_id: str = "",
) -> str:
    """从请求头/参数中解析租户 ID"""
    # 优先级: header > query > default
    tid = headers.get("X-Tenant-ID") or headers.get("X-Tenant-Id")
    if tid:
        return tid
    if query_params:
        tid = query_params.get("tenant_id")
        if tid:
            return tid
    return default_tenant_id


# ---------- 常用工具 ----------

def now_iso() -> str:
    return datetime.fromtimestamp(time.time()).isoformat()
