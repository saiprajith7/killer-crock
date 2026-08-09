# Packaging notes

## Build the `.deb`

```bash
sudo apt install -y debhelper dh-python pybuild-plugin-pyproject \
  python3-all python3-setuptools dpkg-dev

./packaging/build-deb.sh
# → dist/vitaheal_1.0.0-1_all.deb
```

## What the package installs into the OS

| Path | Purpose |
|------|---------|
| `/usr/bin/vitaheal` | GUI launcher |
| `/usr/bin/vitaheal-daemon` | Background watcher |
| `/usr/libexec/vitaheal/vitaheal-helper` | Privileged heal helper (pkexec) |
| `/usr/share/applications/vitaheal.desktop` | App menu entry |
| `/etc/xdg/autostart/vitaheal-daemon.desktop` | Starts with graphical session |
| `/usr/lib/systemd/user/vitaheal-daemon.service` | systemd --user unit |
| `/usr/share/polkit-1/actions/org.vitaheal.policy` | Polkit policy |

After install, VitaHeal is a first-class OS component — not a browser app.
