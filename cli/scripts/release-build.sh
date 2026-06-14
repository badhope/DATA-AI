#!/usr/bin/env bash
# scripts/release-build.sh — cross-compile datactl to standalone binaries
# for every release target via `bun build --compile`.
#
# Bun consumes bin/run.ts (which imports from src/) directly — no `pnpm build`
# / dist/ step needed.
#
# Prereqs:
#   - All @napi-rs/keyring native variants present in node_modules. Append
#     cli/scripts/cross-arch.pnpm.yaml onto pnpm-workspace.yaml before the
#     install that first populates node_modules so pnpm fetches every
#     foreign-arch prebuild (the CLI Release workflow does this).
#
# Env (all optional; defaults derived from cli/package.json + git):
#   CLI_VERSION        — package.json `version`
#   DATACTL_CHANNEL    — package.json `datactl.channel`
#   DATACTL_MIN_DATA   — package.json `datactl.compat.minDATA`
#   DATACTL_MAX_DATA   — package.json `datactl.compat.maxDATA`
#   DATACTL_COMMIT     — `git rev-parse HEAD` (or "unknown")
#   DATACTL_BUILD_DATE — current UTC time
#
# Output: dist/bin/datactl-v<CLI_VERSION>-<target>[.exe]

set -euo pipefail

_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${_dir}/lib/common.sh"

require bun

cli_root="$(cli::root)"
entry="${cli_root}/bin/run.ts"
out_dir="${cli_root}/dist/bin"

read_pkg() { node -p "require('${cli_root}/package.json').$1" 2>/dev/null; }
naming() { node "${_dir}/release-naming.mjs" "$@"; }

CLI_VERSION="${CLI_VERSION:-$(read_pkg version)}"
DATACTL_CHANNEL="${DATACTL_CHANNEL:-$(read_pkg datactl.channel)}"
DATACTL_MIN_DATA="${DATACTL_MIN_DATA:-$(read_pkg datactl.compat.minDATA)}"
DATACTL_MAX_DATA="${DATACTL_MAX_DATA:-$(read_pkg datactl.compat.maxDATA)}"
DATACTL_COMMIT="${DATACTL_COMMIT:-$(git -C "$cli_root" rev-parse HEAD 2>/dev/null || echo unknown)}"
DATACTL_BUILD_DATE="${DATACTL_BUILD_DATE:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"

[[ "$CLI_VERSION" != "undefined" ]] || die "CLI_VERSION could not be derived from package.json"

[[ -f "$entry" ]] || die "entry not found: $entry"

rm -rf "$out_dir"
mkdir -p "$out_dir"

# Build-info globals (referenced as bare identifiers in src/version/info.ts).
# Each value must be a JS expression — wrap strings as JSON-quoted strings.
defines=(
    "--define" "__DATACTL_VERSION__=\"${CLI_VERSION}\""
    "--define" "__DATACTL_CHANNEL__=\"${DATACTL_CHANNEL}\""
    "--define" "__DATACTL_MIN_DATA__=\"${DATACTL_MIN_DATA}\""
    "--define" "__DATACTL_MAX_DATA__=\"${DATACTL_MAX_DATA}\""
    "--define" "__DATACTL_COMMIT__=\"${DATACTL_COMMIT}\""
    "--define" "__DATACTL_BUILD_DATE__=\"${DATACTL_BUILD_DATE}\""
)

# Targets and asset names come from cli/package.json `datactl.release` via
# release-naming.mjs (single source of truth). Each line: bunTarget<TAB>id<TAB>exe.
while IFS=$'\t' read -r bun_target asset_target _exe; do
    out="${out_dir}/$(naming asset "$CLI_VERSION" "$asset_target")"
    log::info "compiling ${asset_target} -> $(basename "$out")..."
    bun build "$entry" \
        --target="$bun_target" \
        --compile \
        --minify \
        "${defines[@]}" \
        --outfile="$out" >/dev/null
done < <(naming targets)

log::info "built $(find "$out_dir" -type f | wc -l | tr -d ' ') binaries:"
ls -lh "$out_dir" >&2
