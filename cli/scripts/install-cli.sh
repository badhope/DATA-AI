#!/bin/sh
# install-cli.sh — one-line datactl installer. datactl ships as assets on DATA
# GitHub Releases; this installs the build matching your DATA version.
#
# usage:
#   curl -fsSL https://raw.githubusercontent.com/langgenius/data/main/cli/scripts/install-cli.sh | sh
#
# env:
#   DATA_VERSION     DATA release tag to install datactl from (e.g. 1.14.2). Primary key.
#   DATACTL_VERSION  datactl version pin (used only when DATA_VERSION is unset).
#   DATACTL_PREFIX   install dir (default $HOME/.local); binary -> $PREFIX/bin/datactl
#   DATACTL_REPO     release source repo (default langgenius/data)
# requires: curl, uname, sort -V, and sha256sum or shasum.
set -eu

REPO="${DATACTL_REPO:-langgenius/data}"
PREFIX="${DATACTL_PREFIX:-${HOME}/.local}"
DATA_VERSION="${DATA_VERSION:-}"
DATACTL_VERSION="${DATACTL_VERSION:-}"
API="https://api.github.com/repos/${REPO}"
DL="https://github.com/${REPO}/releases/download"

err() { printf '%s\n' "install-cli: $*" >&2; }
die() { err "$*"; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required"; }
re_escape() { printf '%s' "$1" | sed 's/[][\\.^$*+?(){}|/]/\\&/g'; }

detect_target() {
    case "$(uname -s)" in
        Linux*)  _os=linux ;;
        Darwin*) _os=darwin ;;
        *)       die "unsupported OS: $(uname -s) (use install.ps1 on Windows)" ;;
    esac
    case "$(uname -m)" in
        x86_64|amd64)  _arch=x64 ;;
        arm64|aarch64) _arch=arm64 ;;
        *)             die "unsupported arch: $(uname -m)" ;;
    esac
    printf '%s-%s' "$_os" "$_arch"
}

# list_asset_names  (reads release JSON on stdin) -> one datactl asset name per line
list_asset_names() {
    grep -oE '"name"[[:space:]]*:[[:space:]]*"datactl-v[^"]*"' \
        | sed -E 's#.*"name"[[:space:]]*:[[:space:]]*"([^"]*)".*#\1#'
}

# pick_asset TARGET  (reads release JSON on stdin) -> highest-semver matching asset name
pick_asset() {
    _target=$(re_escape "$1")
    list_asset_names \
        | grep -E -- "-${_target}(\\.exe)?\$" \
        | grep -vE -- '-checksums\.txt$' \
        | sort -V | tail -1
}

# asset_version ASSET_NAME TARGET -> datactl version embedded in the name
asset_version() {
    _target=$(re_escape "$2")
    printf '%s' "$1" | sed -E "s#^datactl-v(.*)-${_target}(\\.exe)?\$#\\1#"
}

# list_release_tags  (reads /releases array JSON on stdin) -> tag per line, newest first
list_release_tags() {
    grep -oE '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' \
        | sed -E 's#.*:[[:space:]]*"([^"]*)".*#\1#'
}

fetch_json() {
    curl -fsSL -H "Accept: application/vnd.github+json" "$1"
}

# find_release_for_datactl WANT TARGET -> newest DATA tag whose assets host that datactl build
find_release_for_datactl() {
    _want="$1"
    _target="$2"
    _raw=$(fetch_json "${API}/releases?per_page=100") \
        || die "failed to query ${REPO} releases (network error or GitHub API rate limit)"
    _tags=$(printf '%s' "$_raw" | list_release_tags)
    for _t in $_tags; do
        _rel=$(fetch_json "${API}/releases/tags/${_t}") \
            || { err "fetch failed for ${_t}, skipping"; continue; }
        _name=$(printf '%s' "$_rel" | pick_asset "$_target")
        [ -n "$_name" ] || continue
        if [ "$(asset_version "$_name" "$_target")" = "$_want" ]; then
            printf '%s' "$_t"
            return 0
        fi
    done
    return 1
}

resolve_release() {
    _target="$1"
    if [ -n "$DATA_VERSION" ]; then
        REL=$(fetch_json "${API}/releases/tags/${DATA_VERSION}") \
            || die "DATA release ${DATA_VERSION} not found"
        DATA_TAG="$DATA_VERSION"
    elif [ -n "$DATACTL_VERSION" ]; then
        DATA_TAG=$(find_release_for_datactl "$DATACTL_VERSION" "$_target") \
            || die "datactl ${DATACTL_VERSION} not found on any DATA release"
        REL=$(fetch_json "${API}/releases/tags/${DATA_TAG}") \
            || die "failed to fetch DATA release ${DATA_TAG}"
    else
        REL=$(fetch_json "${API}/releases/latest") \
            || die "failed to query latest DATA release (set DATA_VERSION to pin one)"
        DATA_TAG=$(printf '%s' "$REL" | list_release_tags | head -1)
        [ -n "$DATA_TAG" ] || die "could not parse a tag from the latest DATA release"
    fi
}

main() {
    need curl
    need uname
    sort -V /dev/null >/dev/null 2>&1 || die "sort with -V support is required (install coreutils)"
    if command -v sha256sum >/dev/null 2>&1; then
        HASH="sha256sum"
    elif command -v shasum >/dev/null 2>&1; then
        HASH="shasum -a 256"
    else
        die "need sha256sum or shasum"
    fi

    target=$(detect_target)
    resolve_release "$target"

    asset=$(printf '%s' "$REL" | pick_asset "$target")
    [ -n "$asset" ] || die "no datactl published for DATA ${DATA_TAG} (target ${target}); set DATA_VERSION to a release that has one"
    version=$(asset_version "$asset" "$target")
    checksums="datactl-v${version}-checksums.txt"
    base="${DL}/${DATA_TAG}"

    tmp=$(mktemp -d 2>/dev/null || mktemp -d -t datactl-install)
    trap 'rm -rf "$tmp"' EXIT INT TERM

    printf 'downloading %s (DATA %s)...\n' "$asset" "$DATA_TAG"
    curl -fsSL "${base}/${asset}" -o "${tmp}/${asset}" \
        || die "download failed: ${base}/${asset}"
    curl -fsSL "${base}/${checksums}" -o "${tmp}/${checksums}" \
        || die "checksum manifest download failed: ${base}/${checksums}"

    _pattern=$(re_escape "$asset")
    _sumline=$(grep -E -- "[[:space:]]${_pattern}\$" "${tmp}/${checksums}") || true
    [ -n "$_sumline" ] || die "no checksum entry for ${asset}"
    (
        cd "$tmp"
        printf '%s\n' "$_sumline" | $HASH -c -
    ) || die "checksum mismatch for ${asset}"

    bin_dir="${PREFIX}/bin"
    mkdir -p "$bin_dir"
    target_bin="${bin_dir}/datactl"
    cp "${tmp}/${asset}" "$target_bin"
    chmod +x "$target_bin"

    printf '\ndifyctl v%s installed (from DATA %s): %s\n' "$version" "$DATA_TAG" "$target_bin"

    case ":${PATH}:" in
        *":${bin_dir}:"*)
            "$target_bin" version >/dev/null 2>&1 \
                && printf 'verify: run "datactl version"\n' \
                || err "binary present but failed to execute; check ${target_bin}"
            ;;
        *)
            printf '\n%s is not on your PATH. Add this to your shell profile:\n' "$bin_dir"
            printf '  export PATH="%s:$PATH"\n' "$bin_dir"
            ;;
    esac
}

if [ "${DATACTL_INSTALL_LIB:-0}" != "1" ]; then
    main "$@"
fi
