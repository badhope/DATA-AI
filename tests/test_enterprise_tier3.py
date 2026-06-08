"""P1-12 企业级 Tier 3 测试: 跨区域复制 / 灾备恢复 / SLA 赔付"""

from __future__ import annotations

import time

import pytest

from data_ai.core.recovery import (
    BackupType,
    DrillResult,
    RestoreStatus,
    get_recovery_engine,
    reset_recovery_engine,
)
from data_ai.core.replication import (
    FailoverMode,
    FailoverState,
    ReplicationMode,
    StreamState,
    get_replication_engine,
    reset_replication_engine,
)
from data_ai.core.sla import (
    BreachSeverity,
    CreditStatus,
    DisputeStatus,
    get_compensation_engine,
    reset_compensation_engine,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_replication_engine()
    reset_recovery_engine()
    reset_compensation_engine()
    yield
    reset_replication_engine()
    reset_recovery_engine()
    reset_compensation_engine()


# ───────────────────────── Replication ─────────────────────────


class TestReplicationPolicy:
    def test_create_policy(self):
        e = get_replication_engine()
        p = e.create_policy("CN->US", "cn-east", "us-west", mode=ReplicationMode.ASYNC)
        assert p.id.startswith("rp-")
        assert p.source_region == "cn-east"
        assert p.target_region == "us-west"
        assert p.mode == ReplicationMode.ASYNC
        # stream 自动创建
        streams = e.list_streams(policy_id=p.id)
        assert len(streams) == 1
        assert streams[0].state == StreamState.HEALTHY

    def test_list_policies_filter(self):
        e = get_replication_engine()
        e.create_policy("p1", "cn-east", "us-west")
        e.create_policy("p2", "us-west", "eu-central")
        e.create_policy("p3", "cn-east", "eu-central")
        cn_pol = e.list_policies(source_region="cn-east")
        assert len(cn_pol) == 2

    def test_delete_policy(self):
        e = get_replication_engine()
        p = e.create_policy("p1", "a", "b")
        assert e.delete_policy(p.id) is True
        assert e.delete_policy(p.id) is False

    def test_disabled_flag(self):
        e = get_replication_engine()
        p = e.create_policy("p", "a", "b")
        e.delete_policy(p.id)
        e.create_policy("p2", "a", "b", metadata={"x": 1})


class TestReplicaStream:
    def test_record_sync_healthy(self):
        e = get_replication_engine()
        p = e.create_policy("p", "a", "b", max_lag_sec=5.0)
        s = e.list_streams(policy_id=p.id)[0]
        e.record_sync(s.id, records=100, bytes_sent=10000, lag_sec=1.0)
        assert s.records_sent == 100
        assert s.bytes_sent == 10000
        assert s.state == StreamState.HEALTHY

    def test_lag_threshold_triggers_lagging(self):
        e = get_replication_engine()
        p = e.create_policy("p", "a", "b", max_lag_sec=2.0)
        s = e.list_streams(policy_id=p.id)[0]
        e.record_sync(s.id, records=10, bytes_sent=100, lag_sec=5.0)
        assert s.state == StreamState.LAGGING

    def test_recovery_from_lag(self):
        e = get_replication_engine()
        p = e.create_policy("p", "a", "b", max_lag_sec=2.0)
        s = e.list_streams(policy_id=p.id)[0]
        e.record_sync(s.id, records=10, bytes_sent=100, lag_sec=5.0)
        assert s.state == StreamState.LAGGING
        e.record_sync(s.id, records=10, bytes_sent=100, lag_sec=0.5)
        assert s.state == StreamState.HEALTHY

    def test_repeated_failures_escalate(self):
        e = get_replication_engine()
        p = e.create_policy("p", "a", "b")
        s = e.list_streams(policy_id=p.id)[0]
        e.record_failure(s.id, "net error")
        e.record_failure(s.id, "net error")
        e.record_failure(s.id, "net error")
        assert s.state == StreamState.DEGRADED
        for _ in range(7):
            e.record_failure(s.id, "net error")
        assert s.state == StreamState.FAILED

    def test_pause_resume(self):
        e = get_replication_engine()
        p = e.create_policy("p", "a", "b")
        s = e.list_streams(policy_id=p.id)[0]
        e.pause_stream(s.id)
        assert s.state == StreamState.PAUSED
        e.resume_stream(s.id)
        assert s.state == StreamState.HEALTHY


class TestFailover:
    def test_initiate_and_complete(self):
        e = get_replication_engine()
        fo = e.initiate_failover("cn-east", "us-west", FailoverMode.PLANNED, reason="test")
        assert fo.state == FailoverState.INITIATED
        assert e._active_region == "cn-east"  # 还没切
        e.advance_failover(fo.id, FailoverState.DRAINING, "traffic shifting")
        e.advance_failover(fo.id, FailoverState.PROMOTING, "promoting standby")
        ev = e.complete_failover(fo.id, success=True, data_loss_records=0, notes="clean")
        assert ev.state == FailoverState.SWITCHED
        assert e._active_region == "us-west"
        assert ev.duration_sec >= 0

    def test_rollback(self):
        e = get_replication_engine()
        fo = e.initiate_failover("a", "b", FailoverMode.PLANNED)
        e.complete_failover(fo.id, success=True)
        assert e._active_region == "b"
        e.rollback_failover(fo.id, "false alarm")
        assert e._active_region == "a"
        assert fo.state == FailoverState.ROLLED_BACK

    def test_emergency_no_rollback(self):
        e = get_replication_engine()
        fo = e.initiate_failover("a", "b", FailoverMode.EMERGENCY)
        e.complete_failover(fo.id, success=True)
        with pytest.raises(ValueError):
            e.rollback_failover(fo.id)

    def test_drill_does_not_switch_active(self):
        e = get_replication_engine()
        # 默认 active_region 是 "cn-east" (engine 初始值)
        before = e._active_region
        fo = e.initiate_failover(before, "us-west", FailoverMode.DRILL)
        e.complete_failover(fo.id, success=True)
        assert e._active_region == before  # drill 不切
        assert fo.state == FailoverState.SWITCHED

    def test_list_failovers(self):
        e = get_replication_engine()
        e.initiate_failover("a", "b", FailoverMode.PLANNED)
        e.initiate_failover("c", "d", FailoverMode.EMERGENCY)
        all_fo = e.list_failovers()
        assert len(all_fo) == 2
        plan_fo = e.list_failovers(mode=FailoverMode.PLANNED)
        assert len(plan_fo) == 1


class TestQuorumGuard:
    def test_majority_writable(self):
        e = get_replication_engine()
        r = e.check_quorum("cn-east", 3, 2)
        assert r["ok"] is True
        assert r["can_write"] is True
        assert r["ratio"] == pytest.approx(0.6667, rel=1e-3)

    def test_minority_readonly(self):
        e = get_replication_engine()
        r = e.check_quorum("cn-east", 3, 1)
        assert r["ok"] is False
        assert r["can_write"] is False
        assert r["recommendation"] == "switch_to_read_only"

    def test_no_replicas(self):
        e = get_replication_engine()
        r = e.check_quorum("cn-east", 0, 0)
        assert r["ok"] is False


class TestReplicationStats:
    def test_stats(self):
        e = get_replication_engine()
        p = e.create_policy("p1", "a", "b", max_lag_sec=2.0)
        s = e.list_streams(policy_id=p.id)[0]
        e.record_sync(s.id, 100, 1000)
        e.initiate_failover("a", "b")
        st = e.stats()
        assert st["total_policies"] == 1
        assert st["total_streams"] == 1
        assert st["total_failovers"] == 1
        assert st["total_records_replicated"] == 100
        assert "healthy" in st["stream_states"]


# ───────────────────────── Recovery ─────────────────────────


class TestBackupSchedule:
    def test_create_schedule(self):
        e = get_recovery_engine()
        s = e.create_schedule("daily-full", backup_type=BackupType.FULL, retention_days=7)
        assert s.id.startswith("bs-")
        assert s.next_run_at > 0

    def test_enable_disable(self):
        e = get_recovery_engine()
        s = e.create_schedule("p1")
        assert s.enabled is True
        e.set_schedule_enabled(s.id, False)
        assert s.enabled is False

    def test_list_filter(self):
        e = get_recovery_engine()
        e.create_schedule("a")
        e.create_schedule("b")
        e.set_schedule_enabled(e.list_schedules()[0].id, False)
        all_s = e.list_schedules()
        enabled = e.list_schedules(enabled=True)
        assert len(all_s) == 2
        assert len(enabled) == 1


class TestBackupExecution:
    def test_trigger_backup(self):
        e = get_recovery_engine()
        s = e.create_schedule("p", backup_type=BackupType.FULL)
        b = e.trigger_backup(s.id, record_count=500)
        assert b.status.value == "success"
        assert b.size_bytes > 0
        assert b.checksum != ""
        assert b.record_count == 500
        assert b.encrypted is True

    def test_verify_backup(self):
        e = get_recovery_engine()
        s = e.create_schedule("p")
        b = e.trigger_backup(s.id, record_count=10)
        v = e.verify_backup(b.id)
        assert v["ok"] is True
        assert v["size_bytes"] == b.size_bytes

    def test_verify_missing(self):
        e = get_recovery_engine()
        v = e.verify_backup("bk-bogus")
        assert v["ok"] is False

    def test_expire_old(self):
        e = get_recovery_engine()
        s = e.create_schedule("p", retention_days=-1)  # 立即过期
        e.trigger_backup(s.id)
        count = e.expire_old_backups()
        assert count == 1


class TestRestore:
    def test_create_and_advance(self):
        e = get_recovery_engine()
        s = e.create_schedule("p")
        b = e.trigger_backup(s.id, record_count=100)
        j = e.create_restore(b.id, requested_by="admin", reason="disaster")
        assert j.status == RestoreStatus.PENDING
        e.advance_restore(j.id, RestoreStatus.RUNNING, progress_pct=50.0, records_restored=50)
        e.advance_restore(j.id, RestoreStatus.SUCCESS, progress_pct=100.0, records_restored=100, validation_passed=True)
        assert j.status == RestoreStatus.SUCCESS
        assert j.progress_pct == 100.0

    def test_restore_unusable_backup_fails(self):
        e = get_recovery_engine()
        s = e.create_schedule("p")
        b = e.trigger_backup(s.id)
        b.status = b.status  # keep success
        b.status = b.status.__class__("failed")  # simulate failure
        e._backups[b.id] = b
        with pytest.raises(ValueError):
            e.create_restore(b.id)


class TestDRDrill:
    def test_pass(self):
        e = get_recovery_engine()
        s = e.create_schedule("p")
        e.trigger_backup(s.id, record_count=100)
        d = e.run_drill("Q1", schedule_id=s.id, conducted_by="sre-team")
        assert d.result in (DrillResult.PASS, DrillResult.PASS_WITH_ISSUES)
        assert d.rto_actual_sec >= 0
        assert d.rpo_actual_sec >= 0

    def test_no_backup_fails(self):
        e = get_recovery_engine()
        with pytest.raises(ValueError):
            e.run_drill("d1", schedule_id="bs-nope")

    def test_list_drills_filter(self):
        e = get_recovery_engine()
        s = e.create_schedule("p")
        e.trigger_backup(s.id)
        e.run_drill("d1", schedule_id=s.id)
        e.run_drill("d2", schedule_id=s.id)
        all_d = e.list_drills()
        assert len(all_d) == 2


class TestRetentionHold:
    def test_create_hold(self):
        e = get_recovery_engine()
        h = e.create_hold("res-1", "gdpr", "preserve", reason="legal")
        assert h.id.startswith("rh-")
        assert h.released_at == 0.0

    def test_release_hold(self):
        e = get_recovery_engine()
        h = e.create_hold("res-1", "gdpr", "preserve")
        e.release_hold(h.id)
        assert h.released_at > 0

    def test_blocked_action(self):
        e = get_recovery_engine()
        e.create_hold("res-x", "gdpr", "preserve")
        r = e.check_resource_action("res-x", "delete")
        assert r["blocked"] is True

    def test_erase_action_allows_delete(self):
        e = get_recovery_engine()
        e.create_hold("res-x", "gdpr", "erase", reason="right to erasure")
        r = e.check_resource_action("res-x", "delete")
        assert r["blocked"] is False

    def test_no_hold(self):
        e = get_recovery_engine()
        r = e.check_resource_action("res-y", "delete")
        assert r["blocked"] is False


class TestRecoveryStats:
    def test_stats(self):
        e = get_recovery_engine()
        s = e.create_schedule("p")
        e.trigger_backup(s.id)
        e.create_hold("r1", "hipaa")
        e.run_drill("d", schedule_id=s.id)
        st = e.stats()
        assert st["total_schedules"] == 1
        assert st["total_backups"] == 1
        assert st["total_holds"] == 1
        assert st["active_holds"] == 1
        assert st["total_drills"] == 1


# ───────────────────────── Compensation ─────────────────────────


class TestCompensationPolicy:
    def test_default_policy_exists(self):
        e = get_compensation_engine()
        ps = e.list_policies()
        assert len(ps) >= 1
        assert any(p.plan_tier == "enterprise" for p in ps)

    def test_create_custom(self):
        e = get_compensation_engine()
        p = e.create_policy("Pro 99.5%", plan_tier="pro", target_availability_pct=99.5)
        assert p.id.startswith("cp-")
        assert p.target_availability_pct == 99.5

    def test_credit_tier_lookup(self):
        e = get_compensation_engine()
        p = e.find_policy_for_plan("enterprise")
        assert p is not None
        # 99.5% 落在 99.5-99.9 档 (赔 10%)
        pct, _ = p.calculate_credit_pct(99.5)
        assert pct == 10.0
        # 99.0% 落在 99.0-99.5 档 (赔 25%)
        pct, _ = p.calculate_credit_pct(99.0)
        assert pct == 25.0
        # 100% (达标) 赔 0
        pct, _ = p.calculate_credit_pct(100.0)
        assert pct == 0.0


class TestBreach:
    def test_detect_breach_severity(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        # 偏差 0.05% → low
        b1 = e.detect_breach(p.id, "tnt-1", 99.85, downtime_sec=60)
        assert b1.severity == BreachSeverity.LOW
        # 偏差 1% → medium
        b2 = e.detect_breach(p.id, "tnt-1", 98.9, downtime_sec=3600)
        assert b2.severity == BreachSeverity.MEDIUM
        # 偏差 5% → high
        b3 = e.detect_breach(p.id, "tnt-1", 94.9, downtime_sec=36000)
        assert b3.severity == BreachSeverity.HIGH
        # 偏差 10% → critical
        b4 = e.detect_breach(p.id, "tnt-1", 89.0, downtime_sec=86400 * 4)
        assert b4.severity == BreachSeverity.CRITICAL

    def test_list_filter(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        e.detect_breach(p.id, "tnt-A", 99.5)
        e.detect_breach(p.id, "tnt-B", 99.0)
        b_a = e.list_breaches(tenant_id="tnt-A")
        assert len(b_a) == 1
        assert b_a[0].tenant_id == "tnt-A"


class TestCreditCalculation:
    def test_credit_amount(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        b = e.detect_breach(p.id, "tnt-1", 99.5, downtime_sec=14400)
        c = e.calculate_credit(b.id, monthly_fee_usd=10000.0)
        # 99.5% → 10% credit → $1000
        assert c.credit_pct == 10.0
        assert c.credit_amount_usd == pytest.approx(1000.0)
        assert c.base_amount_usd == 10000.0

    def test_auto_approve(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        assert p.auto_apply is True
        b = e.detect_breach(p.id, "tnt-1", 99.5)
        c = e.calculate_credit(b.id, 1000.0)
        assert c.status == CreditStatus.APPROVED
        assert c.approved_by == "auto"

    def test_no_credit_above_target(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        b = e.detect_breach(p.id, "tnt-1", 100.0)  # 达标
        with pytest.raises(ValueError):
            e.calculate_credit(b.id, 1000.0)

    def test_apply_and_pay_lifecycle(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        b = e.detect_breach(p.id, "tnt-1", 99.5)
        c = e.calculate_credit(b.id, 1000.0)
        # auto-apply → APPROVED
        assert c.status == CreditStatus.APPROVED
        e.apply_credit(c.id)
        assert c.status == CreditStatus.APPLIED
        e.mark_paid(c.id)
        assert c.status == CreditStatus.PAID

    def test_reject_credit(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        b = e.detect_breach(p.id, "tnt-1", 99.5)
        c = e.calculate_credit(b.id, 1000.0)
        e.reject_credit(c.id, reason="not our fault")
        assert c.status == CreditStatus.REJECTED


class TestDispute:
    def test_raise_dispute(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        b = e.detect_breach(p.id, "tnt-1", 99.5)
        c = e.calculate_credit(b.id, 1000.0)
        d = e.raise_dispute(c.id, "tnt-1", "cust-1", "want more", evidence={"plan": "ent+"})
        assert d.status == DisputeStatus.OPEN
        assert c.status == CreditStatus.DISPUTED

    def test_resolve_uphold(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        b = e.detect_breach(p.id, "tnt-1", 99.5)
        c = e.calculate_credit(b.id, 1000.0)
        d = e.raise_dispute(c.id, "tnt-1", "cust-1", "want more")
        e.resolve_dispute(d.id, "reviewed and upheld", uphold_credit=True)
        assert d.status == DisputeStatus.RESOLVED
        assert c.status == CreditStatus.APPROVED

    def test_resolve_reject(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        b = e.detect_breach(p.id, "tnt-1", 99.5)
        c = e.calculate_credit(b.id, 1000.0)
        d = e.raise_dispute(c.id, "tnt-1", "cust-1", "want more")
        e.resolve_dispute(d.id, "claim invalid", uphold_credit=False)
        assert d.status == DisputeStatus.REJECTED
        assert c.status == CreditStatus.REJECTED


class TestCompensationReporting:
    def test_tenant_summary(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        b1 = e.detect_breach(p.id, "tnt-1", 99.5, downtime_sec=14400)
        c1 = e.calculate_credit(b1.id, 10000.0)
        e.apply_credit(c1.id)
        start = time.time() - 86400
        end = time.time() + 86400
        s = e.tenant_summary("tnt-1", start, end)
        assert s["total_breaches"] == 1
        assert s["total_credits"] == 1
        assert s["total_credit_amount_usd"] == pytest.approx(1000.0)
        assert s["applied_credit_amount_usd"] == pytest.approx(1000.0)
        assert s["avg_actual_availability_pct"] == pytest.approx(99.5)

    def test_stats(self):
        e = get_compensation_engine()
        p = e.list_policies()[0]
        b = e.detect_breach(p.id, "tnt-1", 99.5)
        e.calculate_credit(b.id, 1000.0)
        st = e.stats()
        assert st["total_policies"] >= 1
        assert st["total_breaches"] == 1
        assert st["total_credits"] == 1
        assert st["total_credit_amount_usd"] > 0


# ───────────────────────── API smoke ─────────────────────────


class TestAPISmoke:
    def test_engine_integration(self):
        """端到端串联: replication + recovery + compensation 联动"""
        r = get_replication_engine()
        rec = get_recovery_engine()
        comp = get_compensation_engine()

        # 1. 建复制策略
        p = r.create_policy("p", "cn-east", "us-west", ReplicationMode.ASYNC)
        # 2. 模拟多次失败触发 degraded
        s = r.list_streams(policy_id=p.id)[0]
        for _ in range(3):
            r.record_failure(s.id, "net issue")
        assert s.state == StreamState.DEGRADED
        # 3. 灾备切换
        fo = r.initiate_failover("cn-east", "us-west", FailoverMode.EMERGENCY, reason="replication failed")
        r.complete_failover(fo.id, success=True, data_loss_records=10)
        # 4. 触发 DR 演练
        sched = rec.create_schedule("post-failover")
        b = rec.trigger_backup(sched.id, record_count=1000)
        rec.run_drill("post-drill", backup_id=b.id)
        # 5. 报 SLA 违约
        comp_p = comp.list_policies()[0]
        breach = comp.detect_breach(comp_p.id, "tnt-1", 99.0, downtime_sec=14400 * 5)
        credit = comp.calculate_credit(breach.id, 50000.0)
        assert credit.credit_amount_usd > 0
        # 6. 客户争议
        d = comp.raise_dispute(credit.id, "tnt-1", "cust", "downtime longer than reported")
        comp.resolve_dispute(d.id, "additional evidence", uphold_credit=True)
        # 一切都通过
        assert r._active_region == "us-west"
        assert rec.stats()["total_drills"] == 1
        assert comp.stats()["total_disputes"] == 1
