# BOSS-Sentinel

Lightweight native Debian PC health monitor with interactive autohealing.

GTK4 desktop app (not web). Minimal blue UI. Tabbed: Overview · CPU · Memory · Disk · GPU · Thermal · Updates · Logs.

## Install (recommended)

```bash
cd install
bash install.sh
boss-sentinel
```

The install script copies the `.deb` to `/tmp` and uses `dpkg`, so you
do not get apt's `_apt` permission / "unsandboxed as root" notice from
installing out of your home folder.

Manual install (may print that apt notice if the `.deb` is under `$HOME`):

```bash
sudo dpkg -i ./install/boss-sentinel_1.2.5-1_all.deb
boss-sentinel
```

If dependencies are missing:

```bash
sudo apt -f install
sudo dpkg -i ./install/boss-sentinel_1.2.5-1_all.deb
boss-sentinel
```

## Run from source (dev)

```bash
sudo apt install -y python3-gi python3-gi-cairo python3-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 policykit-1 libnotify-bin fonts-jetbrains-mono

PYTHONPATH=src python3 -m vitaheal
# or after make install:
boss-sentinel
```

## Build the .deb yourself

```bash
sudo apt install -y debhelper dh-python pybuild-plugin-pyproject \
  python3-all python3-setuptools dpkg-dev fakeroot
make deb
# output: dist/boss-sentinel_1.2.6-1_all.deb
```

## Tests

```bash
# Full application test suite (recommended)
bash scripts/test-boss-sentinel.sh

# Faster (skip .deb inspection)
bash scripts/test-boss-sentinel.sh --quick

# Also probe an installed system package
bash scripts/test-boss-sentinel.sh --installed

# Or via Make
make test-script
make test              # unittest only
```

## Tabs

| Tab | Contents |
|-----|----------|
| Overview | Device graphs + active issues |
| CPU | Cores, threads, per-CPU history + bars |
| Memory | RAM + Swap |
| Disk | Volumes + graph |
| GPU | Util / VRAM / temp / power |
| Thermal | All sensors |
| Hardware | All components + USB health; replace if &lt; 45% |
| Updates | apt sources.list check + Yes/No upgrade |
| Logs | Trouble · Heal · Update Log |

Heal and upgrade actions always ask **Yes / No** first.

## License

GPL-3.0-or-later
