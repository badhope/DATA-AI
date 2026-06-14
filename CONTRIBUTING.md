# Contributing to DATA-AI

So you want to poke at the code. Cool, we like that.

A few ground rules so nobody wastes a weekend:

## Before you start

- Open or comment on an issue first, unless it's a typo. PRs without context tend to sit.
- For big changes, sketch the approach in the issue, get a 👍, *then* write code.
- New model providers, tools, or plugins usually belong in their own plugin repo, not here.

## How we work

- **Small PRs are good PRs.** If your diff is over 500 lines, it's almost certainly two PRs.
- **Test what you change.** Add a test, or explain why you can't.
- **Run the linters and type checks.** Both backend and frontend. CI will catch it anyway, but locally is faster.
- **Update docs if the user-facing behavior changes.**

## Backend (`/api`)

- Read `api/AGENTS.md` for the architecture and conventions.
- Run backend commands through `uv run --project api <command>`.
- Python 3.12, type hints everywhere, prefer `TypedDict` over `dict` for clarity.
- Tests use `pytest`, follow Arrange-Act-Assert.

## Frontend (`/web`)

- Read `web/AGENTS.md`.
- TypeScript strict, no `any` unless you've begged in a comment.
- `pnpm lint:fix` and `pnpm type-check` before pushing.

## Reporting bugs

Include:

- What you did, step by step
- What you expected
- What actually happened
- Logs, screenshots, error messages — anything helps

## License

By sending a PR, you agree your contribution is licensed under the project's [LICENSE](./LICENSE).

## Code of conduct

Be kind. Argue ideas, not people. No harassment, no personal attacks. We take the boring, professional version of this seriously.

That's it. Welcome aboard.
