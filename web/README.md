# DATA-AI · Web

The control plane. Next.js + TypeScript.

## What you need

- Node.js 22+
- [`pnpm`](https://pnpm.io/) (or `corepack enable` to get it automatically)
- A running API at `http://localhost:5001`

## Get it running locally

```bash
# from the repo root
pnpm install
cp web/.env.example web/.env.local      # tweak if needed
./dev/start-web                         # starts on :3000
```

Then open <http://localhost:3000>.

## Layout

```
web/
├── app/                 # Next.js routes
├── components/          # UI building blocks
├── context/             # global stores (theme, app, workspace)
├── service/             # API client + hooks
├── hooks/               # custom React hooks
├── models/              # typed domain objects
├── themes/              # CSS themes
├── i18n-config/         # translation setup
└── __tests__/           # unit + integration tests
```

Conventions in [`AGENTS.md`](./AGENTS.md). The short version: TypeScript strict, no `any` without a comment that says why, lint-fix before you push.
