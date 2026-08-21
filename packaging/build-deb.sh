#!/usr/bin/env bash
# Build the vitaheal .deb into ./dist without writing to the parent directory.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
debian/rules clean
if command -v fakeroot >/dev/null 2>&1; then
  fakeroot debian/rules binary
else
  debian/rules binary
fi
ls -lah dist/*.deb
