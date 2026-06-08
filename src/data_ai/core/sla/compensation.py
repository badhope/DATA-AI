"""
DATA-AI 企业级 — SLA 违约赔付 (Credit 计算 + 工单)

企业痛点:
- 99.9% SLA 承诺: 实际 99.5% 怎么办? (自动算赔付)
- 客户问: 上次故障赔我多少? (透明可查)
- 销售: SLA 99.99% 报价 vs 99.9% 差多少? (定价参考)
- 法务: 赔付条款可配置 (服务等级 → 赔付阶梯)
- 财务: 每月自动生成 credit 报表

设计:
- CompensationPolicy: 赔付政策 (按服务等级 / 月费比例)
- BreachEvent: SLA 违约事件 (关联 incident, 自动检测)
- Credit: 赔付金额 (可应用于账单)
- Dispute: 争议工单 (客户申诉 / 复核)
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class BreachSeverity(str, Enum):
    LOW = "low"  # 轻微违约 (5%-10% 偏差)
    MEDIUM = "medium"  # 中度违约 (10%-25%)
    HIGH = "high"  # 严重违约 (25%-50%)
    CRITICAL = "critical"  # 灾难级 (>50%)


class CreditStatus(str, Enum):
    PENDING = "pending"  # 待审核
    APPROVED = "approved"  # 已批准
    APPLIED = "applied"  # 已抵扣账单
    PAID = "paid"  # 已退款
    DISPUTED = "disputed"  # 争议中
    REJECTED = "rejected"  # 拒绝


class DisputeStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    REJECTED = "rejected"


@dataclass
class CompensationTier:
    """赔付阶梯: 实际可用率 → credit 百分比"""

    min_availability_pct: float  # 0-100
    max_availability_pct: float  # 0-100
    credit_pct: float  # 月费百分比 (0-100)
    description: str = ""


@dataclass
class CompensationPolicy:
    """赔付政策"""

    id: str = field(default_factory=lambda: f"cp-{uuid.uuid4().hex[:8]}")
    name: str = ""
    plan_tier: str = "enterprise"  # free / pro / enterprise
    target_availability_pct: float = 99.9
    measurement_window_days: int = 30
    tiers: list[CompensationTier] = field(default_factory=list)
    max_credit_pct: float = 100.0  # 单次事件最高赔付
    monthly_cap_pct: float = 100.0  # 单月累计赔付上限
    auto_apply: bool = True
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def calculate_credit_pct(self, actual_availability_pct: float) -> tuple[float, CompensationTier | None]:
        """根据实际可用率计算赔付百分比"""
        if actual_availability_pct >= self.target_availability_pct:
            return 0.0, None
        for tier in sorted(self.tiers, key=lambda t: t.min_availability_pct, reverse=True):
            if tier.min_availability_pct <= actual_availability_pct < tier.max_availability_pct:
                return min(tier.credit_pct, self.max_credit_pct), tier
        # 默认按"超低"处理: 每低 0.1% 赔 1%
        diff = self.target_availability_pct - actual_availability_pct
        return min(diff * 10, self.max_credit_pct), None


DEFAULT_TIERS = [
    CompensationTier(99.5, 99.9, 10.0, "轻微违约: 赔 10% 月费"),
    CompensationTier(99.0, 99.5, 25.0, "中度违约: 赔 25% 月费"),
    CompensationTier(95.0, 99.0, 50.0, "严重违约: 赔 50% 月费"),
    CompensationTier(0.0, 95.0, 100.0, "灾难级: 赔 100% 月费"),
]


@dataclass
class BreachEvent:
    """SLA 违约事件"""

    id: str = field(default_factory=lambda: f"be-{uuid.uuid4().hex[:8]}")
    policy_id: str = ""
    tenant_id: str = ""
    severity: BreachSeverity = BreachSeverity.LOW
    target_pct: float = 99.9
    actual_pct: float = 0.0
    downtime_sec: float = 0.0
    measurement_start: float = 0.0
    measurement_end: float = 0.0
    related_incident_ids: list[str] = field(default_factory=list)
    affected_components: list[str] = field(default_factory=list)
    detected_at: float = field(default_factory=time.time)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    @property
    def deviation_pct(self) -> float:
        return self.target_pct - self.actual_pct


@dataclass
class Credit:
    """赔付金额"""

    id: str = field(default_factory=lambda: f"cr-{uuid.uuid4().hex[:8]}")
    breach_id: str = ""
    policy_id: str = ""
    tenant_id: str = ""
    status: CreditStatus = CreditStatus.PENDING
    base_amount_usd: float = 0.0  # 月费基准
    credit_pct: float = 0.0  # 赔付百分比
    credit_amount_usd: float = 0.0  # 实际赔付 USD
    currency: str = "USD"
    period_start: float = 0.0
    period_end: float = 0.0
    approved_by: str = ""
    approved_at: float = 0.0
    applied_at: float = 0.0
    paid_at: float = 0.0
    created_at: float = field(default_factory=time.time)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class Dispute:
    """争议工单"""

    id: str = field(default_factory=lambda: f"dp-{uuid.uuid4().hex[:8]}")
    credit_id: str = ""
    tenant_id: str = ""
    status: DisputeStatus = DisputeStatus.OPEN
    raised_by: str = ""
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    resolution: str = ""
    resolved_by: str = ""
    created_at: float = field(default_factory=time.time)
    resolved_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class CompensationEngine:
    """SLA 赔付引擎"""

    def __init__(self, persist_path: str | None = None) -> None:
        self._lock = threading.RLock()
        self._policies: dict[str, CompensationPolicy] = {}
        self._breaches: dict[str, BreachEvent] = {}
        self._credits: dict[str, Credit] = {}
        self._disputes: dict[str, Dispute] = {}
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path:
            self._load()
        # 预置 enterprise 政策
        if not self._policies:
            self.create_policy(
                name="Enterprise 99.9% SLA",
                plan_tier="enterprise",
                target_availability_pct=99.9,
                tiers=DEFAULT_TIERS,
                auto_apply=True,
            )

    # ---- policy ----

    def create_policy(
        self,
        name: str,
        plan_tier: str = "enterprise",
        target_availability_pct: float = 99.9,
        measurement_window_days: int = 30,
        tiers: list[CompensationTier] | None = None,
        max_credit_pct: float = 100.0,
        monthly_cap_pct: float = 100.0,
        auto_apply: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> CompensationPolicy:
        with self._lock:
            p = CompensationPolicy(
                name=name,
                plan_tier=plan_tier,
                target_availability_pct=target_availability_pct,
                measurement_window_days=measurement_window_days,
                tiers=list(tiers or DEFAULT_TIERS),
                max_credit_pct=max_credit_pct,
                monthly_cap_pct=monthly_cap_pct,
                auto_apply=auto_apply,
                metadata=dict(metadata or {}),
            )
            self._policies[p.id] = p
            self._persist()
            return p

    def list_policies(self, plan_tier: str = "") -> list[CompensationPolicy]:
        with self._lock:
            out: list[CompensationPolicy] = []
            for p in self._policies.values():
                if plan_tier and p.plan_tier != plan_tier:
                    continue
                out.append(p)
            return out

    def get_policy(self, policy_id: str) -> CompensationPolicy | None:
        return self._policies.get(policy_id)

    def find_policy_for_plan(self, plan_tier: str) -> CompensationPolicy | None:
        for p in self._policies.values():
            if p.plan_tier == plan_tier:
                return p
        return None

    # ---- breach detection ----

    def detect_breach(
        self,
        policy_id: str,
        tenant_id: str,
        actual_availability_pct: float,
        downtime_sec: float = 0.0,
        measurement_start: float = 0.0,
        measurement_end: float = 0.0,
        related_incident_ids: list[str] | None = None,
        affected_components: list[str] | None = None,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BreachEvent:
        with self._lock:
            policy = self._policies.get(policy_id)
            if not policy:
                raise ValueError(f"policy not found: {policy_id}")
            deviation = policy.target_availability_pct - actual_availability_pct
            if deviation <= 0:
                severity = BreachSeverity.LOW
            elif deviation <= 0.1:
                severity = BreachSeverity.LOW
            elif deviation <= 1.0:
                severity = BreachSeverity.MEDIUM
            elif deviation <= 5.0:
                severity = BreachSeverity.HIGH
            else:
                severity = BreachSeverity.CRITICAL
            breach = BreachEvent(
                policy_id=policy_id,
                tenant_id=tenant_id,
                severity=severity,
                target_pct=policy.target_availability_pct,
                actual_pct=actual_availability_pct,
                downtime_sec=downtime_sec,
                measurement_start=measurement_start,
                measurement_end=measurement_end,
                related_incident_ids=list(related_incident_ids or []),
                affected_components=list(affected_components or []),
                description=description,
                metadata=dict(metadata or {}),
            )
            self._breaches[breach.id] = breach
            self._persist()
            return breach

    def get_breach(self, breach_id: str) -> BreachEvent | None:
        return self._breaches.get(breach_id)

    def list_breaches(
        self, tenant_id: str = "", severity: BreachSeverity | None = None, limit: int = 100
    ) -> list[BreachEvent]:
        with self._lock:
            out: list[BreachEvent] = []
            for b in self._breaches.values():
                if tenant_id and b.tenant_id != tenant_id:
                    continue
                if severity is not None and b.severity != severity:
                    continue
                out.append(b)
            out.sort(key=lambda b: b.detected_at, reverse=True)
            return out[:limit]

    # ---- credit calculation ----

    def calculate_credit(
        self,
        breach_id: str,
        monthly_fee_usd: float,
    ) -> Credit:
        """根据违约事件计算 credit 金额"""
        with self._lock:
            breach = self._breaches.get(breach_id)
            if not breach:
                raise ValueError(f"breach not found: {breach_id}")
            policy = self._policies.get(breach.policy_id)
            if not policy:
                raise ValueError(f"policy not found: {breach.policy_id}")
            credit_pct, _tier = policy.calculate_credit_pct(breach.actual_pct)
            if credit_pct <= 0:
                raise ValueError(
                    f"no credit applicable: actual={breach.actual_pct}%, target={policy.target_availability_pct}%"
                )
            credit_amount = monthly_fee_usd * (credit_pct / 100.0)
            credit = Credit(
                breach_id=breach_id,
                policy_id=breach.policy_id,
                tenant_id=breach.tenant_id,
                status=CreditStatus.PENDING,
                base_amount_usd=monthly_fee_usd,
                credit_pct=credit_pct,
                credit_amount_usd=credit_amount,
                period_start=breach.measurement_start,
                period_end=breach.measurement_end,
                metadata={"severity": breach.severity.value, "deviation_pct": breach.deviation_pct},
            )
            self._credits[credit.id] = credit
            if policy.auto_apply:
                credit.status = CreditStatus.APPROVED
                credit.approved_at = time.time()
                credit.approved_by = "auto"
            self._persist()
            return credit

    def approve_credit(self, credit_id: str, approved_by: str = "") -> Credit | None:
        with self._lock:
            c = self._credits.get(credit_id)
            if not c:
                return None
            c.status = CreditStatus.APPROVED
            c.approved_at = time.time()
            c.approved_by = approved_by
            self._persist()
            return c

    def apply_credit(self, credit_id: str) -> Credit | None:
        with self._lock:
            c = self._credits.get(credit_id)
            if not c:
                return None
            if c.status not in (CreditStatus.APPROVED, CreditStatus.PENDING):
                raise ValueError(f"credit not in applicable state: {c.status.value}")
            c.status = CreditStatus.APPLIED
            c.applied_at = time.time()
            self._persist()
            return c

    def mark_paid(self, credit_id: str) -> Credit | None:
        with self._lock:
            c = self._credits.get(credit_id)
            if not c:
                return None
            c.status = CreditStatus.PAID
            c.paid_at = time.time()
            self._persist()
            return c

    def reject_credit(self, credit_id: str, reason: str = "") -> Credit | None:
        with self._lock:
            c = self._credits.get(credit_id)
            if not c:
                return None
            c.status = CreditStatus.REJECTED
            c.notes = (c.notes + f" | rejected: {reason}").strip(" |")
            self._persist()
            return c

    def get_credit(self, credit_id: str) -> Credit | None:
        return self._credits.get(credit_id)

    def list_credits(
        self,
        tenant_id: str = "",
        status: CreditStatus | None = None,
        limit: int = 100,
    ) -> list[Credit]:
        with self._lock:
            out: list[Credit] = []
            for c in self._credits.values():
                if tenant_id and c.tenant_id != tenant_id:
                    continue
                if status is not None and c.status != status:
                    continue
                out.append(c)
            out.sort(key=lambda c: c.created_at, reverse=True)
            return out[:limit]

    # ---- dispute ----

    def raise_dispute(
        self,
        credit_id: str,
        tenant_id: str,
        raised_by: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Dispute:
        with self._lock:
            credit = self._credits.get(credit_id)
            if not credit:
                raise ValueError(f"credit not found: {credit_id}")
            # credit 转 disputed 状态
            credit.status = CreditStatus.DISPUTED
            d = Dispute(
                credit_id=credit_id,
                tenant_id=tenant_id,
                status=DisputeStatus.OPEN,
                raised_by=raised_by,
                reason=reason,
                evidence=dict(evidence or {}),
                metadata=dict(metadata or {}),
            )
            self._disputes[d.id] = d
            self._persist()
            return d

    def resolve_dispute(
        self,
        dispute_id: str,
        resolution: str,
        resolved_by: str = "",
        uphold_credit: bool = True,
    ) -> Dispute | None:
        with self._lock:
            d = self._disputes.get(dispute_id)
            if not d:
                return None
            d.status = DisputeStatus.RESOLVED if uphold_credit else DisputeStatus.REJECTED
            d.resolution = resolution
            d.resolved_by = resolved_by
            d.resolved_at = time.time()
            # 同步 credit 状态
            credit = self._credits.get(d.credit_id)
            if credit:
                if uphold_credit:
                    credit.status = CreditStatus.APPROVED
                    credit.approved_at = time.time()
                else:
                    credit.status = CreditStatus.REJECTED
            self._persist()
            return d

    def list_disputes(
        self,
        tenant_id: str = "",
        status: DisputeStatus | None = None,
        limit: int = 50,
    ) -> list[Dispute]:
        with self._lock:
            out: list[Dispute] = []
            for d in self._disputes.values():
                if tenant_id and d.tenant_id != tenant_id:
                    continue
                if status is not None and d.status != status:
                    continue
                out.append(d)
            out.sort(key=lambda d: d.created_at, reverse=True)
            return out[:limit]

    # ---- reporting ----

    def tenant_summary(self, tenant_id: str, period_start: float, period_end: float) -> dict[str, Any]:
        """客户视角: 期间内的可用率 + 累计赔付"""
        with self._lock:
            breaches = [
                b
                for b in self._breaches.values()
                if b.tenant_id == tenant_id and period_start <= b.detected_at <= period_end
            ]
            credits = [
                c
                for c in self._credits.values()
                if c.tenant_id == tenant_id and period_start <= c.created_at <= period_end
            ]
            total_credit = sum(c.credit_amount_usd for c in credits)
            applied_credit = sum(
                c.credit_amount_usd
                for c in credits
                if c.status in (CreditStatus.APPROVED, CreditStatus.APPLIED, CreditStatus.PAID)
            )
            # 平均可用率 (按 deviation 倒推)
            if breaches:
                avg_actual = sum(b.actual_pct for b in breaches) / len(breaches)
            else:
                avg_actual = 100.0
            return {
                "tenant_id": tenant_id,
                "period_start": period_start,
                "period_end": period_end,
                "total_breaches": len(breaches),
                "total_credits": len(credits),
                "total_credit_amount_usd": round(total_credit, 2),
                "applied_credit_amount_usd": round(applied_credit, 2),
                "avg_actual_availability_pct": round(avg_actual, 4),
                "breaches_by_severity": {s.value: sum(1 for b in breaches if b.severity == s) for s in BreachSeverity},
                "credits_by_status": {s.value: sum(1 for c in credits if c.status == s) for s in CreditStatus},
            }

    def stats(self) -> dict[str, Any]:
        with self._lock:
            breach_severity: dict[str, int] = {}
            for b in self._breaches.values():
                k = b.severity.value
                breach_severity[k] = breach_severity.get(k, 0) + 1
            credit_status: dict[str, int] = {}
            for c in self._credits.values():
                k = c.status.value
                credit_status[k] = credit_status.get(k, 0) + 1
            total_credit = sum(c.credit_amount_usd for c in self._credits.values())
            applied = sum(
                c.credit_amount_usd
                for c in self._credits.values()
                if c.status in (CreditStatus.APPROVED, CreditStatus.APPLIED, CreditStatus.PAID)
            )
            return {
                "total_policies": len(self._policies),
                "total_breaches": len(self._breaches),
                "total_credits": len(self._credits),
                "total_disputes": len(self._disputes),
                "breach_severity": breach_severity,
                "credit_status": credit_status,
                "total_credit_amount_usd": round(total_credit, 2),
                "applied_credit_amount_usd": round(applied, 2),
            }

    # ---- persistence ----

    def _persist(self) -> None:
        if not self._persist_path:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "policies": {k: v.to_dict() for k, v in self._policies.items()},
                "breaches": {k: v.to_dict() for k, v in self._breaches.items()},
                "credits": {k: v.to_dict() for k, v in self._credits.items()},
                "disputes": {k: v.to_dict() for k, v in self._disputes.items()},
            }
            self._persist_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            for k, v in data.get("policies", {}).items():
                p = CompensationPolicy(
                    name=v["name"],
                    plan_tier=v.get("plan_tier", "enterprise"),
                    target_availability_pct=v.get("target_availability_pct", 99.9),
                    measurement_window_days=v.get("measurement_window_days", 30),
                    tiers=[CompensationTier(**t) for t in v.get("tiers", [])],
                    max_credit_pct=v.get("max_credit_pct", 100.0),
                    monthly_cap_pct=v.get("monthly_cap_pct", 100.0),
                    auto_apply=v.get("auto_apply", True),
                    metadata=v.get("metadata", {}),
                )
                p.id = v.get("id", k)
                p.created_at = v.get("created_at", time.time())
                self._policies[k] = p
            for k, v in data.get("breaches", {}).items():
                b = BreachEvent(
                    policy_id=v.get("policy_id", ""),
                    tenant_id=v.get("tenant_id", ""),
                    severity=BreachSeverity(v.get("severity", "low")),
                    target_pct=v.get("target_pct", 99.9),
                    actual_pct=v.get("actual_pct", 0.0),
                    downtime_sec=v.get("downtime_sec", 0.0),
                    measurement_start=v.get("measurement_start", 0.0),
                    measurement_end=v.get("measurement_end", 0.0),
                    related_incident_ids=v.get("related_incident_ids", []),
                    affected_components=v.get("affected_components", []),
                    detected_at=v.get("detected_at", time.time()),
                    description=v.get("description", ""),
                    metadata=v.get("metadata", {}),
                )
                b.id = v.get("id", k)
                self._breaches[k] = b
            for k, v in data.get("credits", {}).items():
                c = Credit(
                    breach_id=v.get("breach_id", ""),
                    policy_id=v.get("policy_id", ""),
                    tenant_id=v.get("tenant_id", ""),
                    status=CreditStatus(v.get("status", "pending")),
                    base_amount_usd=v.get("base_amount_usd", 0.0),
                    credit_pct=v.get("credit_pct", 0.0),
                    credit_amount_usd=v.get("credit_amount_usd", 0.0),
                    currency=v.get("currency", "USD"),
                    period_start=v.get("period_start", 0.0),
                    period_end=v.get("period_end", 0.0),
                    approved_by=v.get("approved_by", ""),
                    approved_at=v.get("approved_at", 0.0),
                    applied_at=v.get("applied_at", 0.0),
                    paid_at=v.get("paid_at", 0.0),
                    created_at=v.get("created_at", time.time()),
                    notes=v.get("notes", ""),
                    metadata=v.get("metadata", {}),
                )
                c.id = v.get("id", k)
                self._credits[k] = c
            for k, v in data.get("disputes", {}).items():
                d = Dispute(
                    credit_id=v.get("credit_id", ""),
                    tenant_id=v.get("tenant_id", ""),
                    status=DisputeStatus(v.get("status", "open")),
                    raised_by=v.get("raised_by", ""),
                    reason=v.get("reason", ""),
                    evidence=v.get("evidence", {}),
                    resolution=v.get("resolution", ""),
                    resolved_by=v.get("resolved_by", ""),
                    created_at=v.get("created_at", time.time()),
                    resolved_at=v.get("resolved_at", 0.0),
                    metadata=v.get("metadata", {}),
                )
                d.id = v.get("id", k)
                self._disputes[k] = d
        except Exception:
            pass


_engine: CompensationEngine | None = None


def get_compensation_engine() -> CompensationEngine:
    global _engine
    if _engine is None:
        _engine = CompensationEngine()
    return _engine


def reset_compensation_engine() -> None:
    global _engine
    _engine = None
