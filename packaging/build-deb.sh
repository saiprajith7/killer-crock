#!/usr/bin/env bash
# Build Release binary and produce releases/boss-sentinel_<ver>-1_<arch>.deb
# Prefer building on Debian 12 / BOSS (glibc 2.36) so the binary runs there.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(grep -E '^project\(' CMakeLists.txt | sed -n 's/.*VERSION \([0-9.]*\).*/\1/p' | head -1)"
VERSION="${VERSION:-2.0.2}"
ARCH="$(dpkg --print-architecture)"
PKG="boss-sentinel_${VERSION}-1_${ARCH}"
# Bundle gtkmm only when explicitly requested (not for Debian 12 / BOSS targets)
BUNDLE_LIBS="${BOSS_BUNDLE_LIBS:-0}"

chmod +x scripts/boss-sentinel scripts/boss-sentinel-helper scripts/install-boss-sentinel.sh scripts/install-unified.sh scripts/purge-boss-sentinel.sh scripts/boss-sentinel-gtk3.py debian/rules || true

echo "==> Host glibc: $(ldd --version | head -1)"
echo "==> Configuring CMake"
rm -rf build
export CXX="${CXX:-g++}"
if ! echo 'int main(){return 0;}' | "$CXX" -x c++ - -lstdc++ -o /tmp/boss-cxx-test 2>/dev/null; then
  if command -v g++-12 >/dev/null 2>&1; then export CXX=g++-12; fi
  if command -v g++-13 >/dev/null 2>&1; then export CXX=g++-13; fi
fi
rm -f /tmp/boss-cxx-test
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr

echo "==> Building"
cmake --build build -j"$(nproc)"

# Sanity: refuse Ubuntu-noble binaries that need GLIBC_2.38 when targeting BOSS
if command -v objdump >/dev/null; then
  if objdump -T build/boss-sentinel-bin 2>/dev/null | grep -q 'GLIBC_2\.3[89]\|GLIBC_2\.[4-9]'; then
    echo "ERROR: binary requires glibc >= 2.38; rebuild on Debian 12 / BOSS." >&2
    echo "Hint: sudo chroot /opt/bookworm-root bash -lc 'cd /workspace && ./packaging/build-deb.sh'" >&2
    exit 1
  fi
fi

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
install -m 0755 scripts/boss-sentinel-gtk3.py "$STAGE/usr/lib/boss-sentinel/boss-sentinel-gtk3.py"
install -m 0644 scripts/gauges_gtk3.py "$STAGE/usr/lib/boss-sentinel/gauges_gtk3.py"
install -m 0644 scripts/style-gtk3.css "$STAGE/usr/share/boss-sentinel/style-gtk3.css"
install -m 0755 scripts/install-unified.sh "$STAGE/usr/share/boss-sentinel/install-unified.sh"
install -m 0755 scripts/install-boss-sentinel.sh "$STAGE/usr/share/boss-sentinel/install-boss-sentinel.sh"
install -m 0755 scripts/purge-boss-sentinel.sh "$STAGE/usr/share/boss-sentinel/purge-boss-sentinel.sh"
install -m 0644 src/ui/style.css "$STAGE/usr/share/boss-sentinel/style.css"
install -m 0644 data/desktop/org.bosssentinel.BossSentinel.desktop "$STAGE/usr/share/applications/"
install -m 0644 data/icons/org.bosssentinel.BossSentinel.svg "$STAGE/usr/share/icons/hicolor/scalable/apps/"
install -m 0644 data/polkit/org.bosssentinel.policy "$STAGE/usr/share/polkit-1/actions/"
install -m 0644 docs/BUILD.md docs/SYSTEM_DESIGN.md docs/FILE_STRUCTURE.md \
  docs/CODE_WALKTHROUGH.md docs/USER_GUIDE.md docs/DOCUMENTATION_INDEX.md \
  docs/BOSS-Sentinel-Complete-Guide.docx \
  docs/BOSS-Sentinel-Source-Code-and-Explanation.docx \
  README.md "$STAGE/usr/share/doc/boss-sentinel/" 2>/dev/null || true

if [[ "$BUNDLE_LIBS" == "1" ]]; then
  echo "==> Bundling gtkmm runtime libraries (BOSS_BUNDLE_LIBS=1)"
  bundle_one() {
    local name="$1"
    local src
    src="$(ldconfig -p | awk -v n="$name" '$1==n {print $NF; exit}')"
    [[ -n "$src" && -e "$src" ]] || return 0
    local real
    real="$(readlink -f "$src")"
    install -m 0644 "$real" "$STAGE/usr/lib/boss-sentinel/$(basename "$real")"
    ln -sfn "$(basename "$real")" "$STAGE/usr/lib/boss-sentinel/$name"
  }
  for lib in libgtkmm-4.0.so.0 libgiomm-2.68.so.1 libglibmm-2.68.so.1 \
             libsigc-3.0.so.0 libcairomm-1.16.so.1 libpangomm-2.48.so.1; do
    bundle_one "$lib"
  done
fi

SIZE_KB="$(du -sk "$STAGE/usr" | awk '{print $1}')"

# Debian 12 / BOSS package names (no t64 suffix)
cat > "$STAGE/DEBIAN/control" <<EOF
Package: boss-sentinel
Version: ${VERSION}-1
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: BOSS-Sentinel Packagers <packagers@boss-sentinel.local>
Depends: python3, python3-gi, python3-cairo, gir1.2-gtk-3.0, libgtk-3-0
Recommends: pkexec | policykit-1, power-profiles-daemon, fonts-hack | fonts-jetbrains-mono, libgtkmm-4.0-0, libglibmm-2.68-1, libgtk-4-1, libsigc++-3.0-0, libcairomm-1.16-1, libpangomm-2.48-1
Conflicts: boss-optimize, bossoptimize
Replaces: boss-optimize, bossoptimize
Provides: boss-optimize
Installed-Size: ${SIZE_KB}
Homepage: https://github.com/saiprajith7/killer-crock
Description: BOSS-Sentinel — unified auto-heal and performance optimizer
 GTK3 UI (default) plus optional C++ GTK4 binary for Debian 12 / BOSS Linux.
 Detects pressure, prompts for auto-heal, optimizes performance, and logs actions.
EOF

install -m 0755 debian/postinst "$STAGE/DEBIAN/postinst"
install -m 0755 debian/prerm "$STAGE/DEBIAN/prerm"

mkdir -p "$ROOT/releases" "$ROOT/dist"
OUT="$ROOT/releases/${PKG}.deb"
LATEST="$ROOT/releases/boss-sentinel_latest_amd64.deb"
echo "==> Building deb: $OUT"
if command -v fakeroot >/dev/null 2>&1; then
  fakeroot dpkg-deb --build "$STAGE" "$OUT"
else
  dpkg-deb --build "$STAGE" "$OUT"
fi
cp -f "$OUT" "$ROOT/dist/"
cp -f "$OUT" "$LATEST"
ls -lah "$OUT"
dpkg-deb -I "$OUT" | head -40
# Print max required glibc symbol if available
if command -v objdump >/dev/null; then
  echo "==> GLIBC symbols used (highest):"
  objdump -T "$STAGE/usr/lib/boss-sentinel/boss-sentinel-bin" 2>/dev/null \
    | grep -oE 'GLIBC_[0-9.]+' | sort -Vu | tail -5 || true
fi
echo "OK: $OUT"
