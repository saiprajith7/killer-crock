#!/usr/bin/env bash
# Build Release binary and produce releases/boss-sentinel_<ver>-1_<arch>.deb
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(grep -E '^project\(' CMakeLists.txt | sed -n 's/.*VERSION \([0-9.]*\).*/\1/p' | head -1)"
VERSION="${VERSION:-2.0.0}"
ARCH="$(dpkg --print-architecture)"
PKG="boss-sentinel_${VERSION}-1_${ARCH}"

chmod +x scripts/boss-sentinel scripts/boss-sentinel-helper debian/rules || true

echo "==> Configuring CMake"
rm -rf build
# Prefer g++ when /usr/bin/c++ is clang without a working libstdc++ link
export CXX="${CXX:-g++}"
if ! echo 'int main(){return 0;}' | "$CXX" -x c++ - -lstdc++ -o /tmp/boss-cxx-test 2>/dev/null; then
  if command -v g++-13 >/dev/null 2>&1; then export CXX=g++-13; fi
fi
rm -f /tmp/boss-cxx-test
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr

echo "==> Building"
cmake --build build -j"$(nproc)"

echo "==> Staging package tree"
STAGE="$ROOT/build/stage/$PKG"
rm -rf "$ROOT/build/stage"
mkdir -p "$STAGE/DEBIAN" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/lib/boss-sentinel" \
         "$STAGE/usr/libexec/boss-sentinel" \
         "$STAGE/usr/share/boss-sentinel" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/scalable/apps" \
         "$STAGE/usr/share/polkit-1/actions" \
         "$STAGE/usr/share/doc/boss-sentinel"

install -m 0755 build/boss-sentinel-bin "$STAGE/usr/lib/boss-sentinel/boss-sentinel-bin"
install -m 0755 scripts/boss-sentinel "$STAGE/usr/bin/boss-sentinel"
install -m 0755 scripts/boss-sentinel-helper "$STAGE/usr/libexec/boss-sentinel/boss-sentinel-helper"
install -m 0644 src/ui/style.css "$STAGE/usr/share/boss-sentinel/style.css"
install -m 0644 data/desktop/org.bosssentinel.BossSentinel.desktop "$STAGE/usr/share/applications/"
install -m 0644 data/icons/org.bosssentinel.BossSentinel.svg "$STAGE/usr/share/icons/hicolor/scalable/apps/"
install -m 0644 data/polkit/org.bosssentinel.policy "$STAGE/usr/share/polkit-1/actions/"
install -m 0644 docs/BUILD.md docs/SYSTEM_DESIGN.md README.md "$STAGE/usr/share/doc/boss-sentinel/" 2>/dev/null || true

# Runtime deps sizing
SIZE_KB="$(du -sk "$STAGE/usr" | awk '{print $1}')"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: boss-sentinel
Version: ${VERSION}-1
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: BOSS-Sentinel Packagers <packagers@boss-sentinel.local>
Depends: libgtkmm-4.0-0, libglibmm-2.68-1t64 | libglibmm-2.68-1, libgtk-4-1, python3
Recommends: pkexec | policykit-1, power-profiles-daemon, fonts-hack | fonts-jetbrains-mono
Installed-Size: ${SIZE_KB}
Homepage: https://github.com/saiprajith7/killer-crock
Description: BOSS-Sentinel — unified auto-heal and performance optimizer
 C++ GTK4 monitor that detects pressure, prompts for auto-heal,
 optimizes performance, and logs every action.
EOF

install -m 0755 debian/postinst "$STAGE/DEBIAN/postinst"
install -m 0755 debian/prerm "$STAGE/DEBIAN/prerm"

mkdir -p "$ROOT/releases" "$ROOT/dist"
OUT="$ROOT/releases/${PKG}.deb"
echo "==> Building deb: $OUT"
if command -v fakeroot >/dev/null 2>&1; then
  fakeroot dpkg-deb --build "$STAGE" "$OUT"
else
  dpkg-deb --build "$STAGE" "$OUT"
fi
cp -f "$OUT" "$ROOT/dist/"
ls -lah "$OUT"
dpkg-deb -I "$OUT" | head -40
echo "OK: $OUT"
