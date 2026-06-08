# Configuration

DATA-AI configuration is loaded by `data_ai.utils.config.Settings` (Pydantic
Settings v2). Three sources are merged in this order, last source wins:

1. Built-in defaults from `LLMConfig` / `Settings` / etc.
2. A TOML file, if one is found at `config/config.toml`,
   `~/.data-ai/config.toml`, or `./config.toml` (whichever is found first).
3. Environment variables prefixed with `DATA_AI_`.

Nested settings use a double underscore as the separator
(`DATA_AI_LLM__MODEL` → `Settings.llm.model`).

## Contents

- [Quick start](#quick-start)
- [Server (HTTP) settings](#server-http-settings)
- [LLM settings](#llm-settings)
- [Sandbox settings](#sandbox-settings)
- [Memory settings](#memory-settings)
- [ContextStore settings](#contextstore-settings)
- [Intent normalizer settings](#intent-normalizer-settings)
- [Search settings](#search-settings)
- [TOML file example](#toml-file-example)
- [Frontend settings](#frontend-settings)
- [What's intentionally not configurable](#whats-intentionally-not-configurable)

## Quick start

Most deployments only need two environment variables:

```bash
# Accept any of these API keys on inbound HTTP requests
export DATA_AI_API_KEYS="sk-live-abc,sk-live-xyz"

# Register a model the LLM manager can route to
export DATA_AI_LLM__MODEL="deepseek-chat"
export DATA_AI_LLM__BASE_URL="https://api.deepseek.com/v1"
export DATA_AI_LLM__API_KEY="sk-..."
```

To skip authentication during local development:

```bash
export DATA_AI_DEV_MODE=true   # disables the API key check
```

To use a TOML file instead, copy the template and edit it:

```bash
cp config/config.example.toml config/config.toml
$EDITOR config/config.toml
```

`config/config.toml` is git-ignored. Do not commit real keys.

## Server (HTTP) settings

These are read in `data_ai.core.api.server`.

| Env var                   | Default       | Effect                                                       |
|---------------------------|---------------|--------------------------------------------------------------|
| `DATA_AI_API_KEYS`        | unset         | Comma-separated list of accepted `Authorization: Bearer` keys. If empty, all requests are rejected with `401` (unless `DATA_AI_DEV_MODE=true`). |
| `DATA_AI_DEV_MODE`        | `false`       | Bypasses the API key check. **Never set this in production.** |
| `DATA_AI_CORS_ORIGINS`    | empty         | Comma-separated list of allowed CORS origins. Empty = no CORS headers at all (browsers will block cross-origin calls). |
| `DATA_AI_SKILL_EXEC`      | unset         | If unset, the `POST /v1/skills/{id}/execute` endpoint refuses to run skills. Set to `1` to enable. This is intentional — skills can shell out, so it stays off by default. |
| `DATA_AI_REQUEST_LOCALE`  | unset         | Force a server-side default locale (`en` / `zh`). When unset, the locale is negotiated from the `Accept-Language` header and overridden by the `X-Locale` header per request. |

The server itself binds to `0.0.0.0:8000`. There is no `DATA_AI_HOST` /
`DATA_AI_PORT` env var — pass them to `run_server()` or uvicorn directly.

## LLM settings

Namespace `DATA_AI_LLM__` (or top-level `DATA_AI_LLM_*` for the legacy
pydantic-settings style). Reads the first existing source.

| Key               | Env var                       | Default                       | Notes                                  |
|-------------------|-------------------------------|-------------------------------|----------------------------------------|
| `model`           | `DATA_AI_LLM__MODEL`          | `claude-3-5-sonnet-20250619`  | The model id sent to the provider.     |
| `provider`        | (set in code)                 | derived from model id         | One of the values in `ModelProvider`.  |
| `base_url`        | `DATA_AI_LLM__BASE_URL`       | auto                          | Auto-filled from `PROVIDER_DEFAULT_BASE_URL` for OpenAI-compatible providers (DeepSeek, Qwen, Zhipu, Moonshot, Yi, Baichuan, Doubao, StepFun, SiliconFlow). |
| `api_key`         | `DATA_AI_LLM__API_KEY`        | unset                         | Required for all real providers. The `offline` provider ignores it. |
| `max_tokens`      | `DATA_AI_LLM__MAX_TOKENS`     | `4096`                        | Upper bound for completion tokens.     |
| `max_input_tokens`| `DATA_AI_LLM__MAX_INPUT_TOKENS` | unset                       | Truncate older messages if exceeded.   |
| `temperature`     | `DATA_AI_LLM__TEMPERATURE`    | `0.0`                         | `0.0` – `2.0`.                         |
| `api_type`        | `DATA_AI_LLM__API_TYPE`       | `anthropic`                   | For compatibility with the TOML key from the example. The `provider` field in code takes precedence. |
| `api_version`     | `DATA_AI_LLM__API_VERSION`    | unset                         | Used by the Azure client.              |

### Registering more than one model

`LLMManager` is a registry, not a single-model object. To expose a second
model id (for example, both `deepseek-chat` and `qwen-turbo`), call
`register_model()` at startup — typically from your own launcher script:

```python
from data_ai import get_llm_manager, register_model

register_model(
    name="qwen-turbo",
    provider="qwen",
    model_name="qwen-turbo",
    api_key="sk-...",
)
```

The console script `data-ai list-models` shows what's currently registered.

### Provider-specific keys

These are provider SDKs that need their own native env var. DATA-AI doesn't
intercept them; it just passes them through.

| Provider  | Native env var             |
|-----------|----------------------------|
| OpenAI    | `OPENAI_API_KEY`           |
| Anthropic | `ANTHROPIC_API_KEY`        |
| Google    | `GOOGLE_API_KEY` / `GEMINI_API_KEY` |
| AWS Bedrock | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (+ `AWS_REGION`) |
| Azure     | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` |

If `DATA_AI_LLM__API_KEY` is unset, the LLM manager falls back to the
provider-native env var.

## Sandbox settings

Namespace `DATA_AI_SANDBOX__`.

| Key               | Default                | Notes                                                  |
|-------------------|------------------------|--------------------------------------------------------|
| `enabled`         | `true`                 | Master switch. If false, the `shell` tool is a no-op.  |
| `sandbox_type`    | `local`                | `local` (in-process), `docker`, `daytona`, `remote`.   |
| `work_dir`        | `/tmp/data-ai-sandbox` | Resolved to an absolute path on load.                  |
| `timeout`         | `300`                  | Seconds. `1` – `3600`.                                 |
| `network_enabled` | `true`                 | Allow outbound HTTP from inside the sandbox.           |
| `docker_image`    | `python:3.11-slim`     | Only used when `sandbox_type=docker`.                  |
| `docker_memory_limit` | `1g`               | Docker `--memory`.                                     |
| `docker_cpu_limit`    | `2.0`              | Docker `--cpus`.                                       |

Note: `daytona` is parsed but the Daytona client itself is not bundled. The
TOML key `use_sandbox` is accepted as a synonym for `enabled` for backward
compatibility.

## Memory settings

Namespace `DATA_AI_MEMORY__`.

| Key                              | Default | Notes                                            |
|----------------------------------|---------|--------------------------------------------------|
| `enabled`                        | `true`  |                                                  |
| `enable_long_term_memory`        | `true`  | Persists across sessions.                        |
| `enable_conversation_summarization` | `true` | Compresses older turns when the window grows.   |
| `keep_recent_messages`           | `20`    | Number of recent turns kept verbatim.            |
| `summary_interval`               | `10`    | Summarize every N new turns.                     |
| `max_summary_length`             | `1000`  | Character cap on the rolling summary.            |
| `memory_dir`                     | `~/.data-ai/memory` | Resolved to absolute path on load.    |
| `auto_save_interval`             | `30`    | Seconds between flushes.                         |

### Vector store

Namespace `DATA_AI_VECTOR__`. Disabled by default — install the `chroma`
extra to use it.

| Key                | Default              | Notes                                |
|--------------------|----------------------|--------------------------------------|
| `enabled`          | `false`              |                                      |
| `store_type`       | `chroma`             | `chroma`, `faiss`, or `lance`.       |
| `collection_name`  | `data-ai-memory`     |                                      |
| `persist_directory`| `~/.data-ai/vectorstore` | Resolved on load.                |
| `embedding_model`  | `all-MiniLM-L6-v2`   | Sentence-transformers model id.      |

## ContextStore settings

`ContextStore` is the named, file-backed project memory in
`core/context_store.py`. It is *not* yet exposed through `Settings`;
configure it in code:

```python
from pathlib import Path
from data_ai.core.context_store import ContextStore

store = ContextStore(base_dir=Path("/var/lib/data-ai/contexts"))
store.save(
    "main_character", "陈默,28岁,前刑警",
    namespace="novel_red_blue", tags=["character"],
)
```

| Aspect | Default | Notes |
|---|---|---|
| `base_dir` | `~/.data-ai/contexts` | One folder per namespace, one `.json` per context. |
| File naming | `{base_dir}/{namespace}/{name}.json` | Name and namespace are file-system sanitized (`/` → `_`). |
| Versioning | Auto-increment on `save` when content changes | Old version kept in `history[]` array. |
| Concurrency | Single-process | Multiple writers to the same name will race; wrap with a lock for shared use. |
| Search | Substring (case-insensitive) | For 1k+ contexts, swap in a vector retriever (planned). |

The four enterprise presets in `plugins/agents/` use these namespaces
by default: `customer_service`, `finance`, `secretary`, and
`novel_<title>`. Override via the `namespace=` kwarg.

## Intent normalizer settings

`core/intent/recognizer.py::IntentRecognizer` runs two normalization
stages before intent matching:

1. `_normalize_query` — whitespace, `？`→`?`, `！`→`!`.
2. `_normalize_colloquial` — typo / filler / mixed-language fixes.

Stage 2 is a hard-coded `_COLLOQUIAL_FIXES` list inside the recognizer.
There is no env var or TOML key to toggle it — to extend or override,
edit the list in the source. Long entries are listed first to avoid
being eaten by shorter ones (e.g. `给我弄` precedes `弄一下`).

Failures in stage 2 fall back silently to stage 1, so the recognizer is
never destabilized by a malformed query.

## Search settings

Namespace `DATA_AI_SEARCH__`. Powers the `web_search` tool.

| Key                | Default                | Notes                            |
|--------------------|------------------------|----------------------------------|
| `engine`           | `DuckDuckGo`           | `Google`, `Baidu`, `DuckDuckGo`, `Bing`. |
| `fallback_engines` | `["DuckDuckGo", "Baidu"]` | Tried in order.              |
| `retry_delay`      | `60`                   | Seconds between full retry cycles. |
| `max_retries`      | `3`                    | Per full-cycle retry cap.        |
| `lang`             | `en`                   | ISO 639-1.                       |
| `country`          | `us`                   | ISO 3166-1 alpha-2.              |

## TOML file example

This is what `config/config.example.toml` looks like after trimming keys
that the loader doesn't read:

```toml
# config/config.toml — copy from config/config.example.toml

[llm]
model = "deepseek-chat"
base_url = "https://api.deepseek.com/v1"
api_key = "sk-..."
max_tokens = 4096
temperature = 0.2

[llm.vision]                     # read by VisionConfig, separate from [llm]
model = "gpt-4o"
api_key = "sk-..."

[sandbox]
sandbox_type = "local"           # local | docker | daytona | remote
work_dir = "/tmp/data-ai-sandbox"
timeout = 300
network_enabled = true

[memory]
enable_long_term_memory = true
memory_dir = "~/.data-ai/memory"

[search]
engine = "DuckDuckGo"
fallback_engines = ["Baidu", "Google"]
```

Anything in the example TOML that isn't read by the loader (browser,
MCP, daytona, runflow, memory_explorer, summarization sections) is left in
place for documentation only and will be wired up in a later release.

## Frontend settings

The web UI keeps its user preferences in `localStorage` and never reads a
config file at build time. The only build-time knob is the API base URL:

| Env var            | Default                 | Where it shows up              |
|--------------------|-------------------------|--------------------------------|
| `VITE_API_ENDPOINT`| `http://127.0.0.1:8000` | Settings panel default value   |

You can also change the endpoint at runtime from the in-app Settings panel.
The change is persisted in `localStorage` and used for every subsequent
request.

## What's intentionally not configurable

- **No global "feature flags".** Every feature is either built and on, or
  not yet shipped. There is no `enable_xyz = true` for the UI, agent loop,
  tool registry, or rate limiter.
- **No telemetry or analytics.** DATA-AI does not phone home. There is no
  `DATA_AI_TELEMETRY` env var, and there will not be one.
- **No async DB.** Persistence is JSON-on-disk or sqlite, depending on the
  component. There is no `DATABASE_URL`.
- **No request logging to a remote sink.** Logs go to stdout (and optionally
  to `DATA_AI_LOG_FILE` if you set it). The structured logger is `structlog`,
  not Logstash.
