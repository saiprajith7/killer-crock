#!/usr/bin/env bash
# Compat entrypoint — forwards to install-unified.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || HERE=""
if [[ -n "$HERE" && -f "$HERE/install-unified.sh" ]]; then
  exec bash "$HERE/install-unified.sh" "$@"
fi
exec bash <(curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/install-unified.sh) "$@"
