#!/usr/bin/env bash
# Refresh packaging/bundled-debs/*.deb used inside the single boss-sentinel .deb.
# Run on an amd64 Ubuntu/Debian builder with network access.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bundled-debs
cd bundled-debs
rm -f ./*.deb
# Architecture: all + amd64 extras commonly missing on lean ISO images.
apt-get download fonts-hack libnotify-bin
ls -lah ./*.deb
