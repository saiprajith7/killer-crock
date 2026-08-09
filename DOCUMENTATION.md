# BOSS-Sentinel — Application Documentation

**Version:** 1.2.2  
**Package:** `boss-sentinel`  
**License:** GPL-3.0-or-later  
**Platform:** Debian / Debian-based Linux (native desktop, not a web app)

---

## 1. What it is

**BOSS-Sentinel** is a Debian-native PC health monitor with interactive autohealing.

- Built with **Python 3**, **GTK4**, and **libadwaita**
- Installs as a first-class OS package (`.deb`) with desktop entry, systemd user daemon, and Polkit helper
- Watches CPU, memory, swap, disk, inodes, temperature, GPU, network, and processes
- When something is **critical**, it can propose a repair — but **always asks Yes / No first**
- Minimal blue light UI with live graphs and tabbed detail views

Internal Python package name remains `vitaheal` for compatibility; the product name and launchers are **BOSS-Sentinel**.

---

## 2. Features

### Monitoring
| Area | What is collected |
|------|-------------------|
| CPU | Utilization, model, cores/threads, per-core usage, load |
| Memory | RAM used / available |
| Swap | Swap usage |
| Disk | Filesystem fill % and details |
| Inodes | Inode pressure on volumes |
| Temperature | Thermal sensors (lm-sensors recommended) |
| GPU | NVIDIA / AMD / Intel util, VRAM, temp, power (best-effort) |
| Network | Interface / traffic-oriented readings |
| Processes | Zombie process count and related health |

### Autoheal (interactive)
Autoheal can be toggled **ON / OFF** in the UI. When ON and a critical issue appears, BOSS-Sentinel shows a **Yes / No** dialog. Only on **Yes** does it run the matching heal action (via Polkit / `pkexec` when privileges are needed).

| Issue | Heal action |
|-------|-------------|
| CPU overload | Renice heavy non-critical processes |
| Memory pressure | Drop page caches (`drop_caches`) |
| Swap thrashing | Reset swap (`swapoff` / `swapon`) |
| Disk nearly full | Purge package caches, journal leftovers, temp files |
| Inode exhaustion | Prune `/tmp` and `/var/tmp` |
| Thermal emergency | Force CPU powersave governor |
| GPU util / VRAM / GPU temp | Force GPU powersave profile |
| Zombie swarm | Signal parents to reap zombies |
| Load spike | Pause non-essential user timers briefly |

### Updates
The **Updates** tab:

1. Reads apt sources (`/etc/apt/sources.list` and `sources.list.d`)
2. Checks for available upgrades on demand (not on every UI tick)
3. Asks **Yes / No** before running `apt-get upgrade`
4. Logs results under **Logs → Update Log**

### Logs
Three log views:

- **Trouble** — detected issues
- **Heal** — heal attempts and outcomes
- **Update Log** — apt check / upgrade activity

---

## 3. User interface

Minimal blue theme. First-class brand: **BOSS-Sentinel**.

### Tabs
| Tab | Purpose |
|-----|---------|
| Overview | Live device graphs + active issues |
| CPU | Topology, model, per-core bars |
| Memory | RAM + Swap graphs / details |
| Disk | Volumes + usage graph |
| GPU | Util / VRAM / temp / power |
| Thermal | Sensor list + temperature graph |
| Updates | Sources, package check, Yes/No upgrade |
| Logs | Trouble · Heal · Update Log |

### Controls
- **AUTOHEAL ON / OFF** — enable or disable automatic Yes/No heal prompts
- Explicit window **close (×)** control
- Status line reflects health (OK / warning / critical awaiting decision)

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────┐
│  boss-sentinel (GUI)                                    │
│  GTK4 + libadwaita  ·  vitaheal.ui.window               │
│         │                                               │
│         ▼                                               │
│  HealthEngine  ← collectors (cpu/mem/disk/gpu/…)        │
│         │                                               │
│         ├─► Heal dialog (Yes/No)                        │
│         │        │                                      │
│         │        ▼                                      │
│         │   pkexec → boss-sentinel-helper (Polkit)      │
│         │                                               │
│         └─► Updates (apt sources + upgrade, on demand)  │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  boss-sentinel-daemon                                   │
│  Background watcher · desktop notify · optional GUI hint│
│  systemd --user + XDG autostart                         │
└─────────────────────────────────────────────────────────┘
```

### Source layout
```
src/vitaheal/
  __main__.py          CLI entry (GUI / daemon / once)
  app.py               Adw.Application bootstrap
  monitor/             Collectors + HealthEngine
  heal/actions.py      Heal catalog + helper IPC
  daemon/watcher.py    Background watcher
  ui/                  Window, gauges, dialogs, CSS
scripts/
  boss-sentinel        Quiet GUI launcher (filters EGL noise)
  install-boss-sentinel.sh
  vitaheal-helper      Privileged heal helper (installed as boss-sentinel-helper)
data/                  Desktop, systemd, polkit, icon
debian/                Packaging
releases/              Built .deb and distribution zip
tests/                 Unit tests (engine / heal, no GUI)
```

---

## 5. Commands

### Launch
```bash
boss-sentinel                 # GUI
boss-sentinel-daemon          # background watcher
boss-sentinel --once          # one JSON health snapshot to stdout
boss-sentinel --simulate-issue memory   # demo critical issue in UI
```

Simulate choices: `cpu`, `memory`, `disk`, `temp`, `zombie`, `swap`, `gpu`

Legacy aliases still exist: `vitaheal`, `vitaheal-daemon`.

### Install (recommended)
```bash
cd install
bash install.sh
boss-sentinel
```

`install.sh` copies the `.deb` to `/tmp` and uses `dpkg`, avoiding apt’s home-directory `_apt` permission notice.

### Manual install
```bash
sudo dpkg -i ./install/boss-sentinel_1.2.2-1_all.deb
# if dependencies are missing:
sudo apt -f install
boss-sentinel
```

### Clear a broken / half-installed package
```bash
sudo dpkg --remove --force-remove-reinstreq boss-sentinel
```

### Run from source (development)
```bash
sudo apt install -y python3-gi python3-gi-cairo python3-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 policykit-1 libnotify-bin \
  fonts-jetbrains-mono

PYTHONPATH=src python3 -m vitaheal
make test
make deb    # → dist/boss-sentinel_1.2.2-1_all.deb
```

---

## 6. What the `.deb` installs

| Path | Role |
|------|------|
| `/usr/bin/boss-sentinel` | Quiet GUI launcher |
| `/usr/bin/boss-sentinel-daemon` | Background watcher |
| `/usr/libexec/boss-sentinel/boss-sentinel-helper` | Privileged heal helper |
| `/usr/share/applications/boss-sentinel.desktop` | App menu entry |
| `/etc/xdg/autostart/boss-sentinel-daemon.desktop` | Autostart with graphical session |
| `/usr/lib/systemd/user/boss-sentinel-daemon.service` | systemd user unit |
| `/usr/share/polkit-1/actions/org.bosssentinel.policy` | Polkit policy |
| `/usr/share/icons/hicolor/scalable/apps/boss-sentinel.svg` | App icon |
| `/usr/lib/python3/dist-packages/vitaheal/` | Application code |

### Runtime dependencies
- `python3-gi`, `python3-gi-cairo`, `python3-cairo`
- `gir1.2-gtk-4.0`, `gir1.2-adw-1`
- `policykit-1`, `libnotify-bin`
- monospace font: JetBrains Mono / Fira Code / Hack

**Recommends:** `lm-sensors`, `systemd`, `apt`

---

## 7. Security model

1. Normal monitoring runs as the logged-in user.
2. Destructive / privileged heals go through **Polkit** (`pkexec` + `boss-sentinel-helper`).
3. The UI **must** get an explicit **Yes** before heal or apt upgrade.
4. Polkit message: authentication required for system heal actions (`org.bosssentinel.helper`).

---

## 8. Design notes (product intent)

- **Native desktop**, not a browser or Electron app
- **Lightweight:** vitals poll on a short interval; apt work only on demand; slower graph ticks
- **Minimal UI:** blue theme, no dashboard clutter; brand-forward BOSS-Sentinel chrome
- **Safe autoheal:** never silent; always Yes/No
- **OS-integrated:** `.deb`, desktop file, autostart daemon, Polkit, systemd user unit

---

## 9. Version history

| Version | Highlights |
|---------|------------|
| **1.2.2** | Quiet install script; launcher filters harmless `libEGL` DRI warnings |
| **1.2.1** | Fix install SyntaxError (`VitaHealWindow` class name) |
| **1.2.0** | Updates tab + Update Log; on-demand apt |
| **1.1.0** | Rebrand to BOSS-Sentinel; tabbed blue UI |
| **1.0.0** | Initial native monitor + interactive autoheal |

---

## 10. Distribution artifacts

| File | Purpose |
|------|---------|
| `releases/boss-sentinel_1.2.2-1_all.deb` | Installable package |
| `releases/BOSS-Sentinel-1.2.2.zip` | Source + `install/` deb + `install.sh` |
| `releases/boss-sentinel-deb.zip` | Compact deb-only zip |

Raw download example (branch with the release):

```text
https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/fix-invalid-class-name-02f6/releases/BOSS-Sentinel-1.2.2.zip
```

---

## 11. Quick start checklist

1. Install with `bash install.sh` (or `dpkg -i` the `.deb`)
2. Launch `boss-sentinel`
3. Leave **AUTOHEAL ON** if you want Yes/No repair prompts
4. Use **Updates** when you want apt check / upgrade (also Yes/No)
5. Review outcomes under **Logs**

For demos without real faults:

```bash
boss-sentinel --simulate-issue memory
```
