# DATA-AI · Docker

One-file container deployment for the whole stack.

## Quick start

```bash
cd docker
cp .env.example .env             # tweak as needed
docker compose up -d
```

That's it. Web on `:3000`, API on `:5001`, Postgres + Redis + the vector DB you chose in `.env`.

## Switching the vector database

Set `VECTOR_STORE` in `docker/.env` to one of: `weaviate`, `milvus`, `qdrant`, `opensearch`, `pgvector`, `chroma`, `tidb`, `elasticsearch`. The matching container starts; the API picks it up automatically.

## SSL

See [`certbot/README.md`](./certbot/README.md) for HTTPS setup.

## Env files

`docker/.env` is your local startup config. Optional advanced stuff lives in `docker/envs/*.env.example` — copy without the `.example` suffix to enable.

If your `.env` is drifting from `.env.example`, run `python data-env-sync.py` to reconcile without nuking your overrides.
