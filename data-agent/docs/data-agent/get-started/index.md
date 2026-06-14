# Get started with DATA Agent

This guide walks through the smallest end-to-end path for the current DATA Agent
runtime: install dependencies, configure the server, start it, then use the Python
client to create one plugin-daemon-backed run.

## Prerequisites

Install or prepare:

- Python 3.12 or newer
- `uv`
- Redis
- a reachable DATA plugin daemon
- a plugin/provider already available through that plugin daemon, such as
  `langgenius/openai`

## Install dependencies

From the repository root, enter the `data-agent` package and install all extras
and dependency groups:

```bash
cd data-agent
uv sync --all-extras --all-groups
```

Only the `server` extra is required to run the API server, but installing all
extras and groups gives you the local test, docs, and server dependencies in one
environment.

## Start Redis

Skip this step if you already have a reachable Redis instance.

```bash
docker run -d \
  --name data-agent-redis \
  -p 6379:6379 \
  redis:7-alpine
```

## Configure the server

Create or update `.env` in the `data-agent` directory:

```bash
cat > .env <<'EOF'
DATA_AGENT_REDIS_URL=redis://localhost:6379/0
DATA_AGENT_REDIS_PREFIX=data-agent

DATA_AGENT_PLUGIN_DAEMON_URL=http://localhost:5002
DATA_AGENT_PLUGIN_DAEMON_API_KEY=replace-with-plugin-daemon-server-key
EOF
```

The minimum settings are:

- `DATA_AGENT_REDIS_URL`: Redis connection URL used for run records and event
  streams.
- `DATA_AGENT_REDIS_PREFIX`: Redis key prefix for this server.
- `DATA_AGENT_PLUGIN_DAEMON_URL`: base URL for the DATA plugin daemon.
- `DATA_AGENT_PLUGIN_DAEMON_API_KEY`: API key sent by the server to the plugin
  daemon. In a DATA Docker setup this is usually the value previously configured
  as `PLUGIN_DAEMON_KEY`.

See `.example.env` for the full server settings template.

If you plan to run `data.shell`, also configure `DATA_AGENT_SHELLCTL_ENTRYPOINT`
and, when shell jobs need to call back with the `data-agent` command, set
`DATA_AGENT_STUB_URL` plus a 32-byte base64url
`DATA_AGENT_SERVER_SECRET_KEY` as documented in `.example.env`.

## Start the DATA Agent server

For a normal local server process:

```bash
make serve
```

For development with uvicorn reload:

```bash
make dev
```

Both commands serve the API at:

```text
http://127.0.0.1:8000
```

The equivalent development command is:

```bash
uv run --extra server uvicorn data_agent.server.app:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload
```

`ServerSettings` reads `.env` from the current `data-agent` directory, or from
`data-agent/.env` when the command is run from the repository root.

## Create a Python client example

In another shell, keep working from the `data-agent` directory. Create
`run_data_agent_client.py` with the example below, then replace the placeholder
tenant id and provider credential values.

```python {test="skip" lint="skip"}
import asyncio
import json
import sys

from agenton_collections.layers.plain import PLAIN_PROMPT_LAYER_TYPE_ID, PromptLayerConfig
from data_agent.client import Client
from data_agent.layers.execution_context import DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID, DATAExecutionContextLayerConfig
from data_agent.layers.data_plugin import (
    DATA_PLUGIN_LLM_LAYER_TYPE_ID,
    DATAPluginLLMLayerConfig,
)
from data_agent.protocol import DATA_AGENT_MODEL_LAYER_ID, CreateRunRequest, RunComposition, RunLayerSpec


API_BASE_URL = "http://127.0.0.1:8000"

TENANT_ID = "replace-with-tenant-id"
PLUGIN_ID = "langgenius/openai"
USER_ID: str | None = None

# Keep these aligned with DATA_AGENT_PROVIDER and DATA_AGENT_MODEL_NAME in data-agent/.env.
MODEL_PROVIDER = "replace-with-provider-from-data-agent-env"
MODEL_NAME = "replace-with-model-from-data-agent-env"
MODEL_CREDENTIALS: dict[str, str | int | float | bool | None] = {
    "api_key": "replace-with-provider-key",
}

SYSTEM_PROMPT = "You are a concise assistant."
USER_PROMPT = "用一句话介绍 DATA Agent。"


def build_request() -> CreateRunRequest:
    return CreateRunRequest(
        composition=RunComposition(
            layers=[
                RunLayerSpec(
                    name="prompt",
                    type=PLAIN_PROMPT_LAYER_TYPE_ID,
                    config=PromptLayerConfig(prefix=SYSTEM_PROMPT, user=USER_PROMPT),
                ),
                RunLayerSpec(
                    name="execution_context",
                    type=DATA_EXECUTION_CONTEXT_LAYER_TYPE_ID,
                    config=DATAExecutionContextLayerConfig(
                        tenant_id=TENANT_ID,
                        user_id=USER_ID,
                        invoke_from="workflow_run",
                    ),
                ),
                RunLayerSpec(
                    name=DATA_AGENT_MODEL_LAYER_ID,
                    type=DATA_PLUGIN_LLM_LAYER_TYPE_ID,
                    deps={"execution_context": "execution_context"},
                    config=DATAPluginLLMLayerConfig(
                        plugin_id=PLUGIN_ID,
                        model_provider=MODEL_PROVIDER,
                        model=MODEL_NAME,
                        credentials=MODEL_CREDENTIALS,
                    ),
                ),
            ],
        ),
    )


async def main() -> int:
    async with Client(base_url=API_BASE_URL, stream_timeout=None) as client:
        run = await client.create_run(build_request())
        print(f"created run: {run.run_id}, status={run.status}")

        async for event in client.stream_events(run.run_id):
            print(event.model_dump_json(indent=2))

            if event.type == "run_succeeded":
                print("final output:")
                print(json.dumps(event.data.output, ensure_ascii=False, indent=2))
                return 0

            if event.type == "run_failed":
                print(f"run failed: {event.data.error}", file=sys.stderr)
                return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

## Run the client example

The server-side `.env` controls how DATA Agent reaches the plugin daemon. The
client example controls which tenant/plugin/provider/model and provider
credentials the run uses.

Run the example from the `data-agent` directory:

```bash
uv run python ./run_data_agent_client.py
```

The shape of `MODEL_CREDENTIALS` depends on the selected plugin provider's
credential schema. The `{"api_key":"..."}` value above is only an OpenAI-style
example.

Set `MODEL_PROVIDER` and `MODEL_NAME` to the same values as
`DATA_AGENT_PROVIDER` and `DATA_AGENT_MODEL_NAME` in `data-agent/.env`.

## Troubleshooting

If the run fails, check these items first:

1. Redis is running and reachable from the DATA Agent server.
2. The DATA Agent server is listening on `127.0.0.1:8000`.
3. `DATA_AGENT_PLUGIN_DAEMON_URL` points to the correct plugin daemon.
4. `DATA_AGENT_PLUGIN_DAEMON_API_KEY` matches the plugin daemon server key.
5. `PLUGIN_ID`, `MODEL_PROVIDER`, and `MODEL_NAME` in the client example match
   the corresponding values configured in `data-agent/.env` and a provider
   available through the plugin daemon.
6. `MODEL_CREDENTIALS` matches that provider's credential schema.
