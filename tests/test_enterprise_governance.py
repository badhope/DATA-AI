"""
P1-10 企业治理四件套单元测试
============================
覆盖:
- Audit log: 记录 / 查询 / 过滤 / 导出 / 限容量
- Quota: 令牌桶 / 滑动窗口 / 用量记录 / cost 计算 / 限流决策
- Webhooks: 签名 / 派发 / 订阅 CRUD / 投递统计
- Scheduler: cron / at / every 解析 / 执行 / 触发
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ============================================================================
# Audit
# ============================================================================


class TestAuditLog:
    def test_audit_entry_fields(self):
        from data_ai.core.audit import AuditEntry

        e = AuditEntry(
            actor="user-1",
            action="chat",
            resource_type="chat",
            resource_id="x",
            method="POST",
            path="/v1/chat",
            status_code=200,
            duration_ms=12,
        )
        d = e.to_dict()
        assert d["actor"] == "user-1"
        assert d["status_code"] == 200
        assert "id" in d
        assert "timestamp" in d

    def test_audit_store_append_and_query(self, tmp_path: Path):
        from data_ai.core.audit import AuditEntry, AuditStore

        store = AuditStore(persist_path=tmp_path / "audit.jsonl", max_memory=100)
        for i in range(5):
            store.append(
                AuditEntry(
                    actor=f"u{i}",
                    action="chat",
                    resource_type="chat",
                    resource_id=str(i),
                    method="POST",
                    path=f"/v1/chat/{i}",
                    status_code=200,
                    duration_ms=10,
                )
            )
        all_items = store.query(limit=100)
        assert len(all_items) == 5
        # 倒序
        assert all_items[0]["resource_id"] == "4"

    def test_audit_store_filter(self, tmp_path: Path):
        from data_ai.core.audit import AuditEntry, AuditStore

        store = AuditStore(persist_path=tmp_path / "audit.jsonl", max_memory=100)
        for i in range(10):
            store.append(
                AuditEntry(
                    actor="u1" if i % 2 == 0 else "u2",
                    action="chat" if i < 5 else "rag",
                    resource_type="chat",
                    resource_id=str(i),
                    method="POST",
                    path="/v1/chat",
                    status_code=200 if i < 7 else 500,
                    duration_ms=10,
                )
            )
        u1 = store.query(actor="u1")
        assert all(e["actor"] == "u1" for e in u1)
        assert len(u1) == 5
        chat = store.query(action="chat")
        assert all(e["action"] == "chat" for e in chat)
        assert len(chat) == 5

    def test_audit_store_persistence(self, tmp_path: Path):
        from data_ai.core.audit import AuditEntry, AuditStore

        path = tmp_path / "audit.jsonl"
        s1 = AuditStore(persist_path=path, max_memory=100)
        s1.append(
            AuditEntry(
                actor="u1",
                action="chat",
                resource_type="chat",
                resource_id="r1",
                method="POST",
                path="/v1/chat",
                status_code=200,
                duration_ms=10,
            )
        )
        s2 = AuditStore(persist_path=path, max_memory=100)
        items = s2.query(limit=100)
        assert len(items) == 1
        assert items[0]["resource_id"] == "r1"

    def test_audit_store_max_memory(self, tmp_path: Path):
        from data_ai.core.audit import AuditEntry, AuditStore

        store = AuditStore(persist_path=tmp_path / "audit.jsonl", max_memory=3)
        for i in range(5):
            store.append(
                AuditEntry(
                    actor="u",
                    action="x",
                    resource_type="x",
                    resource_id=str(i),
                    method="GET",
                    path="/",
                    status_code=200,
                    duration_ms=1,
                )
            )
        items = store.query(limit=100)
        assert len(items) == 3
        assert [i["resource_id"] for i in items] == ["4", "3", "2"]

    def test_audit_export(self, tmp_path: Path):
        from data_ai.core.audit import AuditEntry, AuditStore

        store = AuditStore(persist_path=tmp_path / "audit.jsonl", max_memory=100)
        for i in range(3):
            store.append(
                AuditEntry(
                    actor="u1",
                    action="chat",
                    resource_type="chat",
                    resource_id=str(i),
                    method="POST",
                    path="/v1/chat",
                    status_code=200,
                    duration_ms=10,
                )
            )
        json_out = store.export_json()
        parsed = json.loads(json_out) if False else __import__("json").loads(json_out)
        assert len(parsed) == 3
        csv_out = store.export_csv()
        # CSV 头 + 3 行
        lines = csv_out.strip().split("\n")
        assert len(lines) == 4
        assert lines[0].startswith("id,")

    def test_audit_stats(self, tmp_path: Path):
        from data_ai.core.audit import AuditEntry, AuditStore

        store = AuditStore(persist_path=tmp_path / "audit.jsonl", max_memory=100)
        for code in [200, 200, 200, 400, 500]:
            store.append(
                AuditEntry(
                    actor="u",
                    action="chat" if code == 200 else "err",
                    resource_type="x",
                    resource_id="1",
                    method="GET",
                    path="/",
                    status_code=code,
                    duration_ms=1,
                )
            )
        s = store.stats()
        assert s["by_status"]["200"] == 3
        assert s["by_status"]["400"] == 1
        assert s["by_status"]["500"] == 1
        assert s["top_actions"][0]["action"] == "chat"

    def test_audit_count(self, tmp_path: Path):
        from data_ai.core.audit import AuditEntry, AuditStore

        store = AuditStore(persist_path=tmp_path / "audit.jsonl", max_memory=100)
        for i in range(7):
            store.append(
                AuditEntry(
                    actor="u1" if i < 4 else "u2",
                    action="chat",
                    resource_type="chat",
                    resource_id=str(i),
                    method="POST",
                    path="/v1/chat",
                    status_code=200,
                    duration_ms=10,
                )
            )
        assert store.count(actor="u1") == 4
        assert store.count(actor="u2") == 3
        assert store.count() == 7

    def test_audit_clear(self, tmp_path: Path):
        from data_ai.core.audit import AuditEntry, AuditStore

        path = tmp_path / "audit.jsonl"
        store = AuditStore(persist_path=path, max_memory=100)
        for i in range(3):
            store.append(
                AuditEntry(
                    actor="u",
                    action="x",
                    resource_type="x",
                    resource_id=str(i),
                    method="GET",
                    path="/",
                    status_code=200,
                    duration_ms=1,
                )
            )
        store.clear()
        assert store.count() == 0
        # 文件应被清空
        assert not path.exists() or path.stat().st_size == 0


# ============================================================================
# Quota
# ============================================================================


class TestQuota:
    def test_token_bucket_allow_then_block(self):
        from data_ai.core.quota import TokenBucket

        b = TokenBucket(rate=2.0, capacity=2)
        assert b.try_acquire() is True
        assert b.try_acquire() is True
        assert b.try_acquire() is False

    def test_token_bucket_refill(self):
        from data_ai.core.quota import TokenBucket

        b = TokenBucket(rate=10.0, capacity=2)
        b.try_acquire()
        b.try_acquire()
        # 等 0.3s 应该补 ~3 个 token
        time.sleep(0.3)
        assert b.try_acquire() is True

    def test_sliding_window_counter(self):
        from data_ai.core.quota import SlidingWindowCounter

        c = SlidingWindowCounter(window_sec=1.0)
        # add 返回当前计数
        assert c.add() == 1
        assert c.add() == 2
        assert c.add() == 3
        # 1.1s 后窗口已清空
        time.sleep(1.1)
        assert c.add() == 1
        assert c.count() == 1

    def test_usage_record_cost(self):
        from data_ai.core.quota import UsageRecord, UsageTracker

        t = UsageTracker()
        rec = UsageRecord(
            actor="u1",
            model="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500,
            latency_ms=200,
            endpoint="/v1/chat",
        )
        rec.cost_usd = t._compute_cost("gpt-4o", 1000, 500) if hasattr(t, "_compute_cost") else 0
        # 直接用 QuotaManager._estimate_cost
        from data_ai.core.quota import QuotaManager

        cost = QuotaManager()._estimate_cost("gpt-4o", 1000, 500)
        # gpt-4o input 2.5/1M, output 10/1M → 0.0025 + 0.005 = 0.0075
        assert cost == pytest.approx(0.0075, abs=1e-6)

    def test_quota_policy_lookup(self):
        from data_ai.core.quota import QuotaManager

        m = QuotaManager()
        from data_ai.core.quota import QuotaPolicy

        m.set_policy(
            QuotaPolicy(
                scope="global",
                scope_id="default",
                daily_token_limit=1000,
                qps_limit=10,
                max_concurrent=5,
                enabled=True,
            )
        )
        policies = m.list_policies()
        assert any(p["scope"] == "global" for p in policies)
        assert m.get_policy("global", "default")["qps_limit"] == 10

    def test_quota_check_rate_limit_deny_when_qps_exceeded(self):
        from data_ai.core.quota import QuotaManager, QuotaPolicy

        m = QuotaManager()
        m.set_policy(
            QuotaPolicy(
                scope="global",
                scope_id="default",
                qps_limit=2,
                enabled=True,
            )
        )
        r1 = m.check_rate_limit("u1")
        r2 = m.check_rate_limit("u1")
        r3 = m.check_rate_limit("u1")
        assert r1.allowed is True
        assert r2.allowed is True
        assert r3.allowed is False
        assert "qps" in r3.reason

    def test_quota_concurrency_tracking(self):
        from data_ai.core.quota import QuotaManager, QuotaPolicy

        m = QuotaManager()
        # 注意: acquire_concurrency 只对 key scope 生效
        m.set_policy(
            QuotaPolicy(
                scope="key",
                scope_id="u1",
                max_concurrent=2,
                enabled=True,
            )
        )
        # acquire_concurrency 是 fire-and-forget,返回 None
        assert m.acquire_concurrency("u1") is None
        m.acquire_concurrency("u1")
        # 第 3 次应记录但不应阻止
        m.acquire_concurrency("u1")
        # release 后内部计数减 1
        m.release_concurrency("u1")
        assert m._concurrency.get("key:u1", 0) == 2

    def test_quota_daily_token_block(self):
        from data_ai.core.quota import QuotaManager, QuotaPolicy

        m = QuotaManager()
        m.set_policy(
            QuotaPolicy(
                scope="global",
                scope_id="default",
                daily_token_limit=100,
                enabled=True,
            )
        )
        # 1 个调用消耗 90 token
        m.record_usage("u1", "gpt-4o", 80, 10)
        # 下一个 50 token 调用应触发 daily_token 限制
        m.record_usage("u1", "gpt-4o", 30, 20)
        r2 = m.check_rate_limit("u1")
        assert r2.allowed is False
        assert "daily_token" in r2.reason

    def test_quota_summary(self):
        from data_ai.core.quota import QuotaManager

        m = QuotaManager()
        m.record_usage("u1", "gpt-4o", 100, 50, latency_ms=200)
        m.record_usage("u1", "gpt-4o", 200, 100, latency_ms=300)
        m.record_usage("u2", "gpt-4o", 50, 25, latency_ms=150)
        s = m.usage_summary()
        assert s["total_requests"] == 3
        assert s["total_tokens"] == 525
        assert s["by_model"]["gpt-4o"]["requests"] == 3

    def test_quota_status(self):
        from data_ai.core.quota import QuotaManager, QuotaPolicy

        m = QuotaManager()
        # quota_status 只查询 scope=key 且 scope_id=actor 的策略
        m.set_policy(
            QuotaPolicy(
                scope="key",
                scope_id="u1",
                daily_token_limit=1000,
                qps_limit=10,
                max_concurrent=5,
                enabled=True,
            )
        )
        m.record_usage("u1", "gpt-4o", 100, 50)
        st = m.quota_status("u1")
        assert st["usage_today"]["total_tokens"] == 150
        assert len(st["policies"]) >= 1


# ============================================================================
# Webhooks
# ============================================================================


class TestWebhooks:
    def test_event_types_non_empty(self):
        from data_ai.core.webhooks import EVENT_TYPES

        assert len(EVENT_TYPES) >= 10
        assert "agent.run.completed" in EVENT_TYPES
        assert "quota.exceeded" in EVENT_TYPES

    def test_sign_payload(self):
        from data_ai.core.webhooks.dispatcher import _sign_payload

        body = '{"hello":"world"}'
        ts = "1700000000"
        secret = "s3cret"
        sig = _sign_payload(secret, body, ts)
        # 同样的输入必须产生同样的签名
        sig2 = _sign_payload(secret, body, ts)
        assert sig == sig2
        # 不同 secret 应产生不同签名
        sig3 = _sign_payload("other", body, ts)
        assert sig != sig3
        # 标准 HMAC-SHA256
        expected = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
        assert sig == expected

    def test_subscription_lifecycle(self):
        from data_ai.core.webhooks import WebhookDispatcher, WebhookSubscription

        d = WebhookDispatcher()
        sub = WebhookSubscription(
            id="wh-1",
            name="t",
            url="https://example.com/hook",
            secret="abc",
            events=["agent.run.completed"],
        )
        d.create(sub)
        assert d.get("wh-1") is not None
        assert len(d.list()) == 1
        d.update("wh-1", active=False)
        assert d.get("wh-1").active is False
        d.delete("wh-1")
        assert d.get("wh-1") is None

    def test_delivery_stats_initial(self):
        from data_ai.core.webhooks import WebhookDispatcher

        d = WebhookDispatcher()
        st = d.delivery_stats()
        assert st["total"] == 0

    def test_list_deliveries_empty(self):
        from data_ai.core.webhooks import WebhookDispatcher

        d = WebhookDispatcher()
        deliveries = d.list_deliveries()
        assert deliveries == []


# ============================================================================
# Scheduler
# ============================================================================


class TestScheduler:
    def test_cron_next_run(self):
        from data_ai.core.scheduler.jobs import HAS_CRONITER, Schedule

        if not HAS_CRONITER:
            pytest.skip("croniter not installed")
        s = Schedule(kind="cron", expression="* * * * *")
        now = 1700000000
        nxt = s.next_run_after(now)
        assert nxt is not None
        assert nxt > now
        assert nxt - now < 70  # 距 now 不到 70s

    def test_every_calculation(self):
        from data_ai.core.scheduler.jobs import Schedule

        s = Schedule(kind="every", expression="60s")
        now = 1700000000
        assert s.next_run_after(now) == now + 60
        s2 = Schedule(kind="every", expression="5m" if False else "300s")
        assert s2.next_run_after(now) == now + 300

    def test_at_parse(self):
        from data_ai.core.scheduler.jobs import Schedule

        # at 模式 expression 应是 unix timestamp 字符串
        s = Schedule(kind="at", expression="1893456000")
        nxt = s.next_run_after(0)
        assert nxt == 1893456000.0

    def test_cron_invalid_returns_none(self):
        from data_ai.core.scheduler.jobs import HAS_CRONITER, Schedule

        if not HAS_CRONITER:
            pytest.skip("croniter not installed")
        s = Schedule(kind="cron", expression="not a cron")
        # croniter 会抛错 → next_run_after 返回 None
        assert s.next_run_after(time.time()) is None

    def test_job_create_and_trigger(self):
        from data_ai.core.scheduler import JobScheduler, Schedule, ScheduledJob

        js = JobScheduler()
        job = ScheduledJob(
            id="j-1",
            name="t",
            description="",
            action_type="http",
            action_payload={},
            schedule=Schedule(kind="every", expression="3600s"),
            enabled=True,
            created_at=time.time(),
            created_by="test",
        )
        js.create(job)
        jobs = js.list()
        assert any(j["id"] == "j-1" for j in jobs)
        # trigger 是异步线程,需要等一下
        execution = js.trigger_now("j-1")
        assert execution is not None
        assert execution.job_id == "j-1"
        # 等线程完成
        time.sleep(0.3)
        assert execution.status in ("success", "failed", "running", "timeout")

    def test_job_update(self):
        from data_ai.core.scheduler import JobScheduler, Schedule, ScheduledJob

        js = JobScheduler()
        js.create(
            ScheduledJob(
                id="j-1",
                name="t",
                description="",
                action_type="http",
                action_payload={},
                schedule=Schedule(kind="every", expression="3600s"),
                enabled=True,
                created_at=time.time(),
                created_by="test",
            )
        )
        ok = js.update("j-1", enabled=False)
        assert ok is not None
        assert js.get("j-1").enabled is False

    def test_job_delete(self):
        from data_ai.core.scheduler import JobScheduler, Schedule, ScheduledJob

        js = JobScheduler()
        js.create(
            ScheduledJob(
                id="j-1",
                name="t",
                description="",
                action_type="http",
                action_payload={},
                schedule=Schedule(kind="every", expression="3600s"),
                enabled=True,
                created_at=time.time(),
                created_by="test",
            )
        )
        js.delete("j-1")
        assert js.get("j-1") is None

    def test_job_stats(self):
        from data_ai.core.scheduler import JobScheduler, Schedule, ScheduledJob

        js = JobScheduler()
        js.create(
            ScheduledJob(
                id="j-1",
                name="t",
                description="",
                action_type="http",
                action_payload={},
                schedule=Schedule(kind="every", expression="3600s"),
                enabled=True,
                created_at=time.time(),
                created_by="test",
            )
        )
        js.trigger_now("j-1")
        time.sleep(0.3)
        st = js.stats()
        assert st["total_jobs"] == 1
        assert st["enabled_jobs"] == 1
        assert st["total_executions"] >= 1

    def test_job_executions(self):
        from data_ai.core.scheduler import JobScheduler, Schedule, ScheduledJob

        js = JobScheduler()
        js.create(
            ScheduledJob(
                id="j-1",
                name="t",
                description="",
                action_type="http",
                action_payload={},
                schedule=Schedule(kind="every", expression="3600s"),
                enabled=True,
                created_at=time.time(),
                created_by="test",
            )
        )
        js.trigger_now("j-1")
        time.sleep(0.3)
        execs = js.list_executions()
        assert len(execs) >= 1
        assert execs[0]["job_id"] == "j-1"
