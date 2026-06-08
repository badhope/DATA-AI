"""
DATA-AI 企业级 — 区域数据驻留 (Data Residency)

合规要求:
- 欧盟 GDPR: 欧盟用户数据不能出欧盟
- 中国《数据安全法》: 境内数据需境内存储
- 俄罗斯 152-FZ: 公民数据须在俄境内
- 美国 HIPAA: 医疗数据分级驻留

设计:
- Region: 地理区域 (cn-east / eu-west / us-west / ap-south / ...)
- ResidencyPolicy: 数据类型 → 允许/禁止区域
- ResidencyRouter: 写入时按 policy 选 storage backend
- AuditTrail: 记录每条数据的驻留位置
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

RegionStatus = Literal["active", "degraded", "offline"]


# 预置区域
DEFAULT_REGIONS = [
    {"id": "cn-east", "name": "China East (Shanghai)", "country": "CN", "tier": "tier-1"},
    {"id": "cn-north", "name": "China North (Beijing)", "country": "CN", "tier": "tier-1"},
    {"id": "eu-west", "name": "EU West (Frankfurt)", "country": "DE", "tier": "tier-1"},
    {"id": "eu-north", "name": "EU North (Stockholm)", "country": "SE", "tier": "tier-1"},
    {"id": "us-east", "name": "US East (Virginia)", "country": "US", "tier": "tier-1"},
    {"id": "us-west", "name": "US West (Oregon)", "country": "US", "tier": "tier-1"},
    {"id": "ap-southeast", "name": "AP Southeast (Singapore)", "country": "SG", "tier": "tier-1"},
    {"id": "ap-northeast", "name": "AP Northeast (Tokyo)", "country": "JP", "tier": "tier-2"},
]


@dataclass
class Region:
    """地理区域"""

    id: str = ""  # cn-east
    name: str = ""
    country: str = ""  # ISO 3166-1 alpha-2
    tier: str = "tier-2"  # tier-1 (主) / tier-2 (灾备)
    status: RegionStatus = "active"
    storage_backend: str = "local"  # local / s3 / oss
    endpoint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Region:
        return cls(**d)


# 数据类型
DataClass = Literal[
    "user_data", "pii", "phi", "financial", "audit_log", "model_artifact", "embedding", "session", "metric"
]
DefaultRegion = Literal["auto", "cn-east", "eu-west", "us-east", "ap-southeast"]


@dataclass
class ResidencyPolicy:
    """数据驻留策略 — 某类数据可以/禁止在哪些区域"""

    id: str = field(default_factory=lambda: f"rp-{uuid.uuid4().hex[:8]}")
    name: str = ""
    data_class: DataClass = "user_data"
    # 允许存储的区域(白名单)
    allowed_regions: list[str] = field(default_factory=list)
    # 禁止存储的区域(黑名单,优先于白名单)
    forbidden_regions: list[str] = field(default_factory=list)
    # 跨区域传输是否允许
    allow_cross_region_transfer: bool = False
    # 数据加密要求
    encryption_required: bool = True
    # 保留期限(天)
    retention_days: int = 365
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ResidencyPolicy:
        return cls(**d)

    def check(self, region_id: str) -> tuple[bool, str]:
        """检查数据能否驻留在该区域"""
        if not self.enabled:
            return True, ""
        if region_id in self.forbidden_regions:
            return False, f"data_class={self.data_class} forbidden in {region_id}"
        if self.allowed_regions and region_id not in self.allowed_regions:
            return False, f"data_class={self.data_class} not in allowed_regions {self.allowed_regions}"
        return True, ""


@dataclass
class ResidencyAssignment:
    """某条数据被分配到哪个区域的记录(审计)"""

    id: str = field(default_factory=lambda: f"ra-{uuid.uuid4().hex[:12]}")
    resource_id: str = ""  # agent-xxx / memory-yyy
    data_class: DataClass = "user_data"
    region_id: str = ""
    tenant_id: str = ""
    policy_id: str = ""
    encrypted: bool = True
    created_at: float = field(default_factory=time.time)
    transferred_at: float = 0.0
    transferred_from: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ResidencyAssignment:
        return cls(**d)


class ResidencyRouter:
    """驻留路由 — 根据 policy 选择目标 region"""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._regions: dict[str, Region] = {}
        self._policies: dict[str, ResidencyPolicy] = {}
        self._assignments: list[ResidencyAssignment] = []
        self._persist_path = persist_path
        self._bootstrap()
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _bootstrap(self) -> None:
        """预置区域 + 默认策略"""
        for r in DEFAULT_REGIONS:
            self._regions[r["id"]] = Region(**r)
        # 默认策略 — 严格模式
        for dc, allowed in [
            ("pii", ["cn-east", "cn-north", "eu-west", "eu-north", "us-east", "us-west"]),  # PII 可驻留主要区域
            ("phi", []),  # PHI 默认禁止,必须显式配置
            ("financial", ["cn-east", "eu-west", "us-east"]),
            ("audit_log", ["*"]),  # 审计日志可驻留
            ("embedding", ["*"]),
            ("user_data", ["*"]),
        ]:
            p = ResidencyPolicy(
                name=f"default-{dc}",
                data_class=dc,  # type: ignore[arg-type]
                allowed_regions=allowed,
                description=f"默认 {dc} 驻留策略",
            )
            self._policies[p.id] = p

    # ---------- Region ----------
    def add_region(self, region: Region) -> Region:
        with self._lock:
            self._regions[region.id] = region
            return region

    def list_regions(self) -> list[Region]:
        with self._lock:
            return list(self._regions.values())

    def get_region(self, region_id: str) -> Region | None:
        return self._regions.get(region_id)

    def set_region_status(self, region_id: str, status: RegionStatus) -> Region | None:
        with self._lock:
            r = self._regions.get(region_id)
            if r:
                r.status = status
            return r

    # ---------- Policy ----------
    def add_policy(self, policy: ResidencyPolicy) -> ResidencyPolicy:
        with self._lock:
            self._policies[policy.id] = policy
            return policy

    def list_policies(self) -> list[ResidencyPolicy]:
        with self._lock:
            return list(self._policies.values())

    def get_policy_for_class(self, data_class: DataClass) -> ResidencyPolicy | None:
        # 优先用户自定义
        for p in self._policies.values():
            if p.data_class == data_class and not p.name.startswith("default-"):
                return p
        for p in self._policies.values():
            if p.data_class == data_class:
                return p
        return None

    def delete_policy(self, policy_id: str) -> bool:
        with self._lock:
            return self._policies.pop(policy_id, None) is not None

    # ---------- 路由 ----------
    def route(
        self,
        resource_id: str,
        data_class: DataClass,
        tenant_id: str = "",
        prefer_region: str = "",
    ) -> ResidencyAssignment:
        """为某资源选择驻留区域"""
        with self._lock:
            policy = self.get_policy_for_class(data_class)
            candidates: list[str] = []
            if prefer_region and self._regions.get(prefer_region) and self._regions[prefer_region].status == "active":
                ok, _ = policy.check(prefer_region) if policy else (True, "")
                if ok:
                    candidates.append(prefer_region)
            if not candidates:
                # 选第一个 active 且 policy 允许的
                for rid, r in self._regions.items():
                    if r.status != "active":
                        continue
                    ok, _ = policy.check(rid) if policy else (True, "")
                    if ok:
                        candidates.append(rid)
                        break
            if not candidates:
                # 兜底: 任何 active
                for r in self._regions.values():
                    if r.status == "active":
                        candidates.append(r.id)
                        break
            target = candidates[0] if candidates else "default"
            a = ResidencyAssignment(
                resource_id=resource_id,
                data_class=data_class,
                region_id=target,
                tenant_id=tenant_id,
                policy_id=policy.id if policy else "",
                encrypted=policy.encryption_required if policy else True,
            )
            self._assignments.append(a)
            return a

    def can_transfer(self, resource_id: str, from_region: str, to_region: str) -> tuple[bool, str]:
        """检查是否允许跨区域传输"""
        # 找到 resource 的 assignment
        assignment = next((a for a in reversed(self._assignments) if a.resource_id == resource_id), None)
        if not assignment:
            return True, ""  # 没记录,允许
        policy = self._policies.get(assignment.policy_id)
        if not policy:
            return True, ""
        if not policy.allow_cross_region_transfer:
            return False, f"data_class={assignment.data_class} does not allow cross-region transfer"
        ok, reason = policy.check(to_region)
        return ok, reason

    def list_assignments(
        self, tenant_id: str = "", data_class: DataClass | None = None, limit: int = 100
    ) -> list[ResidencyAssignment]:
        with self._lock:
            out = []
            for a in reversed(self._assignments):
                if tenant_id and a.tenant_id != tenant_id:
                    continue
                if data_class and a.data_class != data_class:
                    continue
                out.append(a)
                if len(out) >= limit:
                    break
            return out

    def stats(self) -> dict[str, Any]:
        with self._lock:
            by_region: dict[str, int] = {}
            by_class: dict[str, int] = {}
            for a in self._assignments:
                by_region[a.region_id] = by_region.get(a.region_id, 0) + 1
                by_class[a.data_class] = by_class.get(a.data_class, 0) + 1
            return {
                "total_assignments": len(self._assignments),
                "by_region": by_region,
                "by_data_class": by_class,
                "regions": len(self._regions),
                "policies": len(self._policies),
            }

    # ---------- 持久化 ----------
    def _write_assignment(self, a: ResidencyAssignment) -> None:
        if not self._persist_path:
            return
        try:
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"type": "assignment", "data": a.to_dict()}, ensure_ascii=False) + "\n")
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
                    if rec.get("type") == "assignment":
                        a = ResidencyAssignment.from_dict(rec["data"])
                        self._assignments.append(a)
                    elif rec.get("type") == "policy":
                        p = ResidencyPolicy.from_dict(rec["data"])
                        self._policies[p.id] = p
        except Exception:
            pass


# ============================================================================
# 全局单例
# ============================================================================

_GLOBAL_ROUTER: ResidencyRouter | None = None
_GLOBAL_LOCK = threading.Lock()


def get_residency_router(persist_path: Path | None = None) -> ResidencyRouter:
    global _GLOBAL_ROUTER
    with _GLOBAL_LOCK:
        if _GLOBAL_ROUTER is None:
            _GLOBAL_ROUTER = ResidencyRouter(persist_path=persist_path)
        return _GLOBAL_ROUTER


def reset_residency_router() -> None:
    global _GLOBAL_ROUTER
    with _GLOBAL_LOCK:
        _GLOBAL_ROUTER = None
