# DATA-AI · API

The backend service. Python + Flask, organized by domain so you can find things.

## What you need

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/) — our package manager
- A running PostgreSQL (with the `data` database) and Redis

## Get it running locally

```bash
# from the repo root
./dev/setup          # copies .env files, installs deps
./dev/start-api      # starts the API on :5001 (runs migrations first)
```

By default it expects:

- PostgreSQL at `localhost:5432`, user `postgres`, password `dataai123456`, db `data`
- Redis at `localhost:6379`, password `dataai123456`

Change those in `api/.env` if your setup is different.

## Layout

```
api/
├── controllers/         # HTTP routes, thin
├── services/            # business logic
├── core/                # model providers, indexing, hosting
├── models/              # SQLAlchemy models
├── fields/              # marshmallow-style field defs
├── tasks/               # Celery background jobs
├── migrations/          # alembic migrations
└── tests/               # pytest
```

Conventions live in [`AGENTS.md`](./AGENTS.md). The short version: small PRs, type hints, tests for what you change, no `dict` where a `TypedDict` will do.
