# BOSS-Sentinel
## Technical Product Documentation

| Field | Value |
|-------|-------|
| **Product name** | BOSS-Sentinel |
| **Version** | 1.2.2 |
| **Package name** | `boss-sentinel` |
| **License** | GPL-3.0-or-later |
| **Platform** | Debian / Debian-based Linux (amd64 and architecture-independent Python) |
| **UI stack** | Python 3 · GTK4 · libadwaita |
| **Distribution** | Native `.deb` package + optional Debian ISO integration |
| **Document type** | Complete engineering & operations manual |

---

# 1. Executive Summary

**BOSS-Sentinel** is a **native Linux desktop application** that monitors personal-computer health and offers **interactive autohealing**. It is intentionally **not** a web application, Electron shell, or cloud dashboard. It installs like any other Debian OS component: desktop menu entry, systemd user daemon, Polkit privileged helper, and application icon.

### Core value proposition
1. **Observe** — live vitals for CPU, memory, swap, disk, inodes, temperature, GPU, network, and processes.
2. **Decide** — when a fault is critical, the user is prompted with a clear **Yes / No** dialog.
3. **Heal** — only after **Yes**, privileged repair actions run through Polkit (`pkexec`).
4. **Update** — optional apt package checks and upgrades, also gated by Yes / No.
5. **Ship with the OS** — package as `.deb` and optionally bake into a custom Debian **ISO** so every installed system includes BOSS-Sentinel by default.

---

# 2. Product Overview

## 2.1 What the user sees
- Minimal **blue** light theme
- Brand-forward title: **BOSS-Sentinel**
- Tabbed layout: Overview · CPU · Memory · Disk · GPU · Thermal · Updates · Logs
- Live graphs and status line
- Explicit window close control
- AUTOHEAL ON / OFF toggle

## 2.2 What runs in the background
- `boss-sentinel-daemon` — watches health on an interval, can notify the user
- Enabled via **systemd --user** and **XDG autostart** after package install

## 2.3 Design principles
| Principle | Implementation |
|-----------|----------------|
| Native, not web | GTK4 + libadwaita |
| Safe autoheal | Never silent; always Yes / No |
| Lightweight | Short vitals poll; apt only on demand |
| OS-integrated | `.deb`, desktop, systemd, Polkit |
| Clean CLI | Quiet install script; launcher filters harmless EGL noise |

---

# 3. How It Works (Runtime Flow)

```
User session starts
        │
        ├─► (optional) boss-sentinel-daemon via systemd/autostart
        │         │
        │         └─► poll HealthEngine → notify if critical
        │
        └─► User launches boss-sentinel (GUI)
                  │
                  ▼
           VitaHealApp (Adw.Application)
                  │
                  ▼
           VitaHealWindow
                  │
                  ├─ every few seconds: HealthEngine.snapshot()
                  │         │
                  │         ├─ collectors read /proc, sysfs, sensors, GPU tools
                  │         └─ derive Issues (OK / WARN / CRITICAL)
                  │
                  ├─ if AUTOHEAL ON + CRITICAL issue
                  │         │
                  │         ▼
                  │   Yes/No dialog (heal_dialog)
                  │         │
                  │    Yes ─┴─ No (log skip)
                  │         │
                  │         ▼
                  │   perform_heal(action)
                  │         │
                  │         ▼
                  │   pkexec boss-sentinel-helper <action>
                  │         │
                  │         └─► JSON result → toast + Heal log
                  │
                  └─ Updates tab (on demand)
                            │
                            ├─ read apt sources
                            ├─ apt-get update / simulate upgrade
                            └─ Yes/No → apt-get upgrade via helper
```

### Security path for heals
1. GUI confirms user intent (Yes).
2. `pkexec` asks for admin authentication (Polkit policy `org.bosssentinel.helper`).
3. Helper runs as root for the single requested action only.
4. Helper prints one JSON object: `{ "ok", "message", "details" }`.

---

# 4. Complete File Structure

```
BOSS-Sentinel/
├── README.md
├── DOCUMENTATION.md
├── Makefile
├── pyproject.toml
├── setup.py
├── src/
│   └── vitaheal/                 # Internal Python package name
│       ├── __init__.py           # APP_NAME, APP_ID, version
│       ├── __main__.py           # CLI: GUI / --once / --daemon / --simulate-issue
│       ├── app.py                # Adw.Application bootstrap
│       ├── monitor/
│       │   ├── engine.py         # Aggregates collectors → snapshot + issues
│       │   ├── models.py         # MetricReading, Issue, Severity, HealthSnapshot
│       │   ├── cpu.py
│       │   ├── memory.py
│       │   ├── disk.py
│       │   ├── temperature.py
│       │   ├── gpu.py
│       │   ├── network.py
│       │   ├── process.py
│       │   └── updates.py        # apt sources + upgrade status
│       ├── heal/
│       │   └── actions.py        # Heal catalog + pkexec IPC
│       ├── daemon/
│       │   └── watcher.py        # Background watcher
│       └── ui/
│           ├── window.py         # Main window + tabs
│           ├── gauges.py         # Live graphs
│           ├── heal_dialog.py    # Yes/No dialogs + toasts
│           ├── eventlog.py       # In-app logs
│           └── style.css         # Blue minimal theme
├── scripts/
│   ├── boss-sentinel             # Quiet GUI launcher (filters EGL warnings)
│   ├── install-boss-sentinel.sh  # Quiet .deb install from /tmp
│   └── vitaheal-helper           # Privileged helper (→ boss-sentinel-helper)
├── data/
│   ├── desktop/
│   │   ├── vitaheal.desktop      # → boss-sentinel.desktop
│   │   └── vitaheal-daemon.desktop
│   ├── systemd/
│   │   └── vitaheal-daemon.service
│   ├── polkit/
│   │   └── org.vitaheal.policy   # → org.bosssentinel.policy
│   └── icons/
│       └── vitaheal.svg          # → boss-sentinel.svg
├── debian/                       # Debian packaging metadata
│   ├── control
│   ├── changelog
│   ├── rules
│   ├── postinst
│   ├── prerm
│   └── copyright
├── packaging/
│   ├── build-deb.sh
│   └── README.md
├── tests/
│   └── test_engine.py
├── releases/                     # Built artifacts (.deb, zip)
└── dist/                         # Local build output
```

### Installed filesystem layout (after `dpkg -i`)
| Path | Purpose |
|------|---------|
| `/usr/bin/boss-sentinel` | Quiet GUI launcher |
| `/usr/bin/boss-sentinel-daemon` | Background watcher |
| `/usr/bin/vitaheal` | Compatibility symlink → `boss-sentinel` |
| `/usr/libexec/boss-sentinel/boss-sentinel-helper` | Privileged heal helper |
| `/usr/lib/python3/dist-packages/vitaheal/` | Application code |
| `/usr/share/applications/boss-sentinel.desktop` | App menu |
| `/etc/xdg/autostart/boss-sentinel-daemon.desktop` | Autostart |
| `/usr/lib/systemd/user/boss-sentinel-daemon.service` | User service |
| `/usr/share/polkit-1/actions/org.bosssentinel.policy` | Polkit |
| `/usr/share/icons/hicolor/scalable/apps/boss-sentinel.svg` | Icon |

---

# 5. Code Reference (Key Modules)

## 5.1 Application identity (`src/vitaheal/__init__.py`)
```python
"""BOSS-Sentinel — native Debian PC health monitor with interactive autohealing."""

__version__ = "1.2.2"
APP_ID = "org.bosssentinel.BossSentinel"
APP_NAME = "BOSS-Sentinel"
BRAND = "BOSS-SENTINEL"
```

## 5.2 GUI bootstrap (`src/vitaheal/app.py`)
```python
class VitaHealApp(Adw.Application):
    def __init__(self, simulate: Optional[str] = None) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._simulate = simulate
        self.connect("activate", self._on_activate)

    def _on_activate(self, app: Adw.Application) -> None:
        win = self.props.active_window
        if not win:
            win = VitaHealWindow(app, simulate=self._simulate)
        win.present()


def run_gui(simulate: Optional[str] = None) -> int:
    app = VitaHealApp(simulate=simulate)
    # Do not forward CLI flags to Gio/GTK.
    return app.run([sys.argv[0]])
```

## 5.3 Health engine (concept)
`HealthEngine.snapshot()`:
1. Calls each collector (`CpuCollector`, `MemoryCollector`, …).
2. Optionally injects a simulated critical metric (`--simulate-issue`).
3. Derives `Issue` objects for WARN/CRITICAL readings.
4. Computes overall severity and a 0–100 health score.

## 5.4 Issue → heal mapping
| Metric / issue | Heal action ID | User-facing label |
|----------------|----------------|-------------------|
| CPU overload | `renice_hogs` | Throttle CPU hogs |
| Memory pressure | `drop_caches` | Drop page caches |
| Swap thrashing | `reset_swap` | Reset swap |
| Disk nearly full | `purge_disk` | Purge caches & temp |
| Inode exhaustion | `prune_tmp` | Prune temp inodes |
| Thermal emergency | `thermal_cooldown` | Force powersave cooling |
| GPU util / VRAM / GPU temp | `gpu_cooldown` | Force GPU powersave |
| Zombie swarm | `reap_zombies` | Reap zombie parents |
| Load spike | `pause_timers` | Pause user timers |
| Apt upgrade (Updates tab) | `apt_update` / `apt_upgrade` | Install updates |

## 5.5 Privileged helper IPC
GUI / heal layer:
```python
cmd = ["pkexec", "/usr/libexec/boss-sentinel/boss-sentinel-helper", action, *args]
```
Helper returns:
```json
{"ok": true, "message": "Page caches dropped", "details": ""}
```

## 5.6 Desktop entry
```ini
[Desktop Entry]
Name=BOSS-Sentinel
GenericName=PC Health Monitor
Comment=Minimal PC health monitoring with interactive autohealing
Exec=boss-sentinel
Icon=boss-sentinel
Terminal=false
Type=Application
Categories=System;Monitor;Utility;
```

## 5.7 systemd user unit
```ini
[Unit]
Description=BOSS-Sentinel background health watcher
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/boss-sentinel-daemon --interval 20
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

## 5.8 CLI surface
```bash
boss-sentinel                         # GUI
boss-sentinel --once                  # JSON snapshot
boss-sentinel --daemon                # watcher mode
boss-sentinel --simulate-issue memory # demo critical UI
boss-sentinel-daemon                  # packaged daemon entry
```

Simulate choices: `cpu`, `memory`, `disk`, `temp`, `zombie`, `swap`, `gpu`.

---

# 6. User Interface Specification

## 6.1 Tabs
| Tab | Contents |
|-----|----------|
| **Overview** | Device graphs + active issues |
| **CPU** | Cores, threads, model, per-core bars |
| **Memory** | RAM + Swap |
| **Disk** | Volumes + graph |
| **GPU** | Util / VRAM / temp / power |
| **Thermal** | All sensors + graph |
| **Updates** | apt sources, check, Yes/No upgrade |
| **Logs** | Trouble · Heal · Update Log |

## 6.2 Interaction rules
- Heal and upgrade actions **always** ask Yes / No first.
- AUTOHEAL OFF disables automatic prompts (manual awareness only).
- Apt work is **on demand** (not every poll tick) to keep the UI light.

---

# 7. Build Instructions

## 7.1 Developer dependencies
```bash
sudo apt install -y \
  python3-gi python3-gi-cairo python3-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 \
  policykit-1 libnotify-bin \
  fonts-jetbrains-mono \
  debhelper dh-python pybuild-plugin-pyproject \
  python3-all python3-setuptools dpkg-dev fakeroot
```

## 7.2 Run from source
```bash
cd BOSS-Sentinel-1.2.2   # or git clone / checkout
PYTHONPATH=src python3 -m vitaheal
# demo a critical memory issue:
PYTHONPATH=src python3 -m vitaheal --simulate-issue memory
```

## 7.3 Test
```bash
make test
# equivalent:
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## 7.4 Build the `.deb`
```bash
make deb
# or:
bash packaging/build-deb.sh
# output:
#   dist/boss-sentinel_1.2.2-1_all.deb
```

## 7.5 Quiet end-user install
```bash
cd install
bash install.sh
boss-sentinel
```
`install.sh` copies the `.deb` to `/tmp` (mode `644`) and installs with `dpkg`, avoiding apt’s home-directory `_apt` / “unsandboxed as root” notice.

---

# 8. Integration Guide

## 8.1 Integrate on an existing Debian PC
1. Obtain `boss-sentinel_1.2.2-1_all.deb` (from `releases/` or zip).
2. Run `bash install.sh` **or** `sudo dpkg -i boss-sentinel_*.deb`.
3. If dependencies are missing: `sudo apt -f install`.
4. Launch from menu or `boss-sentinel`.
5. Confirm daemon:
   ```bash
   systemctl --user status boss-sentinel-daemon.service
   ```

## 8.2 Integrate into your product / fleet image
1. Host the `.deb` in an internal apt repository **or** copy into the image build tree.
2. Add package name `boss-sentinel` to the image package list.
3. Ensure Depends are present: GTK4, Adwaita, Polkit, notify-bin, monospace font.
4. Optional: enable user service by default (already handled by package postinst / systemd user enable snippets).

## 8.3 API / automation hooks
| Mode | Use |
|------|-----|
| `boss-sentinel --once` | Scripted health JSON for monitoring pipelines |
| Daemon notifications | User-session awareness without opening GUI |
| Polkit helper | Do **not** call helper directly from untrusted scripts without policy review |

Example:
```bash
boss-sentinel --once | jq '.overall, .score'
```

## 8.4 Compatibility aliases
Package **Provides / Replaces / Conflicts** `vitaheal`. Commands `vitaheal` and `vitaheal-daemon` remain as aliases.

---

# 9. Building a Debian ISO That Includes BOSS-Sentinel

Goal: produce a bootable **Debian ISO** where BOSS-Sentinel is preinstalled (comes with the OS).

## 9.1 Recommended tool: `live-build` (Debian Live)
High-level steps:

### A. Prepare build host
```bash
sudo apt install -y live-build debootstrap squashfs-tools xorriso
mkdir -p ~/iso-boss && cd ~/iso-boss
lb config \
  --distribution bookworm \
  --archive-areas "main contrib non-free non-free-firmware" \
  --debian-installer live \
  --binary-images iso-hybrid
```

### B. Add BOSS-Sentinel as a local package
```bash
mkdir -p config/packages.chroot
cp /path/to/boss-sentinel_1.2.2-1_all.deb config/packages.chroot/
```
`live-build` installs packages placed in `config/packages.chroot/` into the live system.

### C. Ensure runtime dependencies are in the package lists
Create or edit `config/package-lists/boss-sentinel.list.chroot`:
```
python3-gi
python3-gi-cairo
python3-cairo
gir1.2-gtk-4.0
gir1.2-adw-1
policykit-1
libnotify-bin
fonts-jetbrains-mono
lm-sensors
boss-sentinel
```
(If using only the local `.deb` in `packages.chroot`, listing `boss-sentinel` is optional; dependencies above should still be listed.)

### D. Optional: hook to enable daemon defaults
`config/hooks/live/90-boss-sentinel.chroot`:
```bash
#!/bin/sh
set -e
# Desktop file + polkit ship with the package.
# User systemd enable happens per-user at first login / postinst when applicable.
gtk-update-icon-cache -f /usr/share/icons/hicolor || true
update-desktop-database /usr/share/applications || true
```
```bash
chmod +x config/hooks/live/90-boss-sentinel.chroot
```

### E. Build the ISO
```bash
sudo lb build
ls -lah *.hybrid.iso 2>/dev/null || ls -lah live-image-*.hybrid.iso
```

### F. Test
```bash
# Example with QEMU
qemu-system-x86_64 -m 2048 -cdrom *.hybrid.iso -boot d
```
After boot into the live desktop, run `boss-sentinel` or find **BOSS-Sentinel** in the app menu.

## 9.2 Alternative: Debian Installer preseed (installed system, not only live)
1. Build or obtain a Debian netinst/DVD ISO.
2. Remaster or serve a preseed file that includes:
   ```
   d-i pkgsel/include string boss-sentinel
   ```
3. Provide an apt source that hosts your `.deb` (local mirror or `file://` during late_command).
4. Example late command pattern:
   ```
   d-i preseed/late_command string \
     in-target apt-get install -y boss-sentinel || true
   ```

## 9.3 How the ISO “works” with BOSS-Sentinel end-to-end
1. User boots the custom ISO (live or installer).
2. Resulting system already contains `/usr/bin/boss-sentinel` and supporting files.
3. On graphical login, autostart / systemd user unit can start the daemon.
4. User opens BOSS-Sentinel → monitors vitals → Yes/No heals → optional Updates tab.
5. No extra download step is required on first boot if the `.deb` was baked into the image.

## 9.4 Deliverable naming (suggested)
| Artifact | Example name |
|----------|--------------|
| Application package | `boss-sentinel_1.2.2-1_all.deb` |
| Source/distribution zip | `BOSS-Sentinel-1.2.2.zip` |
| Custom OS image | `BOSS-Sentinel-Debian-Bookworm-amd64.iso` |

---

# 10. Operations & Troubleshooting

| Symptom | Fix |
|---------|-----|
| Half-installed package / apt “No file name” | `sudo dpkg --remove --force-remove-reinstreq boss-sentinel` then reinstall 1.2.2+ |
| apt `_apt` unsandboxed notice | Use `bash install.sh` (install from `/tmp`) |
| `libEGL warning: DRI2: failed to authenticate` | Harmless; filtered by 1.2.2 launcher |
| No temperature readings | Install/configure `lm-sensors` (`sudo sensors-detect`) |
| Heal fails auth | Approve Polkit prompt; ensure `policykit-1` installed |
| GPU metrics empty | Install vendor tools when available (`nvidia-smi`, etc.); app still runs |
| Bookworm Adw titlebar crash (historical) | Current builds avoid unsupported `set_titlebar` on AdwWindow |

---

# 11. Version History

| Version | Notes |
|---------|-------|
| **1.2.2** | Quiet install script; EGL warning filter in launcher |
| **1.2.1** | Fixed invalid class name that broke `dpkg` postinst |
| **1.2.0** | Updates tab + Update Log; on-demand apt |
| **1.1.0** | Rebrand to BOSS-Sentinel; tabbed blue UI |
| **1.0.0** | Initial native monitor + interactive autoheal |

---

# 12. License & Compliance

- License: **GPL-3.0-or-later**
- Debian `copyright` file ships inside the package under `/usr/share/doc/boss-sentinel/`
- When redistributing a custom ISO, retain GPL notices and source offer obligations for GPL components

---

# 13. Quick Reference Card

```bash
# Build
make test && make deb

# Install
cd install && bash install.sh

# Run
boss-sentinel
boss-sentinel --once
boss-sentinel --simulate-issue gpu

# Daemon
systemctl --user status boss-sentinel-daemon.service

# ISO (live-build sketch)
cp boss-sentinel_*.deb config/packages.chroot/
sudo lb build
```

---

*End of document — BOSS-Sentinel 1.2.2 Technical Product Documentation*
