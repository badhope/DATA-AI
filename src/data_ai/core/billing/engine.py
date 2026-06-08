"""
DATA-AI 企业级 — 成本中心 / 账单分摊

企业痛点:
- 财务: AI 成本不能一个总数,要按部门/项目/租户拆分
- 预算控制: 月度预算用尽前告警
- 成本归因: 哪些 Agent / Team / Skill 在烧钱?
- 发票/账单: 对外给客户提供按用量计费
- 成本预测: 趋势外推月度结算金额

设计:
- PricingModel: 模型定价 (input/output per 1k token,缓存折扣)
- UsageRecord: 一次资源使用的成本记录
- Budget: 预算配置 (monthly/quarterly/annual + 软硬限)
- CostCenter: 成本归属维度 (department / project / cost_center_id)
- BillingEngine: 计算 / 汇总 / 分摊 / 导出账单
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

# ============================================================================
# 模型定价
# ============================================================================

# 默认定价 (USD per 1k tokens) — 可被 settings 覆盖
DEFAULT_PRICING: dict[str, dict[str, float]] = {
    # model_id: {input: 0.01, output: 0.03}
    "gpt-4o": {"input": 0.005, "output": 0.015, "cached_input": 0.0025},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006, "cached_input": 0.000075},
    "claude-sonnet-4": {"input": 0.003, "output": 0.015, "cached_input": 0.0003},
    "claude-opus-4": {"input": 0.015, "output": 0.075, "cached_input": 0.0015},
    "qwen-max": {"input": 0.0004, "output": 0.0012, "cached_input": 0.0001},
    "qwen-plus": {"input": 0.0002, "output": 0.0006, "cached_input": 0.00005},
    "qwen-turbo": {"input": 0.0001, "output": 0.0003, "cached_input": 0.00002},
    "offline-fast": {"input": 0.0, "output": 0.0, "cached_input": 0.0},
    "default": {"input": 0.001, "output": 0.003, "cached_input": 0.0005},
}


@dataclass
class PricingModel:
    """模型定价表"""

    model_id: str
    input_per_1k: float
    output_per_1k: float
    cached_input_per_1k: float = 0.0
    currency: str = "USD"
    notes: str = ""

    def calculate(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_tokens: int = 0,
    ) -> float:
        """计算一次调用的费用"""
        cost = (
            (prompt_tokens - cached_tokens) / 1000.0 * self.input_per_1k
            + cached_tokens / 1000.0 * self.cached_input_per_1k
            + completion_tokens / 1000.0 * self.output_per_1k
        )
        return max(0.0, round(cost, 8))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
# 用量记录
# ============================================================================


@dataclass
class UsageRecord:
    """一次资源使用的成本记录"""

    id: str = field(default_factory=lambda: f"usr-{uuid.uuid4().hex[:12]}")
    tenant_id: str = ""
    user_id: str = ""
    cost_center_id: str = ""  # 成本中心/部门
    project: str = ""
    resource_type: str = "agent"  # agent/team/skill/tool/rag/sandbox/...
    resource_id: str = ""
    model_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    currency: str = "USD"
    occurred_at: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UsageRecord:
        return cls(**d)


# ============================================================================
# 预算
# ============================================================================

BudgetPeriod = Literal["daily", "weekly", "monthly", "quarterly", "annual", "custom"]


@dataclass
class Budget:
    """预算 — 软/硬限 + 告警阈值"""

    id: str = field(default_factory=lambda: f"bdg-{uuid.uuid4().hex[:8]}")
    name: str = ""
    scope: str = "tenant"  # tenant | cost_center | project | user
    scope_id: str = ""  # tenant_id / cost_center_id / project / user_id
    period: BudgetPeriod = "monthly"
    amount_usd: float = 1000.0
    hard_limit: bool = False  # True=超额拒绝调用;False=仅告警
    warn_threshold: float = 0.8  # 80% 触发告警
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Budget:
        return cls(**d)


# ============================================================================
# 成本中心
# ============================================================================


@dataclass
class CostCenter:
    """成本归属维度 — 部门/项目"""

    id: str = field(default_factory=lambda: f"cc-{uuid.uuid4().hex[:8]}")
    tenant_id: str = ""
    name: str = ""  # 部门/项目名
    code: str = ""  # 财务代码
    parent_id: str = ""  # 支持层级
    manager_user_id: str = ""
    monthly_budget_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CostCenter:
        return cls(**d)


# ============================================================================
# 引擎
# ============================================================================


class BillingEngine:
    """成本中心主引擎"""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._pricing: dict[str, PricingModel] = {}
        self._load_default_pricing()
        self._records: list[UsageRecord] = []
        self._budgets: dict[str, Budget] = {}
        self._cost_centers: dict[str, CostCenter] = {}
        self._persist_path = persist_path
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _load_default_pricing(self) -> None:
        for mid, prices in DEFAULT_PRICING.items():
            self._pricing[mid] = PricingModel(
                model_id=mid,
                input_per_1k=prices["input"],
                output_per_1k=prices["output"],
                cached_input_per_1k=prices.get("cached_input", prices["input"] * 0.5),
            )

    # ---------- 定价 ----------
    def set_pricing(self, model_id: str, input_per_1k: float, output_per_1k: float, **kwargs: Any) -> PricingModel:
        with self._lock:
            p = PricingModel(model_id=model_id, input_per_1k=input_per_1k, output_per_1k=output_per_1k, **kwargs)
            self._pricing[model_id] = p
            return p

    def get_pricing(self, model_id: str) -> PricingModel:
        with self._lock:
            if model_id in self._pricing:
                return self._pricing[model_id]
            return self._pricing.get("default", PricingModel("default", 0.001, 0.003))

    def list_pricing(self) -> list[PricingModel]:
        with self._lock:
            return list(self._pricing.values())

    # ---------- 记录 ----------
    def record(
        self,
        tenant_id: str = "",
        user_id: str = "",
        cost_center_id: str = "",
        project: str = "",
        resource_type: str = "agent",
        resource_id: str = "",
        model_id: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_tokens: int = 0,
    ) -> UsageRecord:
        """记录一次使用并计算费用"""
        with self._lock:
            pricing = self.get_pricing(model_id)
            cost = pricing.calculate(prompt_tokens, completion_tokens, cached_tokens)
            r = UsageRecord(
                tenant_id=tenant_id, user_id=user_id, cost_center_id=cost_center_id, project=project,
                resource_type=resource_type, resource_id=resource_id, model_id=model_id,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cached_tokens=cached_tokens,
                cost_usd=cost, currency=pricing.currency,
            )
            self._records.append(r)
            # 限制内存:最近 5 万条
            if len(self._records) > 50000:
                self._records = self._records[-50000:]
            self._write_record(r)
            return r

    def list_records(
        self, tenant_id: str = "", cost_center_id: str = "", since: float | None = None, until: float | None = None, limit: int = 100
    ) -> list[UsageRecord]:
        with self._lock:
            out = []
            for r in reversed(self._records):
                if tenant_id and r.tenant_id != tenant_id:
                    continue
                if cost_center_id and r.cost_center_id != cost_center_id:
                    continue
                if since is not None and r.occurred_at < since:
                    continue
                if until is not None and r.occurred_at > until:
                    continue
                out.append(r)
                if len(out) >= limit:
                    break
            return out

    # ---------- 预算 ----------
    def set_budget(self, budget: Budget) -> Budget:
        with self._lock:
            self._budgets[budget.id] = budget
            return budget

    def list_budgets(self, scope: str | None = None, scope_id: str = "") -> list[Budget]:
        with self._lock:
            out = list(self._budgets.values())
            if scope:
                out = [b for b in out if b.scope == scope]
            if scope_id:
                out = [b for b in out if b.scope_id == scope_id]
            return out

    def delete_budget(self, budget_id: str) -> bool:
        with self._lock:
            return self._budgets.pop(budget_id, None) is not None

    def check_budget(self, tenant_id: str = "", cost_center_id: str = "") -> tuple[bool, list[dict[str, Any]]]:
        """检查预算使用情况。返回 (ok, alerts)
        - ok=False 表示硬限超额,应拒绝调用
        - alerts 是阈值告警列表
        """
        with self._lock:
            alerts: list[dict[str, Any]] = []
            hard_exceeded = False
            now = time.time()
            for b in self._budgets.values():
                if not b.enabled:
                    continue
                # 匹配 scope
                if b.scope == "tenant" and b.scope_id != tenant_id:
                    continue
                if b.scope == "cost_center" and b.scope_id != cost_center_id:
                    continue
                # 计算周期
                period_start = self._period_start(b.period, now)
                used = sum(r.cost_usd for r in self._records if r.occurred_at >= period_start)
                if b.scope == "tenant":
                    used = sum(r.cost_usd for r in self._records if r.tenant_id == b.scope_id and r.occurred_at >= period_start)
                elif b.scope == "cost_center":
                    used = sum(r.cost_usd for r in self._records if r.cost_center_id == b.scope_id and r.occurred_at >= period_start)

                usage_pct = used / b.amount_usd if b.amount_usd > 0 else 0.0
                if usage_pct >= 1.0:
                    if b.hard_limit:
                        hard_exceeded = True
                    alerts.append({
                        "budget_id": b.id, "budget_name": b.name, "used_usd": round(used, 4),
                        "limit_usd": b.amount_usd, "usage_pct": round(usage_pct * 100, 1),
                        "level": "exceeded",
                    })
                elif usage_pct >= b.warn_threshold:
                    alerts.append({
                        "budget_id": b.id, "budget_name": b.name, "used_usd": round(used, 4),
                        "limit_usd": b.amount_usd, "usage_pct": round(usage_pct * 100, 1),
                        "level": "warning",
                    })
            return (not hard_exceeded), alerts

    def _period_start(self, period: BudgetPeriod, now: float) -> float:
        dt = datetime.fromtimestamp(now)
        if period == "daily":
            return dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        if period == "weekly":
            start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            return start.timestamp() - start.weekday() * 86400
        if period == "monthly":
            return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        if period == "quarterly":
            q_month = ((dt.month - 1) // 3) * 3 + 1
            return dt.replace(month=q_month, day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        if period == "annual":
            return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        return now - 30 * 86400  # custom 默认 30 天

    # ---------- 成本中心 ----------
    def add_cost_center(self, cc: CostCenter) -> CostCenter:
        with self._lock:
            self._cost_centers[cc.id] = cc
            return cc

    def list_cost_centers(self, tenant_id: str = "") -> list[CostCenter]:
        with self._lock:
            out = list(self._cost_centers.values())
            if tenant_id:
                out = [c for c in out if c.tenant_id == tenant_id]
            return out

    def get_cost_center(self, cc_id: str) -> CostCenter | None:
        return self._cost_centers.get(cc_id)

    # ---------- 聚合报表 ----------
    def summary(
        self,
        tenant_id: str = "",
        since: float | None = None,
        until: float | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            if since is None:
                since = now - 30 * 86400
            if until is None:
                until = now
            records = [
                r for r in self._records
                if r.occurred_at >= since and r.occurred_at <= until
                and (not tenant_id or r.tenant_id == tenant_id)
            ]
            total_cost = sum(r.cost_usd for r in records)
            total_tokens = sum(r.prompt_tokens + r.completion_tokens for r in records)
            total_requests = len(records)
            # by_model
            by_model: dict[str, dict[str, float]] = {}
            for r in records:
                m = r.model_id or "unknown"
                if m not in by_model:
                    by_model[m] = {"cost_usd": 0.0, "tokens": 0, "requests": 0}
                by_model[m]["cost_usd"] += r.cost_usd
                by_model[m]["tokens"] += r.prompt_tokens + r.completion_tokens
                by_model[m]["requests"] += 1
            # by_cost_center
            by_cc: dict[str, float] = {}
            for r in records:
                cc = r.cost_center_id or "unassigned"
                by_cc[cc] = by_cc.get(cc, 0.0) + r.cost_usd
            # by_resource_type
            by_rt: dict[str, float] = {}
            for r in records:
                rt = r.resource_type or "unknown"
                by_rt[rt] = by_rt.get(rt, 0.0) + r.cost_usd
            return {
                "total_cost_usd": round(total_cost, 4),
                "total_tokens": total_tokens,
                "total_requests": total_requests,
                "by_model": {k: {"cost_usd": round(v["cost_usd"], 4), "tokens": int(v["tokens"]), "requests": int(v["requests"])} for k, v in by_model.items()},
                "by_cost_center": {k: round(v, 4) for k, v in by_cc.items()},
                "by_resource_type": {k: round(v, 4) for k, v in by_rt.items()},
                "since": since,
                "until": until,
            }

    def cost_by_day(
        self, tenant_id: str = "", days: int = 30, until: float | None = None
    ) -> list[dict[str, Any]]:
        """按日聚合成本(用于画趋势图)"""
        with self._lock:
            now = until or time.time()
            buckets: dict[str, float] = {}
            for r in self._records:
                if tenant_id and r.tenant_id != tenant_id:
                    continue
                if r.occurred_at < now - days * 86400 or r.occurred_at > now:
                    continue
                day = datetime.fromtimestamp(r.occurred_at).strftime("%Y-%m-%d")
                buckets[day] = buckets.get(day, 0.0) + r.cost_usd
            out = [{"date": d, "cost_usd": round(c, 4)} for d, c in sorted(buckets.items())]
            return out

    def top_spenders(
        self, by: str = "user", tenant_id: str = "", limit: int = 10, since: float | None = None
    ) -> list[dict[str, Any]]:
        """Top N 烧钱用户/项目/资源"""
        with self._lock:
            if since is None:
                since = time.time() - 30 * 86400
            agg: dict[str, float] = {}
            for r in self._records:
                if r.occurred_at < since:
                    continue
                if tenant_id and r.tenant_id != tenant_id:
                    continue
                key = r.user_id if by == "user" else (r.project if by == "project" else r.resource_id)
                if not key:
                    key = "unknown"
                agg[key] = agg.get(key, 0.0) + r.cost_usd
            top = sorted(agg.items(), key=lambda x: x[1], reverse=True)[:limit]
            return [{"key": k, "cost_usd": round(c, 4)} for k, c in top]

    def export_invoice(
        self, tenant_id: str, since: float, until: float, format: str = "json"
    ) -> str:
        """导出账单"""
        records = self.list_records(tenant_id=tenant_id, since=since, until=until, limit=100000)
        if format == "csv":
            import csv
            import io
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=records[0].to_dict().keys() if records else [
                "id", "tenant_id", "user_id", "cost_center_id", "model_id", "prompt_tokens", "completion_tokens", "cost_usd", "occurred_at"
            ])
            w.writeheader()
            for r in records:
                w.writerow(r.to_dict())
            return buf.getvalue()
        return json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2)

    # ---------- 持久化 ----------
    def _write_record(self, r: UsageRecord) -> None:
        if not self._persist_path:
            return
        try:
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"type": "record", "data": r.to_dict()}, ensure_ascii=False) + "\n")
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
                    if rec.get("type") == "record":
                        self._records.append(UsageRecord.from_dict(rec["data"]))
                    elif rec.get("type") == "budget":
                        b = Budget.from_dict(rec["data"])
                        self._budgets[b.id] = b
                    elif rec.get("type") == "cost_center":
                        c = CostCenter.from_dict(rec["data"])
                        self._cost_centers[c.id] = c
        except Exception:
            pass


# ============================================================================
# 全局单例
# ============================================================================

_GLOBAL_ENGINE: BillingEngine | None = None
_GLOBAL_LOCK = threading.Lock()


def get_billing_engine(persist_path: Path | None = None) -> BillingEngine:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        if _GLOBAL_ENGINE is None:
            _GLOBAL_ENGINE = BillingEngine(persist_path=persist_path)
        return _GLOBAL_ENGINE


def reset_billing_engine() -> None:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        _GLOBAL_ENGINE = None
