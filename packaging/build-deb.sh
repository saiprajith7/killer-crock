#!/usr/bin/env bash
# Build the vitaheal .deb into ./dist without writing to the parent directory.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
debian/rules clean
debian/rules binary
ls -lah dist/*.deb
