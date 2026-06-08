"""
DATA-AI 企业级 — Webhook 模块

能力:
- 订阅: 业务系统声明对某类事件感兴趣
- 派发: 事件触发时 HTTP POST 到所有订阅者
- 重试: 失败按指数退避重试 (最多 N 次)
- 签名: HMAC-SHA256 签名 + timestamp 防伪造
- 投递日志: 每次投递的状态/响应/耗时

典型企业场景:
- "Agent run 完成后通知 Slack" → 订阅 agent.run.completed
- "RAG 文档更新后同步到企业知识库" → 订阅 rag.document.updated
- "Memory 写入时同步到审计系统" → 订阅 memory.created
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

import httpx

# 支持的事件类型
EVENT_TYPES = [
    "agent.run.started",
    "agent.run.completed",
    "agent.run.failed",
    "agent.run.approval_required",
    "team.run.completed",
    "memory.created",
    "memory.updated",
    "memory.deleted",
    "rag.document.created",
    "rag.document.deleted",
    "skill.created",
    "skill.executed",
    "sandbox.created",
    "sandbox.executed",
    "tool.executed",
    "notification.created",
    "session.created",
    "session.deleted",
    "quota.exceeded",
    "audit.high_risk",
]


@dataclass
class WebhookSubscription:
    """Webhook 订阅"""

    id: str = field(default_factory=lambda: f"wh-{uuid.uuid4().hex[:12]}")
    name: str = ""
    url: str = ""
    secret: str = field(default_factory=lambda: secrets.token_hex(24))  # HMAC 密钥
    events: list[str] = field(default_factory=list)
    active: bool = True
    created_at: float = field(default_factory=time.time)
    description: str = ""
    custom_headers: dict[str, str] = field(default_factory=dict)
    max_retries: int = 3
    timeout_sec: float = 10.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WebhookSubscription:
        return cls(**d)


@dataclass
class WebhookDelivery:
    """Webhook 投递记录"""

    id: str = field(default_factory=lambda: f"whd-{uuid.uuid4().hex[:12]}")
    subscription_id: str = ""
    event: str = ""
    url: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: Literal["pending", "success", "failed", "retrying"] = "pending"
    status_code: int = 0
    response_body: str = ""
    attempt: int = 1
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    error: str = ""
    next_retry_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sign_payload(secret: str, body: str, timestamp: str) -> str:
    """HMAC-SHA256 签名:防止伪造 + 重放"""
    msg = f"{timestamp}.{body}".encode()
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


class WebhookDispatcher:
    """Webhook 派发器"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subs: dict[str, WebhookSubscription] = {}
        self._deliveries: list[WebhookDelivery] = []
        self._max_history = 1000

    # ---------- Subscription CRUD ----------
    def create(self, sub: WebhookSubscription) -> WebhookSubscription:
        with self._lock:
            self._subs[sub.id] = sub
            return sub

    def get(self, sub_id: str) -> WebhookSubscription | None:
        with self._lock:
            return self._subs.get(sub_id)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._subs.values()]

    def update(self, sub_id: str, **kwargs: Any) -> WebhookSubscription | None:
        with self._lock:
            sub = self._subs.get(sub_id)
            if not sub:
                return None
            for k, v in kwargs.items():
                if hasattr(sub, k) and k != "id":
                    setattr(sub, k, v)
            return sub

    def delete(self, sub_id: str) -> bool:
        with self._lock:
            return self._subs.pop(sub_id, None) is not None

    # ---------- 事件派发 ----------
    def _matching_subs(self, event: str) -> list[WebhookSubscription]:
        with self._lock:
            return [s for s in self._subs.values() if s.active and (event in s.events or "*" in s.events)]

    async def dispatch(self, event: str, payload: dict[str, Any]) -> list[str]:
        """派发事件,返回 delivery IDs"""
        subs = self._matching_subs(event)
        if not subs:
            return []
        ids: list[str] = []
        for sub in subs:
            d = WebhookDelivery(
                subscription_id=sub.id,
                event=event,
                url=sub.url,
                payload=payload,
            )
            self._record_delivery(d)
            ids.append(d.id)
            # 异步投递 (非阻塞)
            asyncio.create_task(self._deliver_with_retry(sub, d))
        return ids

    def dispatch_sync(self, event: str, payload: dict[str, Any]) -> list[str]:
        """同步版 (用于非 async 上下文)"""
        subs = self._matching_subs(event)
        if not subs:
            return []
        ids: list[str] = []
        for sub in subs:
            d = WebhookDelivery(
                subscription_id=sub.id,
                event=event,
                url=sub.url,
                payload=payload,
            )
            self._record_delivery(d)
            ids.append(d.id)
        return ids

    async def _deliver_with_retry(self, sub: WebhookSubscription, delivery: WebhookDelivery) -> None:
        body = json.dumps(
            {
                "event": delivery.event,
                "delivery_id": delivery.id,
                "timestamp": delivery.timestamp,
                "data": delivery.payload,
            },
            ensure_ascii=False,
        )
        ts = str(int(time.time()))
        sig = _sign_payload(sub.secret, body, ts)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DATA-AI-Webhooks/1.0",
            "X-DATA-AI-Event": delivery.event,
            "X-DATA-AI-Delivery": delivery.id,
            "X-DATA-AI-Signature": f"sha256={sig}",
            "X-DATA-AI-Timestamp": ts,
        }
        headers.update(sub.custom_headers)
        backoff = 1.0
        for attempt in range(1, sub.max_retries + 2):
            delivery.attempt = attempt
            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=sub.timeout_sec) as client:
                    resp = await client.post(sub.url, content=body, headers=headers)
                delivery.status_code = resp.status_code
                delivery.response_body = resp.text[:1000]
                delivery.duration_ms = round((time.time() - start) * 1000, 2)
                if 200 <= resp.status_code < 300:
                    delivery.status = "success"
                    self._update_delivery(delivery)
                    return
                delivery.error = f"HTTP {resp.status_code}"
            except Exception as e:  # noqa: BLE001
                delivery.error = str(e)[:200]
                delivery.duration_ms = round((time.time() - start) * 1000, 2)
            # 失败 → 退避重试
            if attempt <= sub.max_retries:
                delivery.status = "retrying"
                delivery.next_retry_at = time.time() + backoff
                self._update_delivery(delivery)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
            else:
                delivery.status = "failed"
                self._update_delivery(delivery)

    def _record_delivery(self, d: WebhookDelivery) -> None:
        with self._lock:
            self._deliveries.append(d)
            if len(self._deliveries) > self._max_history:
                self._deliveries = self._deliveries[-self._max_history :]

    def _update_delivery(self, d: WebhookDelivery) -> None:
        with self._lock:
            for i, existing in enumerate(self._deliveries):
                if existing.id == d.id:
                    self._deliveries[i] = d
                    return

    # ---------- 投递日志 ----------
    def list_deliveries(
        self,
        subscription_id: str | None = None,
        event: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock:
            results: list[dict[str, Any]] = []
            for d in reversed(self._deliveries):
                if subscription_id and d.subscription_id != subscription_id:
                    continue
                if event and d.event != event:
                    continue
                if status and d.status != status:
                    continue
                results.append(d.to_dict())
            return results[:limit]

    def delivery_stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._deliveries)
            by_status: dict[str, int] = {}
            for d in self._deliveries:
                by_status[d.status] = by_status.get(d.status, 0) + 1
            return {"total": total, "by_status": by_status}

    # ---------- 测试发送 ----------
    async def test_send(self, sub_id: str) -> WebhookDelivery:
        sub = self.get(sub_id)
        if not sub:
            raise ValueError(f"subscription {sub_id} not found")
        d = WebhookDelivery(
            subscription_id=sub.id,
            event="webhook.test",
            url=sub.url,
            payload={"test": True, "ts": datetime.utcnow().isoformat()},
        )
        self._record_delivery(d)
        await self._deliver_with_retry(sub, d)
        return d


# ============================================================================
# 全局单例
# ============================================================================

_GLOBAL: WebhookDispatcher | None = None
_GLOBAL_LOCK = threading.Lock()


def get_webhook_dispatcher() -> WebhookDispatcher:
    global _GLOBAL
    with _GLOBAL_LOCK:
        if _GLOBAL is None:
            _GLOBAL = WebhookDispatcher()
        return _GLOBAL


def reset_webhook_dispatcher() -> None:
    global _GLOBAL
    with _GLOBAL_LOCK:
        _GLOBAL = None
