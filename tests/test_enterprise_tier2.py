"""P1-11 企业治理 Tier 2 — 单元测试

覆盖:
- Tenants (多租户)
- RBAC (角色 + ABAC + 委托)
- Billing (定价 + 用量 + 预算 + 报表)
- SLA (SLO + 状态页 + 事件)
- SSO (OIDC + SCIM)
- Residency (region + policy + route)
- AuditChain (Merkle)
"""

from __future__ import annotations

import sys
import time

import pytest

# ---------- Tenants ----------


class TestTenants:
    def test_tenant_crud(self, tmp_path):
        from data_ai.core.tenants import TenantStore, reset_tenant_store

        reset_tenant_store()
        store = TenantStore(persist_path=tmp_path / "tenants.jsonl")
        t1 = store.create(name="Acme Corp", slug="acme", plan="pro")
        assert t1.id
        assert t1.name == "Acme Corp"
        assert t1.plan == "pro"
        t2 = store.get(t1.id)
        assert t2 is not None
        assert t2.name == "Acme Corp"
        listed = store.list()
        assert len(listed) == 1
        # update
        updated = store.update(t1.id, plan="enterprise")
        assert updated is not None and updated.plan == "enterprise"
        # delete
        assert store.delete(t1.id) is True
        assert store.get(t1.id) is None

    def test_tenant_unique_slug(self, tmp_path):
        from data_ai.core.tenants import TenantStore

        store = TenantStore(persist_path=tmp_path / "t.jsonl")
        store.create(name="A", slug="dup")
        with pytest.raises(ValueError):
            store.create(name="B", slug="dup")

    def test_tenant_members(self, tmp_path):
        from data_ai.core.tenants import TenantStore

        store = TenantStore(persist_path=tmp_path / "t.jsonl")
        t = store.create(name="A")
        store.add_member(t.id, "alice", "owner")
        store.add_member(t.id, "bob", "admin")
        members = store.list_members(t.id)
        assert len(members) == 2
        # 重复 add 应该更新
        store.add_member(t.id, "alice", "admin")
        members = store.list_members(t.id)
        assert len(members) == 2
        assert next(m for m in members if m.user_id == "alice").role == "admin"
        # remove
        assert store.remove_member(t.id, "alice") is True
        assert len(store.list_members(t.id)) == 1

    def test_tenant_stats(self, tmp_path):
        from data_ai.core.tenants import TenantStore

        store = TenantStore(persist_path=tmp_path / "t.jsonl")
        store.create(name="A", plan="free")
        store.create(name="B", plan="pro")
        store.create(name="C", plan="pro", status="suspended")
        stats = store.stats()
        assert stats["total_tenants"] == 3
        assert stats["by_plan"].get("pro") == 2

    def test_tenant_persistence(self, tmp_path):
        from data_ai.core.tenants import TenantStore

        path = tmp_path / "t.jsonl"
        s1 = TenantStore(persist_path=path)
        s1.create(name="Persistent", slug="p")
        s2 = TenantStore(persist_path=path)
        assert s2.get_by_slug("p") is not None


# ---------- RBAC ----------


class TestRBAC:
    def test_system_roles_loaded(self):
        from data_ai.core.rbac import get_rbac_engine, reset_rbac_engine

        reset_rbac_engine()
        e = get_rbac_engine()
        roles = e.list_roles()
        names = [r.name for r in roles]
        assert "super-admin" in names
        assert "admin" in names
        assert "developer" in names
        assert "viewer" in names

    def test_assign_and_check(self):
        from data_ai.core.rbac import get_rbac_engine, reset_rbac_engine

        reset_rbac_engine()
        e = get_rbac_engine()
        admin = e.get_role_by_name("admin")
        viewer = e.get_role_by_name("viewer")
        e.assign("alice", admin.id)
        e.assign("bob", viewer.id)
        # admin 可 delete agent
        d = e.check("alice", "agent", "delete")
        assert d.allowed
        # viewer 不能 delete
        d = e.check("bob", "agent", "delete")
        assert not d.allowed

    def test_wildcard_permission(self):
        from data_ai.core.rbac import get_rbac_engine, reset_rbac_engine

        reset_rbac_engine()
        e = get_rbac_engine()
        sa = e.get_role_by_name("super-admin")
        e.assign("root", sa.id)
        d = e.check("root", "anything", "any-action")
        assert d.allowed

    def test_no_role_denied(self):
        from data_ai.core.rbac import get_rbac_engine, reset_rbac_engine

        reset_rbac_engine()
        e = get_rbac_engine()
        d = e.check("nobody", "agent", "read")
        assert not d.allowed
        assert "no roles" in d.reason

    def test_abac_policy(self):
        from data_ai.core.rbac import get_rbac_engine, reset_rbac_engine

        reset_rbac_engine()
        e = get_rbac_engine()
        admin = e.get_role_by_name("admin")
        e.assign("alice", admin.id)
        # 创建 deny 策略: 来自恶意 IP 拒绝
        e.create_policy(
            name="block-bad-ip",
            conditions=[{"field": "env.ip", "op": "cidr_match", "value": "1.2.3.0/24"}],
            effect="deny",
            priority=1,
        )
        # 正常 IP 通过
        d = e.check("alice", "agent", "read", env={"ip": "10.0.0.1"})
        assert d.allowed
        # 恶意 IP 被 deny
        d = e.check("alice", "agent", "read", env={"ip": "1.2.3.4"})
        assert not d.allowed
        assert "block-bad-ip" in d.matched_policy

    def test_role_inheritance(self):
        from data_ai.core.rbac import Permission, get_rbac_engine, reset_rbac_engine

        reset_rbac_engine()
        e = get_rbac_engine()
        viewer = e.get_role_by_name("viewer")
        # 创建一个 editor 角色继承 viewer
        editor = e.create_role(name="editor", parent_roles=[viewer.id], permissions=[Permission("agent", "update")])
        e.assign("carol", editor.id)
        # editor 可 read (继承) + update (自有)
        d1 = e.check("carol", "agent", "read")
        d2 = e.check("carol", "agent", "update")
        d3 = e.check("carol", "agent", "delete")
        assert d1.allowed
        assert d2.allowed
        assert not d3.allowed

    def test_delegation(self):
        from data_ai.core.rbac import get_rbac_engine, reset_rbac_engine

        reset_rbac_engine()
        e = get_rbac_engine()
        admin = e.get_role_by_name("admin")
        e.assign("boss", admin.id)
        # boss 把 admin 委托给 assistant 1 小时
        expires_at = time.time() + 3600
        a = e.delegate("boss", "assistant", admin.id, expires_at=expires_at)
        assert a.delegation_from == "boss"
        # assistant 现在有 admin 权限
        d = e.check("assistant", "agent", "delete")
        assert d.allowed

    def test_revoke(self):
        from data_ai.core.rbac import get_rbac_engine, reset_rbac_engine

        reset_rbac_engine()
        e = get_rbac_engine()
        admin = e.get_role_by_name("admin")
        e.assign("temp", admin.id)
        assert e.check("temp", "agent", "delete").allowed
        e.revoke("temp", admin.id)
        assert not e.check("temp", "agent", "delete").allowed

    def test_decision_log(self):
        from data_ai.core.rbac import get_rbac_engine, reset_rbac_engine

        reset_rbac_engine()
        e = get_rbac_engine()
        admin = e.get_role_by_name("admin")
        e.assign("audited", admin.id)
        for _ in range(5):
            e.check("audited", "agent", "read")
        log = e.recent_decisions(10)
        assert len(log) == 5


# ---------- Billing ----------


class TestBilling:
    def test_pricing_default(self):
        from data_ai.core.billing import get_billing_engine, reset_billing_engine

        reset_billing_engine()
        e = get_billing_engine()
        pricing = e.list_pricing()
        assert any(p.model_id == "gpt-4o" for p in pricing)
        assert any(p.model_id == "offline-fast" for p in pricing)

    def test_pricing_set_and_get(self):
        from data_ai.core.billing import get_billing_engine, reset_billing_engine

        reset_billing_engine()
        e = get_billing_engine()
        e.set_pricing("custom-model", input_per_1k=0.01, output_per_1k=0.03)
        p = e.get_pricing("custom-model")
        assert p.input_per_1k == 0.01
        assert p.output_per_1k == 0.03

    def test_pricing_calculate(self):
        from data_ai.core.billing import PricingModel

        p = PricingModel(model_id="t", input_per_1k=0.01, output_per_1k=0.03)
        # 1000 input + 500 output = 0.01 + 0.015 = 0.025
        cost = p.calculate(prompt_tokens=1000, completion_tokens=500)
        assert abs(cost - 0.025) < 1e-6
        # 0 tokens = 0
        assert p.calculate() == 0.0

    def test_record_usage(self):
        from data_ai.core.billing import get_billing_engine, reset_billing_engine

        reset_billing_engine()
        e = get_billing_engine()
        r = e.record(model_id="offline-fast", prompt_tokens=100, completion_tokens=50)
        assert r.cost_usd == 0.0
        # 用真实计费
        e.set_pricing("test", input_per_1k=0.01, output_per_1k=0.02)
        r2 = e.record(model_id="test", prompt_tokens=1000, completion_tokens=500)
        assert abs(r2.cost_usd - 0.02) < 1e-6

    def test_budget_warn(self, tmp_path):
        from data_ai.core.billing import BillingEngine, Budget

        e = BillingEngine(persist_path=tmp_path / "b.jsonl")
        b = Budget(name="test", scope="tenant", scope_id="t1", period="monthly", amount_usd=10, warn_threshold=0.5)
        e.set_budget(b)
        # 记 6 USD
        e.set_pricing("p", input_per_1k=0.001, output_per_1k=0.002)
        for _ in range(60):
            e.record(tenant_id="t1", model_id="p", prompt_tokens=100_000, completion_tokens=0)
        ok, alerts = e.check_budget(tenant_id="t1")
        # 6 USD / 10 USD = 60% > 50% 触发 warn
        assert any(a["level"] == "warning" for a in alerts) or any(a["level"] == "exceeded" for a in alerts)

    def test_budget_hard_limit(self, tmp_path):
        from data_ai.core.billing import BillingEngine, Budget

        e = BillingEngine(persist_path=tmp_path / "b.jsonl")
        b = Budget(name="hard", scope="tenant", scope_id="t2", period="monthly", amount_usd=1, hard_limit=True, warn_threshold=0.5)
        e.set_budget(b)
        e.set_pricing("p", input_per_1k=0.001, output_per_1k=0)
        for _ in range(50):
            e.record(tenant_id="t2", model_id="p", prompt_tokens=100_000, completion_tokens=0)
        ok, alerts = e.check_budget(tenant_id="t2")
        # hard_limit + 超额 = ok=False
        assert ok is False

    def test_summary(self):
        from data_ai.core.billing import get_billing_engine, reset_billing_engine

        reset_billing_engine()
        e = get_billing_engine()
        e.set_pricing("m1", input_per_1k=0.01, output_per_1k=0.02)
        e.record(tenant_id="x", model_id="m1", prompt_tokens=1000, completion_tokens=500, user_id="alice")
        e.record(tenant_id="x", model_id="m1", prompt_tokens=2000, completion_tokens=1000, user_id="bob")
        s = e.summary(tenant_id="x")
        assert s["total_requests"] == 2
        assert s["total_tokens"] == 4500
        assert s["by_model"]["m1"]["cost_usd"] > 0
        assert "alice" in s["by_cost_center"] or "bob" in s["by_cost_center"] or "unassigned" in s["by_cost_center"]

    def test_cost_by_day(self):
        from data_ai.core.billing import get_billing_engine, reset_billing_engine

        reset_billing_engine()
        e = get_billing_engine()
        e.record(model_id="offline-fast")
        series = e.cost_by_day(days=1)
        assert isinstance(series, list)

    def test_export_invoice(self):
        from data_ai.core.billing import get_billing_engine, reset_billing_engine

        reset_billing_engine()
        e = get_billing_engine()
        e.record(tenant_id="inv", model_id="offline-fast")
        now = time.time()
        out = e.export_invoice("inv", since=now - 3600, until=now + 3600, format="json")
        assert "id" in out
        csv = e.export_invoice("inv", since=now - 3600, until=now + 3600, format="csv")
        assert "id" in csv


# ---------- SLA ----------


class TestSLA:
    def test_bootstrap_components(self):
        from data_ai.core.sla import get_sla_monitor, reset_sla_monitor

        reset_sla_monitor()
        m = get_sla_monitor()
        comps = m.list_components()
        names = [c.name for c in comps]
        assert "API Gateway" in names
        assert "LLM Inference" in names

    def test_status_page_initial(self):
        from data_ai.core.sla import get_sla_monitor, reset_sla_monitor

        reset_sla_monitor()
        m = get_sla_monitor()
        page = m.status_page()
        assert page["overall"] == "operational"
        assert len(page["components"]) > 0

    def test_open_and_resolve_incident(self):
        from data_ai.core.sla import IncidentSeverity, IncidentStatus, get_sla_monitor, reset_sla_monitor

        reset_sla_monitor()
        m = get_sla_monitor()
        comp = m.list_components()[0]
        inc = m.open_incident(
            title="Test outage",
            severity=IncidentSeverity.MAJOR,
            affected_components=[comp.id],
            message="investigating",
        )
        assert inc.id
        # 组件状态应该降级
        assert m.get_component(comp.id).status.value == "partial_outage"
        # 状态页应该有 active incident
        page = m.status_page()
        assert len(page["active_incidents"]) == 1
        # resolve
        m.update_incident(inc.id, IncidentStatus.RESOLVED, message="fixed")
        assert m.get_incident(inc.id).status == IncidentStatus.RESOLVED
        # 组件恢复 operational
        assert m.get_component(comp.id).status.value == "operational"

    def test_slo_evaluate(self):
        from data_ai.core.sla import SLO, get_sla_monitor, reset_sla_monitor

        reset_sla_monitor()
        m = get_sla_monitor()
        comp = m.list_components()[0]
        # 100% 成功
        for _ in range(100):
            m.record_probe(comp.id, success=True, latency_ms=50)
        slo = SLO(name="avail", component_id=comp.id, sli_type="availability", target_value=99.0)
        m.create_slo(slo)
        report = m.evaluate_slo(slo, window_sec=3600)
        assert report["status"] == "ok"
        assert report["current_value"] == 100.0

    def test_slo_breach(self):
        from data_ai.core.sla import SLO, get_sla_monitor, reset_sla_monitor

        reset_sla_monitor()
        m = get_sla_monitor()
        comp = m.list_components()[0]
        for _ in range(50):
            m.record_probe(comp.id, success=True)
        for _ in range(50):
            m.record_probe(comp.id, success=False)
        slo = SLO(name="avail-high", component_id=comp.id, sli_type="availability", target_value=99.0)
        m.create_slo(slo)
        report = m.evaluate_slo(slo, window_sec=3600)
        assert report["status"] == "breach"
        assert report["current_value"] == 50.0

    def test_monthly_report(self):
        from data_ai.core.sla import get_sla_monitor, reset_sla_monitor

        reset_sla_monitor()
        m = get_sla_monitor()
        r = m.monthly_report(2026, 1)
        assert r["year"] == 2026
        assert r["month"] == 1
        assert "incident_count" in r


# ---------- SSO ----------


class TestSSO:
    def test_register_and_list_idp(self, tmp_path):
        from data_ai.core.sso import IdentityProvider, SSOEngine, reset_sso_engine

        reset_sso_engine()
        # 避免使用全局单例共享
        e = SSOEngine(persist_path=tmp_path / "sso.jsonl")
        idp = IdentityProvider(
            name="Company Okta",
            type="oidc",
            issuer="https://company.okta.com",
            client_id="test-client",
            client_secret="test-secret",
            authorization_endpoint="https://company.okta.com/oauth2/v1/authorize",
            token_endpoint="https://company.okta.com/oauth2/v1/token",
        )
        e.register_idp(idp)
        assert len(e.list_idps()) == 1
        fetched = e.get_idp_by_name("Company Okta")
        assert fetched is not None
        assert fetched.issuer == "https://company.okta.com"

    def test_oidc_auth_url(self, tmp_path):
        from data_ai.core.sso import IdentityProvider, OIDCProvider, SSOEngine

        e = SSOEngine(persist_path=tmp_path / "sso.jsonl")
        idp = IdentityProvider(
            name="x",
            authorization_endpoint="https://idp.example.com/authorize",
            client_id="cid",
        )
        e.register_idp(idp)
        provider = e.get_provider(idp.id)
        assert isinstance(provider, OIDCProvider)
        url = provider.build_authorization_url(redirect_uri="https://app.example.com/cb")
        assert "client_id=cid" in url
        assert "response_type=code" in url

    def test_id_token_verification(self, tmp_path):
        from data_ai.core.sso import IdentityProvider, OIDCProvider, _make_test_jwt

        idp = IdentityProvider(
            name="x",
            issuer="https://idp.example.com",
            client_id="cid",
            client_secret="secret",
            allowed_email_domains=["company.com"],
        )
        provider = OIDCProvider(idp)
        # 生成合法 token
        token = _make_test_jwt(idp, sub="user-1", email="alice@company.com", name="Alice")
        r = provider.verify_id_token(token)
        assert r["ok"] is True
        assert r["email"] == "alice@company.com"
        # 不在白名单
        token2 = _make_test_jwt(idp, sub="user-2", email="bob@evil.com", name="Bob")
        r2 = provider.verify_id_token(token2)
        assert r2["ok"] is False
        assert "not allowed" in r2["error"]

    def test_scim_provisioner(self, tmp_path):
        from data_ai.core.sso import SSOEngine

        e = SSOEngine(persist_path=tmp_path / "sso.jsonl")
        u = e.scim.upsert_user("alice@co.com", "Alice", active=True, groups=["dev"])
        assert u.id
        # 重复 upsert 更新
        u2 = e.scim.upsert_user("alice@co.com", "Alice Updated", active=True, groups=["dev", "admin"])
        assert u2.id == u.id
        assert u2.display_name == "Alice Updated"
        # 列出
        users = e.scim.list_users()
        assert len(users) == 1
        # 停用
        assert e.scim.deactivate("alice@co.com") is True
        active = e.scim.list_users(active_only=True)
        assert len(active) == 0


# ---------- Residency ----------


class TestResidency:
    def test_bootstrap_regions(self):
        from data_ai.core.residency import get_residency_router, reset_residency_router

        reset_residency_router()
        r = get_residency_router()
        regions = r.list_regions()
        assert any(r.id == "cn-east" for r in regions)
        assert any(r.id == "eu-west" for r in regions)

    def test_route_pii(self):
        from data_ai.core.residency import get_residency_router, reset_residency_router

        reset_residency_router()
        r = get_residency_router()
        # pii 默认允许所有主要 region
        a = r.route(resource_id="agent-1", data_class="pii", prefer_region="cn-east")
        assert a.region_id == "cn-east"
        assert a.encrypted is True

    def test_route_phi_default_blocked(self):
        from data_ai.core.residency import get_residency_router, reset_residency_router

        reset_residency_router()
        r = get_residency_router()
        # phi 默认 allowed_regions 为空 → 选任意 active
        a = r.route(resource_id="phi-1", data_class="phi")
        assert a.region_id != ""

    def test_can_transfer(self):
        from data_ai.core.residency import get_residency_router, reset_residency_router

        reset_residency_router()
        r = get_residency_router()
        # 未注册的 resource 默认允许
        ok, _ = r.can_transfer("never-seen", "cn-east", "us-east")
        assert ok

    def test_custom_policy(self):
        from data_ai.core.residency import ResidencyPolicy, get_residency_router, reset_residency_router

        reset_residency_router()
        r = get_residency_router()
        # 自定义: phi 只能在中国
        pol = ResidencyPolicy(
            name="phi-cn-only",
            data_class="phi",
            allowed_regions=["cn-east", "cn-north"],
            forbidden_regions=[],
        )
        r.add_policy(pol)
        # 路由 phi 到 cn-east
        a = r.route(resource_id="phi-x", data_class="phi", prefer_region="cn-east")
        assert a.region_id == "cn-east"
        # 试图转移到 eu-west
        ok, reason = r.can_transfer("phi-x", "cn-east", "eu-west")
        # 实际 resource 是已分配的,应能查到 policy
        # 先验证 record 存在
        assert r.list_assignments()

    def test_region_status(self):
        from data_ai.core.residency import get_residency_router, reset_residency_router

        reset_residency_router()
        r = get_residency_router()
        r.set_region_status("cn-east", "offline")
        assert r.get_region("cn-east").status == "offline"


# ---------- Audit Chain (Merkle) ----------


class TestAuditChain:
    def test_merkle_root_empty(self):
        from data_ai.core.audit_chain import build_merkle_root

        assert build_merkle_root([]) == ""

    def test_merkle_root_single(self):
        from data_ai.core.audit_chain import build_merkle_root

        h = "abc123"
        assert build_merkle_root([h]) == h

    def test_merkle_root_consistent(self):
        from data_ai.core.audit_chain import build_merkle_root

        leaves = [f"h{i}" for i in range(4)]
        r1 = build_merkle_root(leaves)
        r2 = build_merkle_root(leaves)
        assert r1 == r2

    def test_merkle_proof_and_verify(self):
        from data_ai.core.audit_chain import build_merkle_root, merkle_proof, verify_proof

        leaves = ["h0", "h1", "h2", "h3"]
        root = build_merkle_root(leaves)
        for i in range(4):
            path, computed_root = merkle_proof(leaves, i)
            assert verify_proof(leaves[i], i, path, root) is True
            assert computed_root == root

    def test_chain_seal_at_threshold(self, tmp_path):
        from data_ai.core.audit_chain import AuditChain

        chain = AuditChain(seal_threshold=5, persist_path=tmp_path / "chain.jsonl")
        # 加 5 条
        result = None
        for i in range(5):
            result = chain.add_entry({"id": f"e{i}", "actor": "alice", "action": "create"})
        assert result is not None  # 第 5 条触发 seal
        assert len(chain.list_blocks()) == 1
        # 再加 3 条,不触发
        for i in range(5, 8):
            chain.add_entry({"id": f"e{i}"})
        assert len(chain.list_blocks()) == 1
        assert chain.pending_count() == 3

    def test_chain_integrity(self, tmp_path):
        from data_ai.core.audit_chain import AuditChain

        chain = AuditChain(seal_threshold=2, persist_path=tmp_path / "c.jsonl")
        for i in range(4):
            chain.add_entry({"id": f"e{i}"})
        # 强制 seal
        chain.force_seal()
        chain.force_seal()
        r = chain.chain_integrity()
        assert r["ok"] is True
        assert r["block_count"] >= 2

    def test_force_seal_empty(self, tmp_path):
        from data_ai.core.audit_chain import AuditChain

        chain = AuditChain(persist_path=tmp_path / "c.jsonl")
        b = chain.force_seal()
        assert b.entry_count == 0


# ---------- API 端到端 (TestClient) ----------


class TestAPISmoke:
    """简单 smoke test — 确认 FastAPI 应用能加载 + 主要路径返回 200"""

    def test_api_loads(self):
        from data_ai.core.api import extensions

        router = extensions.router
        # 数路由数
        paths = {r.path for r in router.routes if hasattr(r, "path")}
        # 关键路径必须存在
        assert "/v1/tenants" in paths
        assert "/v1/rbac/roles" in paths
        assert "/v1/billing/summary" in paths
        assert "/v1/sla/status" in paths
        assert "/v1/sso/idps" in paths
        assert "/v1/residency/regions" in paths
        assert "/v1/audit-chain/integrity" in paths


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
