# DATA-AI · Agent

The runtime that powers goal-driven agents inside DATA-AI. They take a goal, break it into steps, call tools, check their own work, and report back.

This is a separate Python package so it can evolve independently from the main API. The API pulls it in as a dependency.

## Layout

```
data-agent/
├── src/data_agent/      # the runtime
├── docs/                # user-facing docs (mkdocs)
├── tests/               # pytest
└── Makefile             # docs / lint / test shortcuts
```

## Local dev

```bash
cd data-agent
uv sync
uv run pytest
make docs       # serves the docs at http://localhost:8000
```

## Where the docs live

- `docs/agenton/guide/` — user guide
- `docs/agenton/api/` — API reference
- `docs/data-agent/` — runtime internals

## Conventions

Same as the main API: type hints everywhere, tests for what you change, no copy-pasted boilerplate.
