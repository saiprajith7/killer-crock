#!/usr/bin/env bash
# Build a self-contained boss-sentinel (BOSS Health) .deb without debhelper.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="1.3.3-1"
PKG="boss-sentinel_${VERSION}_all"
STAGE="$ROOT/build/deb-stage/$PKG"
DIST="$ROOT/dist"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
  "$STAGE/usr/lib/python3/dist-packages" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/libexec/boss-sentinel" \
  "$STAGE/usr/libexec/boss-health" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps" \
  "$STAGE/usr/share/icons/hicolor/64x64/apps" \
  "$STAGE/usr/share/polkit-1/actions" \
  "$STAGE/usr/lib/systemd/user" \
  "$STAGE/etc/xdg/autostart" \
  "$STAGE/etc/boss-health" \
  "$STAGE/usr/share/boss-health" \
  "$STAGE/usr/share/cinnamon/applets/boss-health@boss" \
  "$STAGE/usr/share/doc/boss-sentinel"

# Python packages
cp -a "$ROOT/src/vitaheal" "$STAGE/usr/lib/python3/dist-packages/"
cp -a "$ROOT/src/boss_health" "$STAGE/usr/lib/python3/dist-packages/"
find "$STAGE/usr/lib/python3/dist-packages" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# Reliable launcher (shows error dialog on failure)
install -m 0755 "$ROOT/scripts/boss-health-launch" "$STAGE/usr/bin/boss-health"

cat > "$STAGE/usr/bin/boss-health-tray" <<'EOF'
#!/usr/bin/python3
import sys
for p in ("/usr/lib/python3/dist-packages", "/usr/local/lib/python3/dist-packages"):
    if p not in sys.path:
        sys.path.insert(0, p)
from boss_health.__main__ import tray_main
sys.exit(tray_main())
EOF
cat > "$STAGE/usr/bin/boss-sentinel" <<'EOF'
#!/usr/bin/python3
import sys
for p in ("/usr/lib/python3/dist-packages", "/usr/local/lib/python3/dist-packages"):
    if p not in sys.path:
        sys.path.insert(0, p)
from vitaheal.__main__ import main
sys.exit(main())
EOF
chmod 0755 "$STAGE/usr/bin/boss-health" "$STAGE/usr/bin/boss-health-tray" "$STAGE/usr/bin/boss-sentinel"

# Assets
install -m 0755 "$ROOT/scripts/vitaheal-helper" "$STAGE/usr/libexec/boss-sentinel/boss-sentinel-helper"
install -m 0755 "$ROOT/scripts/boss-health-enable-panel" "$STAGE/usr/libexec/boss-health/boss-health-enable-panel"
install -m 0644 "$ROOT/data/desktop/boss-health.desktop" "$STAGE/usr/share/applications/boss-health.desktop"
install -m 0644 "$ROOT/data/desktop/vitaheal.desktop" "$STAGE/usr/share/applications/boss-sentinel.desktop"
install -m 0644 "$ROOT/data/desktop/boss-health-tray.desktop" "$STAGE/etc/xdg/autostart/boss-health-tray.desktop"
install -m 0644 "$ROOT/data/icons/boss-health.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/boss-health.svg"
install -m 0644 "$ROOT/data/icons/vitaheal.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/boss-sentinel.svg"
install -m 0644 "$ROOT/data/polkit/org.vitaheal.policy" "$STAGE/usr/share/polkit-1/actions/org.bosssentinel.policy"
install -m 0644 "$ROOT/data/systemd/vitaheal-daemon.service" "$STAGE/usr/lib/systemd/user/boss-sentinel-daemon.service"
install -m 0644 "$ROOT/data/desktop/vitaheal-daemon.desktop" "$STAGE/etc/xdg/autostart/boss-sentinel-daemon.desktop"
install -m 0644 "$ROOT/data/config/boss-health.conf" "$STAGE/etc/boss-health/boss-health.conf"
install -m 0644 "$ROOT/data/config/boss-health.conf" "$STAGE/usr/share/boss-health/boss-health.conf"
install -m 0644 "$ROOT/data/cinnamon/applets/boss-health@boss/applet.js" \
  "$STAGE/usr/share/cinnamon/applets/boss-health@boss/applet.js"
install -m 0644 "$ROOT/data/cinnamon/applets/boss-health@boss/metadata.json" \
  "$STAGE/usr/share/cinnamon/applets/boss-health@boss/metadata.json"
install -m 0644 "$ROOT/data/cinnamon/applets/boss-health@boss/icon.png" \
  "$STAGE/usr/share/cinnamon/applets/boss-health@boss/icon.png"
install -m 0644 "$ROOT/data/icons/boss-health.svg" \
  "$STAGE/usr/share/cinnamon/applets/boss-health@boss/icon.svg"
if [ -f "$ROOT/data/icons/boss-health.png" ]; then
  install -m 0644 "$ROOT/data/icons/boss-health.png" \
    "$STAGE/usr/share/icons/hicolor/64x64/apps/boss-health.png"
fi
install -m 0644 "$ROOT/README.md" "$STAGE/usr/share/doc/boss-sentinel/README.md"
install -m 0644 "$ROOT/TREE.md" "$STAGE/usr/share/doc/boss-sentinel/TREE.md"

SIZE_KB=$(du -sk "$STAGE" | awk '{print $1}')
cat > "$STAGE/DEBIAN/control" <<EOF
Package: boss-sentinel
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Maintainer: BOSS Health Packagers <packagers@boss-health.local>
Depends: python3, python3-gi, python3-gi-cairo, python3-cairo, gir1.2-gtk-3.0
Recommends: cinnamon, gir1.2-gtk-4.0, gir1.2-adw-1, policykit-1, libnotify-bin, systemd, apt
Provides: boss-health, vitaheal
Installed-Size: ${SIZE_KB}
Description: BOSS Health — System Readiness with integrated BOSS-Sentinel
 BOSS Health System Readiness dashboard. Menu-bar icon click opens the
 readiness dashboard. Reuses BOSS-Sentinel CPU/RAM collectors.
EOF

install -m 0755 "$ROOT/debian/postinst" "$STAGE/DEBIAN/postinst"
install -m 0755 "$ROOT/debian/prerm" "$STAGE/DEBIAN/prerm"

mkdir -p "$DIST"
dpkg-deb --build --root-owner-group "$STAGE" "$DIST/${PKG}.deb"
ls -lah "$DIST/${PKG}.deb"
echo "Install with: sudo dpkg -i $DIST/${PKG}.deb && sudo apt -f install"
