# DATA-AI Roadmap

This file tracks the **Enterprise Governance** program end-to-end. Each
tier is a self-contained release; tiers stack on top of each other.
The README contains the summary tables; this file contains the detailed
checklists and per-item acceptance criteria.

> Status legend: `[x]` shipped, `[~]` in progress, `[ ]` not started,
> `[?]` under design.

---

## Tier 1 — Observability & Control  ✅ shipped (P1-10)

- [x] `core/audit` — structured log + stats
- [x] `core/quota` — soft + hard limits, top-N
- [x] `core/webhooks` — HMAC + retry + DLQ
- [x] `core/scheduler` — cron + backoff
- [x] Web pages: `/audit`, `/quota`, `/webhooks`, `/scheduler`
- [x] API endpoints, SDK methods, TypeScript types
- [x] 33 unit tests passing

## Tier 2 — Multi-Tenancy & Compliance  ✅ shipped (P1-11)

- [x] `core/tenants` — multi-tenant isolation + members
- [x] `core/rbac` — roles + ABAC + delegation
- [x] `core/billing` — per-model pricing + budgets
- [x] `core/sla` — SLO + incidents + status page
- [x] `core/sso` — OIDC / SAML / SCIM
- [x] `core/residency` — region routing
- [x] `core/audit_chain` — Merkle-rooted tamper-evidence
- [x] Web pages: `/tenants`, `/rbac`, `/billing`, `/sla`, `/sso`, `/residency`, `/audit-chain`
- [x] 47 unit tests passing

## Tier 3 — Resilience & Service Guarantees  ✅ shipped (P1-12)

- [x] `core/replication` — sync / async streams, failover, quorum
- [x] `core/recovery` — backup / restore / DR drill / retention hold
- [x] `core/sla/compensation` — breach detection + credit + dispute
- [x] Web pages: `/replication`, `/recovery`, `/compensation`
- [x] 52 unit tests passing

**Combined Tier 1+2+3: 423 unit tests passing, ruff clean, web build ✓,
70+ enterprise API endpoints, 50+ SDK methods.**

---

## Tier 4 — Real-time sync & Runbook automation  `[ ]` planned

Items ship independently, no tier-wide flag day.

### 4.1 Bi-directional WebSocket cross-region replication
- [ ] `core/replication/ws.py` — WebSocket transport
- [ ] Backpressure, resume-from-LSN, deduplication
- [ ] TLS + mutual auth between regions
- [ ] Backfill tool for cold start
- Acceptance: WAL events cross regions in <1s P50, survive region restart.

### 4.2 One-click DR Runbook
- [ ] `core/recovery/runbook.py` — YAML-defined steps
- [ ] Pre-flight checks, auto-rollback on step failure
- [ ] Audit-log every run
- [ ] CLI: `data-ai dr run <name>`
- Acceptance: full `detect → snapshot → failover → verify` from one
  command, end-to-end <15 min on 1 TB dataset.

### 4.3 Auto credit-on-invoice
- [ ] `core/billing/credit_apply.py` — hook into invoice builder
- [ ] Idempotency: same credit never applied twice
- [ ] Export applied credits in invoice PDF
- Acceptance: when a `Credit` is approved, next invoice deducts it
  automatically and the credit status moves to `applied`.

### 4.4 Per-tenant API quotas enforced from `tenants.limits`
- [ ] `core/quota/tenant_bridge.py` — read `tenants.limits` into quota
- [ ] 429 response when tenant exceeds
- [ ] Burst allowance + per-tenant dashboard tile
- Acceptance: a tenant at `max_tokens_per_day` gets HTTP 429 in the
  Web SDK within the same billing day.

### 4.5 SOC 2 / ISO 27001 evidence exporter
- [ ] `core/compliance/evidence.py` — bundle generator
- [ ] Covers audit log, retention holds, DR drill history, RBAC changes
- [ ] Output: signed ZIP + SHA-256 manifest
- Acceptance: a customer can request a 90-day evidence bundle and
  receive a verifiable archive in <10 min.

---

## Tier 5 — Federation & Marketplace  `[?]` backlog

### 5.1 Multi-model router with vendor failover
- [ ] `core/llm/router.py` — strategy pattern (cost / latency / quality)
- [ ] Health probing per provider
- [ ] Per-tenant vendor allow-list
- Acceptance: when primary provider returns 5xx for 30s, traffic moves
  to secondary with no user-visible retry.

### 5.2 Skill marketplace
- [ ] `core/marketplace/` — publish + signed install
- [ ] Versioned manifest with semver
- [ ] Org-scoped vs public visibility
- Acceptance: a partner can ship a Skill that installs with one click
  on a target tenant.

### 5.3 BYO identity (LinkedIn, GitHub Org, WeCom)
- [ ] `core/sso/providers/linkedin.py` etc.
- [ ] Reuse the existing `IdentityProvider` interface
- Acceptance: a tenant can enable LinkedIn OIDC from `/sso` page.

### 5.4 Federation between independent DATA-AI installs
- [ ] `core/federation/` — agent delegation with mTLS
- [ ] Trust store of remote org public keys
- Acceptance: tenant A in org 1 can invoke a published agent in org 2
  with a single delegation token.

---

## Tier 6 — AI-native operations  `[?]` vision

- [ ] Anomaly-aware audit alerts (per-actor / time-of-day baselines)
- [ ] Natural-language DR drill (`"drill last week"`)
- [ ] Predictive SLA breach forecast (next 30 days)
- [ ] Self-tuning quotas (raise/lower based on growth)

These depend on Tier 1–3 data being clean, which is why they are last.

---

## How tiers ship

1. Branch `feat/pX-Y-tier-Z` off `main`.
2. Implement core module + API + SDK + Web page + tests.
3. `pytest tests/ -q` must show all green; `ruff check` clean.
4. `pnpm --dir web build` must succeed.
5. Smoke test the new endpoints with `uvicorn` + `curl`.
6. Update this file and `README.md` to mark items `[x]`.
7. Commit with `feat(pX-Y): <tier summary>`.

Last updated: 2026-06-05
