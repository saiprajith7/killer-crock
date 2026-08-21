# BOSS Health — project file tree (reference)

```
boss-health / workspace
├── README.md
├── TREE.md                          ← this file
├── Makefile
├── pyproject.toml
├── debian/                          ← .deb packaging
│   ├── control
│   ├── rules
│   └── …
├── packaging/
│   └── build-deb.sh
├── data/
│   ├── config/
│   │   └── boss-health.conf         ← default connectivity / services lists
│   ├── desktop/
│   │   ├── boss-health.desktop      ← application launcher
│   │   └── vitaheal.desktop         ← existing BOSS-Sentinel launcher
│   ├── icons/
│   │   ├── boss-health.svg          ← menu-bar / app icon
│   │   └── vitaheal.svg             ← existing sentinel icon
│   ├── cinnamon/applets/
│   │   └── boss-health@boss/
│   │       ├── applet.js            ← Cinnamon panel click → dashboard
│   │       └── metadata.json
│   ├── polkit/
│   └── systemd/
├── scripts/
│   └── vitaheal-helper              ← existing privileged helper
├── src/
│   ├── boss_health/                 ← NEW: System Readiness app
│   │   ├── __init__.py
│   │   ├── __main__.py              ← `boss-health` / `python3 -m boss_health`
│   │   ├── config.py
│   │   ├── models.py                ← CheckStatus / CheckResult / Report
│   │   ├── connectivity.py          ← Repository · ISOC · Network
│   │   ├── services.py              ← Critical · Security services
│   │   ├── readiness.py             ← orchestrator (reuses sentinel)
│   │   ├── dashboard.py             ← GTK3 readiness dashboard
│   │   └── style.css
│   └── vitaheal/                    ← EXISTING BOSS-Sentinel (REUSED)
│       ├── monitor/
│       │   ├── cpu.py               ← CpuCollector  ← reused for CPU
│       │   ├── memory.py            ← MemoryCollector ← reused for RAM
│       │   ├── disk.py              ← DiskCollector ← reused for Disk
│       │   ├── engine.py            ← HealthEngine / overall score ← reused
│       │   └── models.py
│       ├── ui/                      ← existing full sentinel UI (unchanged)
│       ├── heal/
│       └── daemon/
└── tests/
    └── test_boss_health_readiness.py
```

## Click flow

```
Cinnamon BOSS Health icon (applet)
        ↓
boss-health
        ↓
run_all_checks()  [boss_health.readiness]
   ├── connectivity: Repository / ISOC / Network
   ├── system: CPU / RAM / Disk / Overall  ← HealthEngine (vitaheal)
   └── services: Critical / Security
        ↓
GTK dashboard (all results)
```
