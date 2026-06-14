#!/usr/bin/env bash
# scripts/release-validate-manifest.sh — validate cli/package.json release fields.

set -euo pipefail

_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${_dir}/lib/common.sh"

cd "$(cli::root)"

SEMVER_RE='^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$'

version=$(node -p "require('./package.json').version")
channel=$(node -p "require('./package.json').datactl.channel")
min_data=$(node -p "require('./package.json').datactl.compat.minDATA")
max_data=$(node -p "require('./package.json').datactl.compat.maxDATA")

# Version form (per channel) and channel validity are enforced by
# release-naming.mjs validate below — the single source for those rules.

[[ "$min_data" =~ $SEMVER_RE ]] || die "invalid datactl.compat.minDATA: ${min_data}"
[[ "$max_data" =~ $SEMVER_RE ]] || die "invalid datactl.compat.maxDATA: ${max_data}"

case "$min_data" in *[xX*]*) die "wildcards not allowed in minDATA: ${min_data}" ;; esac
case "$max_data" in *[xX*]*) die "wildcards not allowed in maxDATA: ${max_data}" ;; esac

cmp=$(node -e "
const a = process.argv[1].split('-')[0].split('.').map(Number)
const b = process.argv[2].split('-')[0].split('.').map(Number)
for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) { console.log(a[i] < b[i] ? -1 : 1); process.exit(0) }
}
console.log(0)
" "$min_data" "$max_data")

[[ "$cmp" -le 0 ]] || die "minDATA (${min_data}) > maxDATA (${max_data})"

node "${_dir}/release-naming.mjs" validate >/dev/null

log::info "manifest valid: version=${version} channel=${channel} compat=${min_data}..${max_data}"
