#!/usr/bin/env bash
# Build the vitaheal .deb into ./dist without writing to the parent directory.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist packaging/bundled-debs
# Ensure offline-install helper debs exist (fonts + notify-send).
if ! ls packaging/bundled-debs/*.deb >/dev/null 2>&1; then
  echo "Fetching bundled dependency .debs..."
  bash packaging/fetch-bundled-debs.sh
fi
debian/rules clean
if command -v fakeroot >/dev/null 2>&1; then
  fakeroot debian/rules binary
else
  debian/rules binary
fi
ls -lah dist/*.deb
