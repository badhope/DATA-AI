# DATA-AI · CLI (`datactl`)

Command-line client for the DATA-AI platform. Browser device-flow login, list and inspect apps, run them with structured input, parse output as JSON / YAML / human.

## Install

Pre-built standalone binaries ship as GitHub Actions workflow artifacts on this repo. The installer pulls the latest successful run, verifies sha256, and drops the binary into `$HOME/.local/bin/datactl`.

```sh
export GH_TOKEN=<your-pat-with-actions:read>
curl -fsSL https://raw.githubusercontent.com/<your-org>/DATA-AI/main/cli/scripts/install-cli.sh | sh
```

| Env              | Default                  | Purpose                                               |
| ---------------- | ------------------------ | ----------------------------------------------------- |
| `GH_TOKEN`       | —                        | PAT (or `GITHUB_TOKEN`) with `actions:read`.          |
| `DATACTL_PREFIX` | `$HOME/.local`           | Install root. Binary lands at `<prefix>/bin/datactl`. |
| `DATACTL_REPO`   | `<your-org>/DATA-AI`     | Source repo.                                          |
| `DATACTL_BRANCH` | `main`                   | Branch to pick the latest successful run from.        |

Supported targets: `darwin-arm64`, `darwin-x64`, `linux-arm64`, `linux-x64`, `windows-x64.exe`.

## Quickstart

```sh
datactl auth login                          # browser device flow
datactl get app                             # list apps in the default workspace
datactl describe app <app-id>               # inspect parameters
datactl run app <app-id> --input '{}'       # run it
```

See `datactl --help` for the full command tree.
