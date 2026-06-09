# DATA-AI

A single Python process that gives you an OpenAI-compatible chat API,
a React web console, a multi-agent runtime, RAG, long-term memory,
a code sandbox, and 30+ tools — and the whole thing is one repo,
one `make up`, one `python -m data_ai.core.api.server`.

I built this because every "AI platform" demo I saw needed four
containers and a half-day of YAML to even boot. I wanted something I
could `git clone` and have running before my coffee got cold.

---

## What it actually does

- **Single agent, multi-agent teams.** Consensus (LLM synthesis, vote,
  semantic), reflection, iteration limits. The agent loop is real —
  every tool call hits a real adapter; the failures are real too.
- **19 LLM providers** behind one registry. OpenAI, Anthropic, Google,
  Azure, Bedrock, DeepSeek, SiliconFlow, Qwen, Zhipu, Moonshot, Yi,
  Baichuan, Doubao, StepFun, Ollama, vLLM, LM Studio, and a built-in
  offline model for tests.
- **30+ tools** for file I/O, Python / Bash / Node sandbox, browser
  automation, web search, PDF / Word / Excel / PPT, data analysis.
- **RAG + memory in the same process.** In-memory, FAISS, Chroma, or
  LanceDB. Long-term memory is wired into the chat loop, not bolted
  on after the fact.
- **ContextStore** — named, file-backed, JSON-tree project memory. Save
  drafts, outlines, character sheets; diff them across commits; never
  lose them inside a chat session.
- **4 ready-made enterprise presets** (customer service, finance
  analyst, secretary, novel writer) so you don't start from a blank
  system prompt.

## Quick start

```bash
cp .env.example .env
# add your OPENAI_API_KEY
make up
# open http://localhost:3000
```

That's the whole on-ramp. Everything else is in [`docs/`](docs/).

---

## What it is

DATA-AI is a single backend process that exposes a chat-compatible HTTP
API plus a static web UI. It is meant to be self-hosted: clone, set an API
key, run `python -m data_ai.core.api.server`, and you have a working
multi-model agent in under a minute.

The interesting parts:

- **Real agent runtime.** Single agents and multi-agent teams, with
  consensus (LLM synthesis, majority vote, semantic), reflection, and
  iteration limits. Not a prompt wrapper.
- **19 LLM providers behind one registry.** OpenAI, Anthropic, Google,
  Azure, AWS Bedrock, DeepSeek, SiliconFlow, Qwen, Zhipu, Moonshot, Yi,
  Baichuan, Doubao, StepFun, Ollama, vLLM, LM Studio, plus a built-in
  offline model for tests and demos.
- **30+ tools.** File ops, Python / Bash / Node sandbox, browser
  automation, web search, PDF / Word / Excel / PPT processing, data
  analysis, system tools.
- **RAG and memory in the same process.** In-memory, FAISS, Chroma, or
  LanceDB. Long-term memory with summarization is wired into the chat
  loop, not bolted on.
- **ContextStore — named, file-backed project memory.** Save / load /
  version / search any long text (drafts, outlines, character sheets)
  in a transparent JSON tree, git-friendly, decoupled from chat
  sessions. See
  [`core/context_store.py`](src/data_ai/core/context_store.py).
- **Four ready-made enterprise agent presets.** Customer service,
  finance analyst, secretary, and novel writer. Each ships with a tuned
  system prompt, scoped tool list, and default context namespace. Load
  with one line:
  [`plugins/agents/`](src/data_ai/plugins/agents/).
- **Colloquial-Chinese intent normalizer.** Lightweight typo / filler /
  mixed-language fixes (e.g. 帐单→账单, 给我弄→帮我, 打开 app→打开
  应用) applied before intent matching. See
  [`_normalize_colloquial`](src/data_ai/core/intent/recognizer.py).
- **One-shot sandbox setup.** `bash scripts/setup_sandbox.sh`
  installs every system package, Python lib, and CJK font DATA-AI
  needs in a fresh container.
- **A web console that actually works.** Vite + React 19, SSE streaming
  chat, dark / light theme, English / 简体中文 switchable from the
  topbar, no telemetry.

The backend is small enough to read in an afternoon. The interesting
files are `src/data_ai/core/llm/manager.py` (the LLM registry),
`src/data_ai/core/agent/base.py` (the agent loop), and
`src/data_ai/core/api/server.py` (the HTTP surface — 70+ routes).

## Quick Start

### Just the CLI (smallest possible setup)

```bash
pip install -e .
data-ai chat --model offline-chat
```

`offline-chat` is built in, so this works with no API key. You get a
REPL that exercises the agent loop, tool registry, and memory.

### The web console (recommended)

```bash
# 1) Backend — http://127.0.0.1:8000
pip install -e .
# 如遇 FastAPI 0.115+ 的 "Status code 204 must not have a response body" 启动失败,
# 跑一次兼容性补丁 (幂等, 打过会跳过):
#   make patch
python -m data_ai.core.api.server

# 2) Frontend — http://127.0.0.1:5173
cd web
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. The default page is the **Chat Console**:
pick a model, send a message, watch it stream token by token.

To use a real provider, set its env var before starting the backend:

```bash
export DEEPSEEK_API_KEY="sk-..."      # any of OPENAI_*, ANTHROPIC_*, DEEPSEEK_*, ...
# or set DATA_AI_API_KEYS to enable inbound auth
export DATA_AI_API_KEYS="any-token"
# or skip auth in dev
export DATA_AI_DEV_MODE=true
```

See [`docs/INSTALLATION.md`](docs/INSTALLATION.md) and
[`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for the full reference.

## Web Console

| Page                | Path                          | What it does                         |
|---------------------|-------------------------------|--------------------------------------|
| Chat Console        | `/chat`                       | Multi-model streaming chat (SSE)     |
| Agents              | `/agents`                     | Single-agent definition + run history |
| Agent Teams         | `/teams`                      | Multi-agent collaboration + consensus |
| Memory              | `/memory`                     | Short / long-term memory management  |
| Knowledge Base      | `/rag`                        | Document upload, chunking, retrieval |
| Sandbox             | `/sandbox`                    | Online Python / Bash / Node execution |
| Tools               | `/tools`                      | Browse and try built-in tools        |
| Skills              | `/skills`                     | Skill definitions and execution      |
| Office (Word/PPT/Excel/PDF) | `/office/*`           | Office file processing               |
| Models              | `/models`                     | Model registration and testing       |
| Settings            | `/settings`                   | API key, base URL, theme, language   |

### Enterprise (self-hosted SaaS console)

| Page                | Path                          | What it does                         |
|---------------------|-------------------------------|--------------------------------------|
| Audit Log           | `/audit`                      | Searchable audit trail with stats     |
| Quota               | `/quota`                      | Per-actor rate limits, soft + hard   |
| Webhooks            | `/webhooks`                   | Event subscriptions + delivery log   |
| Scheduler           | `/scheduler`                  | Cron jobs, executions, retry policy  |
| Tenants             | `/tenants`                    | Multi-tenant isolation + members     |
| RBAC                | `/rbac`                       | Roles, ABAC policies, delegation log |
| Cost Center         | `/billing`                    | Per-model pricing, budgets, invoices |
| SLA & Status        | `/sla`                        | SLO evaluation, incidents, status    |
| SSO / IdP           | `/sso`                        | OIDC / SAML, SCIM, sessions          |
| Data Residency      | `/residency`                  | Region routing, compliance policies  |
| Audit Chain         | `/audit-chain`                | Merkle-rooted tamper-evident log     |
| Cross-Region Repl.  | `/replication`                | Streams, lag, failover + quorum      |
| Backup & Recovery   | `/recovery`                   | Schedules, restore, DR drills, holds |
| SLA Compensation    | `/compensation`               | Breach detection, credits, disputes  |

Switch UI language from the topbar — supports **English** and **简体中文**
without a reload.

## Features

### LLM providers

- **Global**: OpenAI, Anthropic, Google Gemini, Azure OpenAI, AWS Bedrock
- **Chinese**: DeepSeek, Qwen, Zhipu, Moonshot, Yi, Baichuan, Doubao, StepFun, SiliconFlow
- **Local / self-hosted**: Ollama, vLLM, LM Studio
- **Built-in**: `offline-chat`, `offline-fast`, `offline-mini` — templated
  replies, used for CI, tests, and demos. No external call.

All Chinese / global providers except Anthropic and Google are
OpenAI-compatible and share a single client implementation with
auto-detected `base_url`. See
[`PROVIDER_DEFAULT_BASE_URL`](src/data_ai/core/llm/manager.py).

The server auto-registers a model for any of these env vars on startup
(see the lifespan hook in
[`src/data_ai/core/api/server.py`](src/data_ai/core/api/server.py)):

| Provider     | Env var(s)                              | Model id (default)         |
|--------------|------------------------------------------|----------------------------|
| OpenAI       | `OPENAI_API_KEY`                         | `openai-gpt-4o-mini`       |
| Anthropic    | `ANTHROPIC_API_KEY`                      | `anthropic-claude-3-5-sonnet` |
| DeepSeek     | `DEEPSEEK_API_KEY`                       | `deepseek-chat`            |
| SiliconFlow  | `SILICONFLOW_API_KEY`                    | `siliconflow-deepseek`     |
| Qwen         | `QWEN_API_KEY` / `DASHSCOPE_API_KEY`     | `qwen-plus`                |
| Zhipu GLM    | `ZHIPU_API_KEY` / `GLM_API_KEY`          | `zhipu-glm-4-flash`        |
| Moonshot     | `MOONSHOT_API_KEY`                       | `moonshot-v1-32k`          |
| Yi           | `YI_API_KEY`                             | `yi-medium`                |
| Baichuan     | `BAICHUAN_API_KEY`                       | `baichuan4`                |
| Doubao       | `DOUBAO_API_KEY`                         | `doubao-lite-32k`          |
| StepFun      | `STEPFUN_API_KEY`                        | `step-1-flash`             |

### Agents

- `BaseAgent` with tool calling, reflection, iteration control
- **Self-Reflection** (P0-2): LLM 评估自己答案的 confidence,issues 注入回 messages
- **Checkpoint 持久化** (P1-1): 每轮 iteration 自动存盘, 支持 resume, gzip 压缩
- **Human-in-the-Loop** (P1-2): 危险工具触发暂停, 等人工 approve / reject (5min 超时自动 reject)
- **Sub-Agent 委派** (P1-3): `delegate(query, role)` spawn sub-agent, 套 preset (customer_service / finance_analyst / secretary / novel_writer), `delegate_many` 并行
- **Tool Retry** (P1-4): 异常分类 (retryable / permanent), 指数退避 + jitter, 防 thundering herd
- `AgentTeam` with **LLM synthesis / majority vote / semantic / concatenation** consensus
- Sequential thinking and closed-loop learning are part of the same loop,
  not a separate "mode"

### Tooling

- File ops: read / write / search / replace / batch
- Code execution: Python sandbox, Bash, Node.js with real stdout capture
- Browser automation: navigation, click, screenshot, form filling
  (Playwright, optional)
- Documents: PDF, Word, Excel, PPT, Markdown, HTML
- Data analysis: Pandas, Matplotlib, Plotly
- Office workflows with real `.docx` / `.pptx` / `.xlsx` / `.pdf` round-trip

### RAG

- Loaders: PDF, Word, Markdown, HTML, TXT
- Splitters: recursive character, token-based
- Stores: in-memory, FAISS, Chroma, LanceDB
- Retrieval: similarity, MMR diversity, with citations

### Memory

- Session / semantic / short-term / long-term
- Automatic summarization when the window grows
- Closed-loop: execute → evaluate → extract → retrieve

## Enterprise Governance

Three production tiers, all shipped and self-hostable. Each tier maps to
a recurring customer pain point (audit gap, access control, compliance,
business continuity, contractual SLA).

### Tier 1 — Observability & Control (shipped)

| Module        | Purpose                                                                |
|---------------|------------------------------------------------------------------------|
| `core/audit`        | Structured audit log with actor, resource, IP, payload hash, stats   |
| `core/quota`        | Per-actor soft + hard rate / token limits, top-N reporting           |
| `core/webhooks`     | Event subscriptions with HMAC signing, retry, dead-letter, delivery  |
| `core/scheduler`    | Cron-style job runner with retry, backoff and execution history      |

### Tier 2 — Multi-Tenancy & Compliance (shipped)

| Module               | Purpose                                                            |
|----------------------|--------------------------------------------------------------------|
| `core/tenants`       | Tenant + member lifecycle, per-tenant quotas, plan tiers           |
| `core/rbac`          | Role + permission + ABAC conditions, role inheritance, delegation |
| `core/billing`       | Per-model pricing, soft/hard budget caps, cost-center allocation   |
| `core/sla`           | SLO evaluation, component health, incident lifecycle, status page  |
| `core/sso`           | OIDC + SAML providers, SCIM provisioning, session store            |
| `core/residency`     | Region-aware data routing, 6 policy classes, residency assignments |
| `core/audit_chain`   | Merkle-rooted append-only chain with inclusion-proof verification  |

### Tier 3 — Resilience & Service Guarantees (shipped)

| Module                     | Purpose                                                        |
|----------------------------|----------------------------------------------------------------|
| `core/replication`         | Sync / async / semi-sync streams, lag, failover, quorum guard  |
| `core/recovery`            | Backup schedules, restore, DR drills, retention / legal hold   |
| `core/sla/compensation`    | Breach detection, credit calculation, dispute / refund flow    |

All three tiers share the same shape:

- Pure-Python core under `data_ai.core.<module>/` — usable from
  `from data_ai.core.tenants import get_tenant_store` without the API
- REST surface mounted under `/v1/...` (see `api/extensions.py`)
- Typed Python SDK client (`from data_ai.sdk_client import DataAIClient`)
- Typed TypeScript client (`web/src/lib/api/client.ts`)
- Web console page + sidebar entry + `i18n` strings
- Unit tests under `tests/test_enterprise_tier*.py` (current: 423 passing)

## Architecture

```
src/data_ai/
├── core/
│   ├── llm/manager.py            LLM registry, 19 providers, streaming
│   ├── agent/base.py             BaseAgent, AgentTeam, consensus
│   ├── api/server.py             FastAPI app, 70+ routes
│   ├── api/extensions.py         Resource routers (agents, memory, ...)
│   ├── api/auth.py               Bearer-key verification
│   ├── tool/                     30+ tools
│   ├── memory/                   Short / long-term memory
│   ├── rag/                      Loaders, splitters, vector stores
│   ├── sandbox/                  Local + docker sandbox
│   ├── office/                   Word / PPT / Excel / PDF processors
│   └── i18n/                     catalog + locale negotiation
├── utils/                        config, exceptions, logging, platform
├── cli/                          typer commands (data-ai ...)
└── __main__.py                   data-ai entry point
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the long version.

## Configuration

A short version — the full reference is in
[`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

| Env var                   | Effect                                                       |
|---------------------------|--------------------------------------------------------------|
| `DATA_AI_API_KEYS`        | Comma-separated bearer keys. Empty = reject all (401).       |
| `DATA_AI_DEV_MODE`        | `true` skips auth. Local dev only.                           |
| `DATA_AI_CORS_ORIGINS`    | Comma-separated allowed origins. Empty = no CORS headers.    |
| `DATA_AI_SKILL_EXEC`      | `1` enables the skill execution endpoint. Off by default.    |
| `DATA_AI_LLM__MODEL`      | Default chat model id.                                       |
| `DATA_AI_LLM__BASE_URL`   | Default API endpoint.                                        |
| `DATA_AI_LLM__API_KEY`    | Default API key.                                             |

A TOML file at `config/config.toml` works too — see
[`config/config.example.toml`](config/config.example.toml) for the
template.

## Security

- Sandboxed code execution with CPU / memory / time limits
- Strict / moderate / permissive policy presets
- Bearer-key auth on every route by default
- Skill execution is gated behind an explicit env var so a default install
  cannot shell out even if the auth is bypassed
- No telemetry, no phone-home, no third-party requests outside the
  providers you configure

## Status

DATA-AI is suitable for self-hosting and experimentation. It is not a
managed SaaS. The breaking-change rate is roughly once a month while the
agent API stabilizes.

## Roadmap

Enterprise governance is delivered in numbered tiers. **Tier 1, 2, and 3
are shipped** (see *Enterprise Governance* above). Future tiers are
listed here so customers and contributors can plan ahead.

### Tier 4 — Real-time sync & Runbook automation  *(planned, not started)*

| Item                                                | Why                                                          |
|-----------------------------------------------------|--------------------------------------------------------------|
| Bi-directional WebSocket cross-region replication   | Replace the in-memory replication engine with a transport    |
|   `core/replication/ws.py`                          | that actually streams WAL between regions                   |
| One-click DR Runbook                                | Tie detection → snapshot → failover → verification into a    |
|   `core/recovery/runbook.py`                        | single named playbook that ops can rehearse                 |
| Auto credit-on-invoice                              | When a `Credit` is approved, the next billing cycle deducts  |
|   `core/billing/credit_apply.py`                    | it without manual bookkeeping                                |
| Per-tenant API quotas that respect `tenants.limits`  | Make the `tenants` limits actually feed the `quota` engine   |
|   `core/quota/tenant_bridge.py`                     | so a tenant over-limit is rejected, not just reported        |
| SOC 2 / ISO 27001 evidence exporter                 | Bundle audit + retention + DR history into a ZIP for audits |
|   `core/compliance/evidence.py`                     |                                                              |

### Tier 5 — Federation & Marketplace  *(backlog)*

| Item                                                | Why                                                          |
|-----------------------------------------------------|--------------------------------------------------------------|
| Multi-model router with vendor failover             | Route to cheapest / healthiest provider, fall back on 5xx    |
|   `core/llm/router.py`                              |                                                              |
| Skill marketplace (publish + signed install)        | Let partners distribute Skills with a versioned manifest     |
|   `core/marketplace/`                               |                                                              |
| BYO identity (LinkedIn, GitHub Org, WeCom)          | Add non-enterprise IdPs on top of the existing SSO engine    |
|   `core/sso/providers/linkedin.py` etc.             |                                                              |
| Federation between independent DATA-AI installs     | Cross-org agent delegation with mutual mTLS                  |
|   `core/federation/`                                |                                                              |

### Tier 6 — AI-native operations  *(vision)*

| Item                                                | Why                                                          |
|-----------------------------------------------------|--------------------------------------------------------------|
| Anomaly-aware audit alerts                          | Surface outlier actors / times / payloads in `audit` feed    |
| Natural-language DR drill (`"drill last week"`)     | ChatOps surface over the runbook engine                      |
| Predictive SLA breach model                         | Forecast next 30 days SLO from incident history              |
| Self-tuning quotas                                  | Raise / lower limits based on tenant growth trend            |

Track the latest tier progress in [`ROADMAP.md`](ROADMAP.md) (kept in
sync with each tier commit).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). The short version: fork, branch,
`make install-dev`, `make test`, open a PR. Keep changes small and
falsifiable.

## License

[MIT](LICENSE).
