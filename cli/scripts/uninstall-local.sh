#!/bin/sh
# uninstall-local.sh — remove a locally installed datactl.
# Run via: pnpm uninstall:local
set -eu

PREFIX="${DATACTL_PREFIX:-${HOME}/.local}"
SHARE_DIR="${PREFIX}/share/datactl"
BIN_LINK="${PREFIX}/bin/datactl"

rm -rf "$SHARE_DIR"
rm -f  "$BIN_LINK"
echo "removed ${SHARE_DIR} and ${BIN_LINK}"
