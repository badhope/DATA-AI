# DATA-AI · E2E

End-to-end tests. Cucumber + Playwright under the hood.

## Running

Make sure the API and Web are up first (see [`/api/README.md`](../api/README.md) and [`/web/README.md`](../web/README.md)).

```bash
pnpm install
pnpm e2e                # headless
pnpm e2e:headed         # with a browser
pnpm e2e:full           # full suite, including slow paths
```

## Layout

```
e2e/
├── features/            # Gherkin feature files
├── scripts/             # test runner glue
├── support/             # step definitions
└── fixtures/            # test data
```

If you write a new feature, please also write the steps. Skeleton steps are fine, but no orphan features.
