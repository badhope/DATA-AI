# DATA-AI Architecture

A practical overview for engineers who want to read the code, not the marketing.

## At a glance

DATA-AI is a small, self-contained backend that wires up an LLM-agnostic agent
runtime with a FastAPI server, a sandbox for code execution, a vector store for
long-term memory, and a React/Vite web console. Nothing here depends on
LangChain or any other agent framework — `BaseAgent` is a hand-rolled event
loop, and every LLM client talks plain HTTP.

```
+-----------------+         +--------------------+
|  Web (React)    |  HTTP   |  FastAPI (server)  |
|  Vite + TS      | <-----> |  70+ routes        |
+-----------------+         +----+----------+----+
                                 |          |
                          locale |          | RAG / memory
                                 v          v
                           +---------+    +-----------+
                           | LLM Mgr |    |  Vector   |
                           | 17 prov.|    |  Store    |
                           +----+----+    +-----------+
                                |
                       +--------+--------+
                       |    BaseAgent    |
                       | (hand-rolled)   |
                       +--------+--------+
                                |
                          +-----v-----+
                          |  Sandbox  |
                          | (code)    |
                          +-----------+
```

## Module layout (`src/data_ai/`)

| Path | What it does |
|---|---|
| `core/agent/` | `BaseAgent` + `AgentState` + `AgentConfig`. ReAct-style loop. |
| `core/llm/` | `LLMManager` with 17 providers (Anthropic / OpenAI-compatible). `OfflineLLMClient` for tests. |
| `core/api/` | FastAPI app, auth (`auth.py`), OpenAI-compatible `/v1/chat/completions`. |
| `core/skill/` | Stored tool/skill definitions; execution is gated by env var. |
| `core/memory/` | Vector memory (Qdrant-compatible) + summary store. |
| `core/context_store.py` | Named, file-backed project memory (drafts, outlines, customer sheets). Versioned JSON tree, git-friendly. |
| `core/rag/` | Document chunking, embeddings, retrieval. |
| `core/sandbox/` | Subprocess-based code execution with timeout. |
| `core/i18n/` | Locale catalog + Accept-Language negotiation. |
| `core/intent/` | Intent recognizer with colloquial-Chinese normalizer (typo / filler / mixed-language fixes). |
| `plugins/agents/` | Ready-made agent presets: `customer_service`, `finance_analyst`, `secretary`, `novel_writer`. |
| `cli/` | `data-ai` console entry point. |
| `sdk/` | Thin Python client for the HTTP API. |

## The agent loop

`BaseAgent.run(query)` in `core/agent/base.py` is the heart of the system.
It's not magical: it iterates a state machine, calls the LLM through
`LLMManager`, dispatches tool calls to the `ToolRegistry`, and stops on
`<final>` or after `max_iterations`. Streaming variants push `AgentEvent`
objects onto an `asyncio.Queue`.

```
state -> LLM -> parse -> tool calls? -> registry -> result -> state
                          no
                          v
                        done
```

## LLM clients

All real providers go through `BaseLLMClient`. The interesting bits:

- `OpenAIClient` handles OpenAI, DeepSeek, and the 7 Chinese providers
  (Qwen / Zhipu / Moonshot / Yi / Lingyi / Baichuan / Doubao / StepFun)
  because they all speak the OpenAI chat-completions schema.
- `AnthropicClient` is the only bespoke client (different message format).
- `OfflineLLMClient` returns deterministic echo responses and is what
  CI / tests use.

Models can come from code (`register_model(...)`) or from env vars
(`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DASHSCOPE_API_KEY`, …) — the
manager auto-registers anything it finds on startup.

## API surface

The server is regular FastAPI. The 70+ routes split roughly into:

- `/v1/chat/completions`, `/v1/completions`, `/v1/models`, `/v1/embeddings` — OpenAI-compatible.
- `/v1/agents`, `/v1/teams`, `/v1/sessions` — agent lifecycle.
- `/v1/memory`, `/v1/memory/search` — long-term memory.
- `/v1/skills`, `/v1/tools/execute` — tool calls.
- `/v1/sandboxes` — code execution.
- `/v1/documents`, `/v1/office/*` — RAG and Office parsing.
- `/health`, `/openapi.json`, `/docs` — ops.

Auth is `Authorization: Bearer <key>` or `X-Api-Key: <key>`. See `core/api/auth.py`.

## i18n

Locale resolution priority: `X-Locale` header → `Accept-Language` → default `en`.
The catalog is a plain dict in `core/i18n/catalog.py` with mirrored EN/ZH strings.
`tr(key, locale, **kwargs)` does string formatting.

The chat endpoint injects a system-prompt hint that tells the LLM which
language to reply in, so a Chinese user gets a Chinese answer even from
English-only models.

## Web

`web/` is a Vite + React 19 + Tailwind 4 app. The Vite dev server proxies
`/v1/*` to the FastAPI backend. The build is set to `base: "./"` so the
dist directory can be served from any sub-path or opened directly from
`file://`.

## ContextStore — file-backed project memory

`core/context_store.py` provides a lightweight, transparent store for
project-level artifacts (drafts, outlines, customer profiles, character
sheets). Unlike `core/memory/` (which is LLM-facing and short-lived),
ContextStore is human-readable, git-trackable, and decoupled from chat
sessions.

```
~/.data-ai/contexts/
├── finance/
│   ├── data_manifest.json
│   └── company_info.json
├── secretary/
│   └── owner_profile.json
└── novel_red_blue/
    ├── main_character.json      # has version + history
    └── chapter_1.json
```

Each `.json` file is plain text:

```json
{
  "name": "main_character",
  "namespace": "novel_red_blue",
  "content": "陈默,28岁,前刑警,左眼有疤",
  "tags": ["character", "main"],
  "created_at": "2026-06-04T10:00:00",
  "updated_at": "2026-06-04T15:30:00",
  "version": 2,
  "history": [
    {"version": 1, "content": "陈默,28岁,前刑警", "ts": "..."}
  ]
}
```

`ContextStore` exposes: `save`, `load`, `list (namespace/tag filter)`,
`search (keyword)`, `history`, `delete`, `namespaces`. Every write
emits a structured log line with `namespace`, `name`, `version`, and
`size` for full traceability.

## Agent presets

`plugins/agents/` ships four enterprise presets. Each is a `PRESET` dict
with `system_prompt`, `tools`, `default_namespace`, `max_iterations`,
and `temperature`, plus a `build_agent(llm_manager, ...)` factory.

| Preset | Role | Tools | temp | Use case |
|---|---|---|---|---|
| `customer_service` | 客服 | 7 | 0.3 | 查订单/物流/FAQ,不编造,引导人工 |
| `finance_analyst`  | 财务分析 | 15 | 0.1 | 多源数据 → 多格式报告(Word/PDF/PPT/MD) |
| `secretary`        | 秘书 | 13 | 0.5 | 日程/纪要/邮件草稿/查资料,长记忆 |
| `novel_writer`     | 小说写作 | 14 | 0.8 | 大纲/人物/章节跨会话持久化 |

`REGISTERED_PRESETS` in `plugins/agents/__init__.py` is the registry.
`list_presets()` and `get_preset(role)` are the public API.

## Intent normalization

`core/intent/recognizer.py::IntentRecognizer` runs a two-stage
normalization before keyword / pattern matching:

1. `_normalize_query` — whitespace, Chinese / English punctuation.
2. `_normalize_colloquial` — a small dict of high-frequency typos,
   fillers, and Chinese/English mix-ups (e.g. 帐单→账单, 登陆→登录,
   给我弄→帮我, 打开 app→打开应用). Long strings are listed first to
   avoid being eaten by shorter ones.

Failures fall back silently so the recognizer is never destabilized by
a malformed query.

## What's intentionally absent

- No LangChain / LlamaIndex dependency. `BaseAgent` is ~300 lines.
- No async DB. State lives in `STORE` (in-memory, with file-backed snapshots).
- No docker-compose. Run backend + frontend separately, or use the dev script.
- No telemetry, no auth providers beyond a static API key.
