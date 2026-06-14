# DATA-AI

> An AI agent that finally makes sense of your enterprise data.

Look. We know the problem. Every company is sitting on a pile of financial reports, internal docs, customer records, project files, that one folder nobody dares to touch, and a few Excel sheets that are basically the company's nervous system. None of it talks to each other, nobody can find anything, and the people who actually understand the data are drowning in requests.

We built **DATA-AI** for that.

**DATA-AI** is a self-hosted AI agent that lives next to your enterprise data — finance, internal knowledge, the stuff that matters — and does the boring work for you. Ask it a question, it digs through your files and gives you an answer with sources. Point it at a task, it runs the task. Want a weekly report from `/finance/2025-Q4/`? Done in two minutes, not two days.

## What's in the box

- **Knowledge bases that actually know your stuff** — feed it PDFs, Word docs, spreadsheets, Notion exports, internal wikis, plain-text dumps. It indexes them, learns from them, and answers questions like a colleague who's been there for ten years.
- **Workflows you draw, not code** — drag a few blocks, wire them up, save. Data cleanup, monthly reports, "summarize everything new in `/legal/`", "flag every contract expiring this quarter", whatever.
- **Agents that finish the job** — give one a goal. It breaks the goal into steps, calls the right tools, checks its own work, and tells you what it did. Less babysitting, more shipping.
- **Models, your call** — OpenAI, Claude, DeepSeek, your local Llama, that obscure one your team swears by. Plug it in, the agent uses it.
- **Vector DB, your choice** — pgvector, Milvus, Weaviate, Qdrant, Elasticsearch. Use whatever you already have running.
- **A web UI people don't hate** — a console for admins, a chat for end users, an API for engineers who'd rather not click.

## Why we built it

We tried the SaaS options. Then the "open-core" options. Then building it ourselves with raw OpenAI API calls, until we were writing the same boilerplate for the fourth time and got tired.

So we made something we'd actually use:

- **Self-hosted** — runs on a single Linux box, no Kubernetes required.
- **Your data stays yours** — nothing leaves your network, every model call is auditable.
- **No sales calls** — it's open source, the code's right here.
- **No "we'll add that in Q3"** — features get built when someone needs them.

## Get it running

The easy way (Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

The manual way (no Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # one terminal
./dev/start-web    # another
```

Then open <http://localhost:3000>. Full guide in [`docs/`](./docs/).

## Architecture, in one paragraph

Python + Flask on the backend, organized by domain so you can find things. Next.js on the frontend (the modern kind, not the 2018 kind). PostgreSQL for the boring structured stuff. Your choice of vector DB for embeddings. Celery + Redis for everything that shouldn't block the user. A plugin system so you can bolt on models, tools, and integrations without forking the repo.

## Contributing

We take pull requests. Read [CONTRIBUTING.md](./CONTRIBUTING.md) first, so you don't waste a Saturday.

## License

[Apache 2.0](./LICENSE). Do what you want, just keep the copyright notice.

---

<p align="center">
  <a href="./docs/zh-CN/README.md">简体中文</a> ·
  <a href="./docs/zh-TW/README.md">繁體中文</a> ·
  <a href="./docs/ja-JP/README.md">日本語</a> ·
  <a href="./docs/ko-KR/README.md">한국어</a> ·
  <a href="./docs/es-ES/README.md">Español</a> ·
  <a href="./docs/fr-FR/README.md">Français</a> ·
  <a href="./docs/de-DE/README.md">Deutsch</a> ·
  <a href="./docs/pt-BR/README.md">Português</a> ·
  <a href="./docs/it-IT/README.md">Italiano</a> ·
  <a href="./docs/vi-VN/README.md">Tiếng Việt</a> ·
  <a href="./docs/tr-TR/README.md">Türkçe</a> ·
  <a href="./docs/hi-IN/README.md">हिन्दी</a>
</p>
