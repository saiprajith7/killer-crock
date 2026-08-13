# BOSS-Sentinel — File Structure

Complete map of the repository as of **v2.2.2**.

```
boss-sentinel / killer-crock
│
├── README.md                      # Quick start, install, version notes
├── CMakeLists.txt                 # C++ GTK4 optional binary build
├── .gitignore
│
├── docs/                          # ★ Documentation (read these)
│   ├── DOCUMENTATION_INDEX.md     # Master index — start here
│   ├── FILE_STRUCTURE.md          # This file
│   ├── SYSTEM_DESIGN.md           # Architecture, flows, privileges
│   ├── USER_GUIDE.md              # End-user install / use / purge
│   ├── BUILD.md                   # How to compile & package .deb
│   └── CODE_WALKTHROUGH.md        # Step-by-step explanation of every module
│
├── scripts/                       # ★ Runtime default path (GTK3)
│   ├── boss-sentinel              # /usr/bin launcher (bash)
│   ├── boss-sentinel-gtk3.py      # Main GTK3 UI (~1200 lines)
│   ├── gauges_gtk3.py             # Cairo graphs, pie, GNOME CPU chart
│   ├── style-gtk3.css             # GTK3 theme (slate + trust blue)
│   ├── boss-sentinel-helper       # Privileged actions via pkexec (Python)
│   ├── install-unified.sh         # Install + purge old packages/.debs
│   ├── install-boss-sentinel.sh   # Compat wrapper → install-unified.sh
│   └── purge-boss-sentinel.sh     # Complete system removal
│
├── src/                           # Optional C++ / gtkmm-4 binary
│   ├── main.cpp                   # Entry: force software GL, run app
│   ├── app/
│   │   ├── application.hpp/.cpp   # Gtk::Application activate / window
│   ├── core/
│   │   ├── types.hpp              # Snapshot, Issue, Metric, Severity
│   │   ├── logger.hpp/.cpp        # File logger
│   │   ├── settings.hpp/.cpp      # ~/.config/.../settings.json
│   │   └── paths.hpp/.cpp         # Helper / CSS path discovery
│   ├── monitor/
│   │   └── engine.hpp/.cpp        # /proc sampling → Snapshot
│   ├── heal/
│   │   └── healer.hpp/.cpp        # Issue → pkexec helper actions
│   ├── optimize/
│   │   └── optimizer.hpp/.cpp     # Performance suite
│   └── ui/
│       ├── main_window.hpp/.cpp   # GTK4 rich window (optional path)
│       ├── gauges.hpp/.cpp        # LevelBar gauges (no Cairo draw)
│       ├── dialogs.hpp/.cpp       # Yes/No MessageDialog
│       └── style.css              # GTK4 CSS
│
├── data/
│   ├── desktop/org.bosssentinel.BossSentinel.desktop
│   ├── icons/org.bosssentinel.BossSentinel.svg
│   └── polkit/org.bosssentinel.policy
│
├── packaging/
│   └── build-deb.sh               # Build Release binary + .deb
│
├── debian/                        # Packaging metadata / changelog
│   ├── changelog
│   ├── control (generated at build)
│   ├── postinst, prerm, rules, …
│
└── releases/
    ├── boss-sentinel_2.2.2-1_amd64.deb
    ├── boss-sentinel_latest_amd64.deb
    └── README.md
```

## What runs on BOSS by default

| Path | Role |
|------|------|
| `/usr/bin/boss-sentinel` | Launcher script |
| `/usr/lib/boss-sentinel/boss-sentinel-gtk3.py` | **Default UI** |
| `/usr/lib/boss-sentinel/gauges_gtk3.py` | Graphs / pie / CPU history |
| `/usr/share/boss-sentinel/style-gtk3.css` | Theme |
| `/usr/libexec/boss-sentinel/boss-sentinel-helper` | Root actions |
| `/usr/lib/boss-sentinel/boss-sentinel-bin` | Optional C++ UI (`BOSS_SENTINEL_UI=cpp`) |

## User data (runtime)

| Path | Purpose |
|------|---------|
| `~/.config/boss-sentinel/settings.json` | Autoheal on/off, poll interval |
| `~/.local/share/boss-sentinel/boss-sentinel.log` | Append-only event log |

## Installed docs

Copied into `/usr/share/doc/boss-sentinel/` by the `.deb` (README + docs/*.md).
