# BOSS-Sentinel

Unified **health monitoring**, **auto-heal**, and **performance optimization** in one C++ GTK4 application.

## What it does

1. Continuously monitors CPU, memory, disk, processes, and services.
2. When pressure is detected, shows a **Yes / No** popup asking to auto-heal.
3. On **Yes**, runs heal actions **and** the performance optimization suite.
4. Shows a popup listing **what was optimized**, then closes automatically.
5. Logs every snapshot, prompt, heal, and optimize event to  
   `~/.local/share/boss-sentinel/boss-sentinel.log`.

## Quick install (BOSS Linux / Debian 12)

```bash
curl -L -o boss-sentinel_2.1.0-1_amd64.deb \
  https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/releases/boss-sentinel_2.1.0-1_amd64.deb

sudo dpkg -i /var/cache/apt/archives/libsigc++-3.0-0_*.deb \
             /var/cache/apt/archives/libcairomm-1.16-1_*.deb \
             /var/cache/apt/archives/libpangomm-2.48-1_*.deb \
             /var/cache/apt/archives/libglibmm-2.68-1_*.deb \
             /var/cache/apt/archives/libgtkmm-4.0-0_*.deb 2>/dev/null || true

sudo dpkg -i ./boss-sentinel_2.1.0-1_amd64.deb
boss-sentinel
```

v2.1.0 brings back the rich Sentinel UI: live Cairo graphs, vitality ring,
per-CPU meters, process/service tables, and Optimize Yes/No — built for
Debian 12 / BOSS (glibc 2.36).

## Build

See [docs/BUILD.md](docs/BUILD.md). System design: [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md).

## File structure

```
boss-sentinel/
├── CMakeLists.txt
├── README.md
├── debian/                 # Debian packaging metadata
├── packaging/build-deb.sh  # Produces releases/*.deb
├── scripts/
│   ├── boss-sentinel              # /usr/bin launcher
│   └── boss-sentinel-helper       # pkexec privileged helper (Python)
├── data/
│   ├── desktop/…desktop
│   ├── icons/….svg
│   └── polkit/….policy
├── docs/
│   ├── BUILD.md
│   └── SYSTEM_DESIGN.md
├── releases/               # Built .deb artifacts
└── src/
    ├── main.cpp
    ├── app/                # Gtk::Application
    ├── core/               # types, logger, settings
    ├── monitor/            # /proc + systemd snapshot engine
    ├── heal/               # issue → helper actions
    ├── optimize/           # performance suite
    └── ui/                 # gtkmm-4 window, dialogs, CSS
```

## Requirements

- Linux with GTK 4 / gtkmm 4
- `pkexec` / PolicyKit for privileged heal & optimize
- CMake ≥ 3.16, g++ with C++20

## License

MIT
