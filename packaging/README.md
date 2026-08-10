# Packaging notes

## Build the `.deb`

```bash
sudo apt install -y debhelper dh-python pybuild-plugin-pyproject \
  python3-all python3-setuptools dpkg-dev fakeroot

./packaging/build-deb.sh
# → dist/boss-sentinel_1.2.12-1_all.deb
```

## What the package installs into the OS

| Path | Purpose |
|------|---------|
| `/usr/bin/boss-sentinel` | GUI launcher |
| `/usr/bin/boss-sentinel-daemon` | Background watcher |
| `/usr/libexec/boss-sentinel/boss-sentinel-helper` | Privileged helper (pkexec) |
| `/usr/share/applications/boss-sentinel.desktop` | App menu entry |
| `/etc/xdg/autostart/boss-sentinel-daemon.desktop` | Starts with graphical session |
| `/usr/lib/systemd/user/boss-sentinel-daemon.service` | systemd --user unit |
| `/usr/share/polkit-1/actions/org.bosssentinel.policy` | Polkit policy |

After install, BOSS-Sentinel is a first-class OS component — not a browser app.
