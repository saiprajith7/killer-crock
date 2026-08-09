#!/usr/bin/env bash
# Download VitaHeal .deb to your current folder (Debian/Ubuntu).
set -euo pipefail

BRANCH="cursor/vitaheal-pc-monitor-02f6"
REPO="saiprajith7/killer-crock"
OUT_DIR="${1:-$HOME/Downloads}"
mkdir -p "$OUT_DIR"

DEB_URL="https://github.com/${REPO}/raw/${BRANCH}/releases/vitaheal_1.0.0-1_all.deb"
ZIP_URL="https://github.com/${REPO}/raw/${BRANCH}/releases/vitaheal-deb.zip"

echo "Downloading VitaHeal package into: $OUT_DIR"
cd "$OUT_DIR"

if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 -o vitaheal_1.0.0-1_all.deb "$DEB_URL"
  curl -fL --retry 3 -o vitaheal-deb.zip "$ZIP_URL"
elif command -v wget >/dev/null 2>&1; then
  wget -O vitaheal_1.0.0-1_all.deb "$DEB_URL"
  wget -O vitaheal-deb.zip "$ZIP_URL"
else
  echo "Need curl or wget installed." >&2
  exit 1
fi

echo
echo "Downloaded:"
ls -lah "$OUT_DIR/vitaheal_1.0.0-1_all.deb" "$OUT_DIR/vitaheal-deb.zip"
echo
echo "Install with:"
echo "  sudo apt install \"$OUT_DIR/vitaheal_1.0.0-1_all.deb\""
echo "  vitaheal"
