#!/usr/bin/env bash
# Quiet local install for BOSS-Sentinel.
# Avoids apt's "_apt ... Permission denied / unsandboxed as root" notice that
# appears when installing a .deb straight from a private home directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

find_deb() {
  local candidates=()
  while IFS= read -r f; do candidates+=("$f"); done < <(ls -1 "$SCRIPT_DIR"/boss-sentinel_*.deb 2>/dev/null | sort -V || true)
  while IFS= read -r f; do candidates+=("$f"); done < <(ls -1 "$SCRIPT_DIR"/../install/boss-sentinel_*.deb 2>/dev/null | sort -V || true)
  while IFS= read -r f; do candidates+=("$f"); done < <(ls -1 "$SCRIPT_DIR"/../releases/boss-sentinel_*.deb 2>/dev/null | sort -V || true)
  while IFS= read -r f; do candidates+=("$f"); done < <(ls -1 "$SCRIPT_DIR"/../dist/boss-sentinel_*.deb 2>/dev/null | sort -V || true)
  if ((${#candidates[@]} == 0)); then
    echo "error: no boss-sentinel_*.deb found near $SCRIPT_DIR" >&2
    exit 1
  fi
  printf '%s\n' "${candidates[-1]}"
}

DEB="$(find_deb)"
TMP="$(mktemp /tmp/boss-sentinel_XXXXXX.deb)"
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

cp -f "$DEB" "$TMP"
chmod 644 "$TMP"

echo "Installing $(basename "$DEB") ..."
# Install from /tmp via dpkg — no apt home-dir sandbox warning.
if ! sudo dpkg -i "$TMP"; then
  echo "Resolving dependencies..."
  sudo apt-get install -f -y
fi

echo "Done. Launch with: boss-sentinel"
