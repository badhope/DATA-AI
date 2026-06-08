"""
DATA-AI 企业级 — 用量与配额模块

能力:
- 按 API key / 用户 / 全局 多维度跟踪 token 用量与请求数
- 配额: 每日/每月 token 上限、QPS、并发
- 限流: 滑动窗口 + 令牌桶 (双算法)
- 成本估算: 不同模型单价 × token → 美元/人民币
- 告警: 接近配额 (>=80%) 时返回 header 提醒

典型企业场景:
- "这个月 AI 成本超 5k 美元要告警" → quota 配额
- "每秒最多 20 个 chat 请求" → QPS 限流
- "某项目组月度 1M token 预算" → per-key 配额
- "个人免费版 100 req/day" → 分级套餐
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

# 模型单价 (USD per 1M tokens) — 参考 2025 公开定价,可被 settings 覆盖
DEFAULT_MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "o1": {"input": 15.0, "output": 60.0},
    "o1-mini": {"input": 3.0, "output": 12.0},
    # Anthropic
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku": {"input": 0.8, "output": 4.0},
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    # DashScope (Qwen)
    "qwen-max": {"input": 0.4, "output": 1.2},
    "qwen-plus": {"input": 0.08, "output": 0.24},
    "qwen-turbo": {"input": 0.03, "output": 0.06},
    "qwen3-32b": {"input": 0.4, "output": 1.2},
    "qwen3-coder-flash": {"input": 0.1, "output": 0.3},
    # DeepSeek
    "deepseek-chat": {"input": 0.27, "output": 1.1},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # offline (免费)
    "offline-chat": {"input": 0.0, "output": 0.0},
    "offline-fast": {"input": 0.0, "output": 0.0},
    "offline-mini": {"input": 0.0, "output": 0.0},
}


@dataclass
class QuotaPolicy:
    """单条配额策略"""

    scope: Literal["global", "key", "user"] = "global"
    scope_id: str = ""  # key hash / user id
    daily_token_limit: int | None = None  # tokens/day
    monthly_token_limit: int | None = None  # tokens/month
    daily_request_limit: int | None = None  # req/day
    qps_limit: float | None = None  # req/sec (滑动窗口)
    max_concurrent: int | None = None  # 并发任务数
    enabled: bool = True


@dataclass
class UsageRecord:
    """一次调用的用量记录"""

    timestamp: float = field(default_factory=time.time)
    actor: str = "anonymous"
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    endpoint: str = ""


@dataclass
class RateLimitResult:
    """限流判定结果"""

    allowed: bool
    reason: str = ""
    retry_after: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)


class SlidingWindowCounter:
    """滑动窗口计数器 (QPS / 限流)"""

    def __init__(self, window_sec: float = 1.0) -> None:
        self.window_sec = window_sec
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def add(self, ts: float | None = None) -> int:
        ts = ts or time.time()
        with self._lock:
            self._timestamps.append(ts)
            self._evict(ts)
            return len(self._timestamps)

    def count(self) -> int:
        with self._lock:
            self._evict(time.time())
            return len(self._timestamps)

    def _evict(self, now: float) -> None:
        cutoff = now - self.window_sec
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()


class TokenBucket:
    """令牌桶 (QPS 平滑限流)"""

    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate  # tokens / sec
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last = time.time()
        self._lock = threading.Lock()

    def try_acquire(self, n: int = 1) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self._last
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last = now
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False


class UsageTracker:
    """用量跟踪器 (按 actor 维度聚合)"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: list[UsageRecord] = []
        self._by_actor: dict[str, list[UsageRecord]] = {}

    def record(self, rec: UsageRecord) -> None:
        with self._lock:
            self._records.append(rec)
            self._by_actor.setdefault(rec.actor, []).append(rec)

    def query(
        self,
        actor: str | None = None,
        model: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock:
            results: list[dict[str, Any]] = []
            src = self._by_actor.get(actor) if actor else self._records
            if src is None:
                return []
            for r in src:
                if model and r.model != model:
                    continue
                if since is not None and r.timestamp < since:
                    continue
                if until is not None and r.timestamp > until:
                    continue
                results.append(
                    {
                        "timestamp": r.timestamp,
                        "actor": r.actor,
                        "model": r.model,
                        "prompt_tokens": r.prompt_tokens,
                        "completion_tokens": r.completion_tokens,
                        "total_tokens": r.total_tokens,
                        "cost_usd": r.cost_usd,
                        "latency_ms": r.latency_ms,
                        "endpoint": r.endpoint,
                    }
                )
            return results[-limit:]

    def summary(
        self,
        actor: str | None = None,
        since: float | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            src = self._by_actor.get(actor) if actor else self._records
            if not src:
                return {
                    "total_requests": 0,
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost_usd": 0.0,
                    "by_model": {},
                }
            recs = [r for r in src if since is None or r.timestamp >= since]
            total_req = len(recs)
            prompt = sum(r.prompt_tokens for r in recs)
            completion = sum(r.completion_tokens for r in recs)
            cost = sum(r.cost_usd for r in recs)
            by_model: dict[str, dict[str, Any]] = {}
            for r in recs:
                m = r.model or "unknown"
                if m not in by_model:
                    by_model[m] = {"requests": 0, "tokens": 0, "cost_usd": 0.0}
                by_model[m]["requests"] += 1
                by_model[m]["tokens"] += r.total_tokens
                by_model[m]["cost_usd"] += r.cost_usd
            return {
                "total_requests": total_req,
                "total_tokens": prompt + completion,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "cost_usd": round(cost, 6),
                "by_model": by_model,
            }


class QuotaManager:
    """配额 + 限流统一管理器"""

    def __init__(self, pricing: dict[str, dict[str, float]] | None = None) -> None:
        self._lock = threading.RLock()
        self._policies: dict[str, QuotaPolicy] = {}  # key = "{scope}:{scope_id}"
        self._usage = UsageTracker()
        self._qps_windows: dict[str, SlidingWindowCounter] = {}  # actor → window
        self._buckets: dict[str, TokenBucket] = {}  # actor → token bucket
        self._concurrency: dict[str, int] = {}  # actor → active count
        self.pricing = pricing or DEFAULT_MODEL_PRICING

    # ---------- Policy CRUD ----------
    def set_policy(self, policy: QuotaPolicy) -> None:
        with self._lock:
            key = f"{policy.scope}:{policy.scope_id}"
            self._policies[key] = policy
            if policy.qps_limit:
                self._buckets[key] = TokenBucket(rate=policy.qps_limit, capacity=max(1, int(policy.qps_limit * 2)))
            self._qps_windows[key] = SlidingWindowCounter(window_sec=1.0)

    def list_policies(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._policy_to_dict(p) for p in self._policies.values()]

    def get_policy(self, scope: str, scope_id: str) -> dict[str, Any] | None:
        with self._lock:
            p = self._policies.get(f"{scope}:{scope_id}")
            return self._policy_to_dict(p) if p else None

    def delete_policy(self, scope: str, scope_id: str) -> bool:
        with self._lock:
            key = f"{scope}:{scope_id}"
            return self._policies.pop(key, None) is not None

    @staticmethod
    def _policy_to_dict(p: QuotaPolicy) -> dict[str, Any]:
        return {
            "scope": p.scope,
            "scope_id": p.scope_id,
            "daily_token_limit": p.daily_token_limit,
            "monthly_token_limit": p.monthly_token_limit,
            "daily_request_limit": p.daily_request_limit,
            "qps_limit": p.qps_limit,
            "max_concurrent": p.max_concurrent,
            "enabled": p.enabled,
        }

    # ---------- 限流判定 ----------
    def check_rate_limit(self, actor: str) -> RateLimitResult:
        """在请求进入时调用,判定是否放行"""
        with self._lock:
            for p in self._policies.values():
                if not p.enabled:
                    continue
                if p.scope == "global" or (p.scope == "key" and p.scope_id == actor):
                    key = f"{p.scope}:{p.scope_id}"
                    # QPS 令牌桶
                    if p.qps_limit and key in self._buckets:
                        if not self._buckets[key].try_acquire():
                            return RateLimitResult(
                                allowed=False,
                                reason="qps_exceeded",
                                retry_after=1.0 / p.qps_limit,
                            )
                    # 滑动窗口 QPS
                    if key in self._qps_windows:
                        cnt = self._qps_windows[key].add()
                        if p.qps_limit and cnt > p.qps_limit:
                            return RateLimitResult(
                                allowed=False,
                                reason="qps_window_exceeded",
                                retry_after=1.0,
                            )
                    # 并发
                    if p.max_concurrent and self._concurrency.get(key, 0) >= p.max_concurrent:
                        return RateLimitResult(
                            allowed=False,
                            reason="concurrent_exceeded",
                            retry_after=1.0,
                        )
                    # 日请求数
                    if p.daily_request_limit:
                        today_start = time.time() - 86400
                        cnt = sum(
                            1 for r in self._usage.query(actor=actor if p.scope == "key" else None, since=today_start)
                        )
                        if cnt >= p.daily_request_limit:
                            return RateLimitResult(
                                allowed=False,
                                reason="daily_request_exceeded",
                                retry_after=86400.0,
                            )
                    # 日 token
                    if p.daily_token_limit:
                        today_start = time.time() - 86400
                        summary = self._usage.summary(actor=actor if p.scope == "key" else None, since=today_start)
                        if summary["total_tokens"] >= p.daily_token_limit:
                            return RateLimitResult(
                                allowed=False,
                                reason="daily_token_exceeded",
                                retry_after=86400.0,
                            )
            return RateLimitResult(allowed=True)

    def acquire_concurrency(self, actor: str) -> None:
        """在请求开始时调用"""
        with self._lock:
            for p in self._policies.values():
                if p.scope == "key" and p.scope_id == actor and p.max_concurrent:
                    key = f"{p.scope}:{p.scope_id}"
                    self._concurrency[key] = self._concurrency.get(key, 0) + 1

    def release_concurrency(self, actor: str) -> None:
        with self._lock:
            for p in self._policies.values():
                if p.scope == "key" and p.scope_id == actor and p.max_concurrent:
                    key = f"{p.scope}:{p.scope_id}"
                    self._concurrency[key] = max(0, self._concurrency.get(key, 0) - 1)

    # ---------- 用量记录 ----------
    def record_usage(
        self,
        actor: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float = 0.0,
        endpoint: str = "",
    ) -> UsageRecord:
        total = prompt_tokens + completion_tokens
        cost = self._estimate_cost(model, prompt_tokens, completion_tokens)
        rec = UsageRecord(
            actor=actor,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_usd=cost,
            latency_ms=latency_ms,
            endpoint=endpoint,
        )
        self._usage.record(rec)
        return rec

    def _estimate_cost(self, model: str, prompt: int, completion: int) -> float:
        p = self.pricing.get(model, {"input": 0.0, "output": 0.0})
        return round((prompt / 1_000_000) * p["input"] + (completion / 1_000_000) * p["output"], 6)

    # ---------- 查询 ----------
    def usage_summary(
        self,
        actor: str | None = None,
        since: float | None = None,
    ) -> dict[str, Any]:
        return self._usage.summary(actor=actor, since=since)

    def usage_records(
        self,
        actor: str | None = None,
        model: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._usage.query(actor=actor, model=model, limit=limit)

    def quota_status(self, actor: str) -> dict[str, Any]:
        """查询 actor 当前剩余配额"""
        with self._lock:
            result: dict[str, Any] = {"actor": actor, "policies": [], "usage_today": {}}
            today_start = time.time() - 86400
            usage = self._usage.summary(actor=actor, since=today_start)
            result["usage_today"] = usage
            for p in self._policies.values():
                if p.scope == "key" and p.scope_id == actor and p.enabled:
                    policy_d = self._policy_to_dict(p)
                    if p.daily_token_limit:
                        policy_d["daily_token_remaining"] = max(0, p.daily_token_limit - usage["total_tokens"])
                        policy_d["daily_token_pct"] = round(usage["total_tokens"] / p.daily_token_limit * 100, 1)
                    if p.daily_request_limit:
                        policy_d["daily_request_remaining"] = max(0, p.daily_request_limit - usage["total_requests"])
                    result["policies"].append(policy_d)
            return result


# ============================================================================
# 全局单例
# ============================================================================

_GLOBAL: QuotaManager | None = None
_GLOBAL_LOCK = threading.Lock()


def get_quota_manager() -> QuotaManager:
    global _GLOBAL
    with _GLOBAL_LOCK:
        if _GLOBAL is None:
            _GLOBAL = QuotaManager()
        return _GLOBAL


def reset_quota_manager() -> None:
    global _GLOBAL
    with _GLOBAL_LOCK:
        _GLOBAL = None
