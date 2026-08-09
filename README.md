# VitaHeal

**Native Debian PC health monitor with interactive autohealing.**

Not a web app. VitaHeal is a GTK4 / libadwaita desktop application that ships as a `.deb`, registers a systemd user daemon + XDG autostart entry, and installs like any other OS utility.

When a critical fault is detected it **pops up a dialog naming the issue and asks Yes or No** before any heal action runs.

## Features

- Live vitals: CPU, load, memory, swap, disk, inodes, temperature, **GPU** (NVIDIA/AMD/Intel), network, zombies
- Cyber-medical HUD UI (Cairo pulse rings, arc gauges, scrolling waveform)
- Autoheal armed mode → Yes/No confirmation → privileged helper via polkit/`pkexec`
- Background daemon with desktop notifications that launches the GUI for decisions
- Proper Debian packaging (`vitaheal` package)

## File structure

```
vitaheal/
├── README.md
├── Makefile
├── pyproject.toml
├── debian/                      # Debian package metadata
│   ├── control
│   ├── rules
│   ├── changelog
│   ├── compat
│   ├── copyright
│   ├── postinst                 # enable user daemon on install
│   ├── prerm
│   └── source/format
├── data/
│   ├── desktop/
│   │   ├── vitaheal.desktop           # app menu launcher
│   │   └── vitaheal-daemon.desktop    # XDG autostart
│   ├── systemd/
│   │   └── vitaheal-daemon.service    # systemd --user unit
│   ├── polkit/
│   │   └── org.vitaheal.policy        # privilege escalation policy
│   └── icons/
│       └── vitaheal.svg
├── scripts/
│   └── vitaheal-helper          # root helper invoked via pkexec
├── src/vitaheal/
│   ├── __init__.py
│   ├── __main__.py              # CLI: GUI / --once / --daemon
│   ├── app.py                   # Adw.Application bootstrap
│   ├── monitor/
│   │   ├── models.py
│   │   ├── engine.py            # aggregates collectors → issues
│   │   ├── cpu.py
│   │   ├── memory.py
│   │   ├── disk.py
│   │   ├── temperature.py
│   │   ├── gpu.py               # NVIDIA / AMD / Intel
│   │   ├── network.py
│   │   └── process.py
│   ├── heal/
│   │   └── actions.py           # heal catalog + helper IPC
│   ├── daemon/
│   │   └── watcher.py           # headless notifier
│   └── ui/
│       ├── style.css            # HUD theme
│       ├── gauges.py            # Cairo pulse/arc/wave widgets
│       ├── heal_dialog.py       # Yes/No autoheal popup
│       └── window.py            # main window
└── tests/
    └── test_engine.py
```

## Heal actions (always confirm first)

| Issue | Action id | What it does |
|-------|-----------|--------------|
| CPU overload | `renice_hogs` | Renice top non-critical CPU hogs |
| Memory pressure | `drop_caches` | `sync` + drop page caches |
| Swap thrash | `reset_swap` | `swapoff -a && swapon -a` |
| Disk full | `purge_disk` | apt clean, journal vacuum, temp purge |
| Inode pressure | `prune_tmp` | Prune scratch temps |
| Thermal | `thermal_cooldown` | Set cpufreq governor to `powersave` |
| GPU / VRAM / GPU temp | `gpu_cooldown` | NVIDIA power limit / AMD `performance_level=low` |
| Zombies | `reap_zombies` | SIGCHLD parent processes |
| Load spike | `pause_timers` | Pause safe apt/fstrim timers |

## Install on Debian / Ubuntu

### From source (dev)

```bash
sudo apt update
sudo apt install -y python3 python3-gi python3-gi-cairo python3-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 policykit-1 libnotify-bin \
  fonts-jetbrains-mono

cd /path/to/vitaheal
sudo make install
vitaheal
```

### Build & install the `.deb` (ships with the OS)

```bash
sudo apt install -y debhelper dh-python pybuild-plugin-pyproject python3-setuptools dpkg-dev
make deb
sudo apt install ./dist/vitaheal_1.0.0-1_all.deb
```

After install:

```bash
# GUI
vitaheal

# Enable background watcher for your user session
systemctl --user enable --now vitaheal-daemon.service
```

The package also drops `/etc/xdg/autostart/vitaheal-daemon.desktop` so the watcher starts with the graphical session.

## Usage

```bash
vitaheal                          # open HUD
vitaheal --once                   # JSON health snapshot
vitaheal --simulate-issue memory  # demo critical memory + heal popup
vitaheal-daemon --interval 20     # headless watcher
```

## Autoheal UX contract

1. Monitor detects a **critical** issue  
2. Popup shows the **issue title + description + proposed action**  
3. User chooses **Yes — Heal Now** or **No**  
4. Only on Yes does VitaHeal call the polkit helper  

Manual **HEAL?** buttons in the heal queue use the same popup.

## License

GPL-3.0-or-later
