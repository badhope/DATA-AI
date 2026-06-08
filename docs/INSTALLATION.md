# Installation

This document covers installing the DATA-AI backend and the optional web UI.
Both are independent — you can run the backend without the UI, or the UI
against a remote backend.

## Contents

- [Requirements](#requirements)
- [Backend (Python)](#backend-python)
- [Web UI (Node)](#web-ui-node)
- [Sanity check](#sanity-check)
- [Common issues](#common-issues)
- [Sandbox one-shot setup](#sandbox-one-shot-setup)

## Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python    | 3.10    | 3.11 or 3.12 |
| Node.js   | 18 LTS  | 20 LTS      |
| RAM       | 2 GB    | 4 GB        |
| Disk      | 1 GB    | 3 GB        |

Operating system: Linux, macOS, or Windows via WSL2. The sandbox only runs on
Linux and macOS; on Windows it falls back to a non-exec stub.

You also need at least one of:

- An LLM API key (OpenAI, Anthropic, DeepSeek, Qwen, …) for real replies, or
- Nothing — the backend ships with an `offline-chat` model that returns
  templated responses so you can test routing, memory, and tools without
  burning tokens.

## Backend (Python)

The package is `data-ai`. Everything is installed from `pyproject.toml`.

### 1. Clone and enter a virtual environment

```bash
git clone https://github.com/your-org/DATA-AI.git
cd DATA-AI

python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows PowerShell
```

### 2. Install the package

```bash
# Core only — fast, no optional deps
pip install -e .

# With all optional extras (vector store, document parsing, browser automation)
pip install -e ".[all]"
```

Extras available:

| Extra         | Adds                                                  |
|---------------|-------------------------------------------------------|
| `anthropic`   | `anthropic` SDK (only required for the Anthropic client) |
| `google`      | `google-generativeai` SDK                             |
| `chroma`      | `chromadb` for vector memory                          |
| `embeddings`  | `sentence-transformers` for local embeddings          |
| `documents`   | `PyPDF2`, `python-docx`, `openpyxl`, `python-pptx`    |
| `office`      | `pillow`, plus everything in `documents`              |
| `browser`     | `playwright` for the browser-use tool                 |
| `dev`         | `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`      |
| `all`         | Everything above                                      |

### 3. Configure (optional)

The backend works out of the box with `offline-chat`. To use a real provider,
either drop a TOML file or set environment variables — see
[`CONFIGURATION.md`](CONFIGURATION.md) for the full reference.

The fastest path:

```bash
export DATA_AI_API_KEYS="sk-..."                       # one or more comma-separated keys
export DATA_AI_LLM__MODEL="deepseek-chat"              # nested setting (note the double underscore)
export DATA_AI_LLM__API_KEY="sk-..."                   # or per-model override
```

### 4. Start the server

The console script exposes `version`, `chat`, `rag`, and `list_models`. For the
HTTP server, the supported entry points are:

```bash
# Preferred — uses the in-tree factory (binds to 0.0.0.0:8000)
PYTHONPATH=src python -m data_ai.core.api.server

# Same thing, via the run_server() helper (lets you pass host/port/reload)
PYTHONPATH=src python -c "from data_ai.core.api.server import run_server; run_server(host='127.0.0.1', port=8000)"

# Or call uvicorn yourself (handy with --reload during development)
PYTHONPATH=src uvicorn data_ai.core.api.server:app --reload
```

There is no `data-ai serve` subcommand — the API server is intentionally a
library entry point so that tests can import `app` from
`data_ai.core.api.server` without going through a CLI.

The API is then on <http://127.0.0.1:8000>. Swagger UI is at `/docs`,
ReDoc at `/redoc`.

## Web UI (Node)

The web UI is a Vite + React 19 SPA. It is built to a static bundle and can
be served from any static host, including `file://` for offline use.

```bash
cd web
npm install
npm run dev          # http://127.0.0.1:5173
```

For a production bundle:

```bash
npm run build        # output → web/dist/ (relative paths, drop into any static server)
```

The frontend talks to the backend at the URL configured in the Settings
panel (or at `VITE_API_ENDPOINT` if you set it before `npm run build`).
There is no proxy in production — the UI and the API are decoupled.

## Sanity check

In one terminal:

```bash
data-ai serve --port 8000
```

In another:

```bash
# OpenAI-compatible health probe
curl http://127.0.0.1:8000/v1/models

# Quick chat round-trip
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"offline-chat","messages":[{"role":"user","content":"hi"}]}'
```

Expected: a 200 response with a JSON body. If you see `401`, set
`DATA_AI_DEV_MODE=true` or add your key to `DATA_AI_API_KEYS`.

## Common issues

**`ModuleNotFoundError: data_ai` after `pip install -e .`**
Your virtual environment isn't activated, or you installed into a different
interpreter. Run `which python` and confirm it points inside `.venv/`.

**`Address already in use` on port 8000**
Either pass `--port 8001` to `data-ai serve`, or stop the previous process.
On Linux: `pkill -f "data_ai serve"`.

**`pydantic_settings` complains about an unknown env var**
You have a stray `DATA_AI_*` variable in your shell. The loader is strict
about types — unset it and try again.

**Sandbox returns "permission denied" on a directory**
The local sandbox runs as your user. Make sure `data_ai.sandbox.work_dir`
points somewhere writable, or change it to a temp dir.

**Anthropic / Google client fails with `ImportError: anthropic`**
Install the matching extra: `pip install -e ".[anthropic]"` or
`pip install -e ".[google]"`. Core only pulls the OpenAI SDK.

**Frontend cannot reach the backend**
Open Settings in the UI, set the API base URL to wherever the backend
listens, and click "Test connection". The default is `http://127.0.0.1:8000`.

## Sandbox one-shot setup

If you are running DATA-AI inside a fresh container (Daytona, Docker,
Codespaces, etc.) and you need every system tool, Python library, and
CJK font installed in one shot, run:

```bash
cd /workspace/DATA-AI
bash scripts/setup_sandbox.sh
```

What it installs:

| Layer | What | Why |
|---|---|---|
| `apt` | `libreoffice-{writer,calc,impress,core}`, `pandoc`, `ghostscript`, `poppler-utils`, `imagemagick`, `fonts-wqy-microhei`, `fonts-noto-cjk` | Office / PDF round-trip and CJK rendering |
| `pip` (core) | `openpyxl`, `python-docx`, `python-pptx`, `pypdf`, `PyPDF2`, `reportlab`, `matplotlib`, `Pillow`, `xlsxwriter`, `requests` | Document I/O and chart rendering |
| `pip` (extra) | `pandas`, `PyMuPDF`, `pdfplumber`, `docxtpl`, `docxcompose` | Data analysis and advanced Office workflows |
| `fc-cache` | Rebuild the fontconfig cache so matplotlib / reportlab see the new fonts | Chinese characters without boxes |
| `verify` | `python -c "import …"` + `command -v …` | Fail loudly if something is missing |

The script is idempotent and exits on the first error (`set -e`). Run
it once per fresh sandbox; updates are additive.

## Next steps

- [`CONFIGURATION.md`](CONFIGURATION.md) — every env var and TOML key
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — how the components fit together
- [`MODEL_PROVIDERS.md`](MODEL_PROVIDERS.md) — the 19 supported providers
