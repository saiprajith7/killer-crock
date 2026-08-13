# BOSS-Sentinel — System Design

**Version:** 2.2.2  
**Product:** Unified health monitor + autoheal + performance optimize  
**Default UI:** Python **GTK3** (stable on BOSS Linux)  
**Optional UI:** C++ **gtkmm-4** (`BOSS_SENTINEL_UI=cpp`)

---

## 1. Goals

Merge former **BOSS-Sentinel** (health / autoheal) and **BOSS-Optimize** (performance) into one app that:

1. Continuously monitors CPU, memory, disk, swap, processes, services.
2. Shows rich tabs (graphs, disk pie, GNOME-style per-CPU history).
3. Asks **Yes / No** before healing when Autoheal is ON.
4. On Yes (or Optimize tab), runs heal **and** performance actions.
5. Logs every snapshot, heal, optimize, and update event.
6. Supports apt **Updates** check/install and structured logs.

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  /usr/bin/boss-sentinel  (bash launcher)                        │
│    default → python3 boss-sentinel-gtk3.py                      │
│    BOSS_SENTINEL_UI=cpp → boss-sentinel-bin (gtkmm-4)           │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
   ┌─────────────────────┐      ┌──────────────────────┐
   │  GTK3 UI (default)  │      │  C++ GTK4 UI (opt.)  │
   │  MainWindow         │      │  MainWindow          │
   │  gauges_gtk3.py     │      │  MonitorEngine       │
   │  (Cairo DrawingArea)│      │  Healer / Optimizer  │
   └──────────┬──────────┘      └──────────┬───────────┘
              │                            │
              └────────────┬───────────────┘
                           ▼
              ┌────────────────────────────┐
              │  boss-sentinel-helper      │
              │  (Python, via pkexec)      │
              │  sysfs / apt / caches      │
              └────────────────────────────┘
                           │
                           ▼
              ~/.local/share/boss-sentinel/boss-sentinel.log
```

---

## 3. Component map

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Launch | `scripts/boss-sentinel` | Pick GTK3 vs C++, set safe graphics env |
| UI | `boss-sentinel-gtk3.py` | Tabs, polling, dialogs, settings, apt UI |
| Widgets | `gauges_gtk3.py` | DeviceGraph, DiskPie, MultiCpuGraph, HeroVitality |
| Theme | `style-gtk3.css` | Colors, autoheal segment, tabs |
| Privilege | `boss-sentinel-helper` | Root actions; JSON stdout |
| Optional | `src/*` | Same product ideas in C++/GTK4 |
| Package | `packaging/build-deb.sh` | Bookworm .deb (glibc ≤ 2.36) |

---

## 4. UI tabs (GTK3 default)

| Tab | Contents |
|-----|----------|
| Overview | 4 device graphs, autoheal card, active issues |
| CPU | Stat tiles, **GNOME multi-line CPU history**, individual meters, overall graph |
| Memory | RAM/SWAP tiles + graphs |
| Disk | **Pie chart** (used/free) + trend graph |
| Processes | Top RSS processes |
| Services | Running systemd units |
| Autoheal | ON/OFF control, manual heal, **heal log** |
| Optimize | Plan + YES/NO optimize |
| Updates | Check/Install apt, sources, packages, update log |
| Logs | Sub-tabs: Trouble · Heal · Update · Full file |

---

## 5. Autoheal + optimize flow

```
every poll_ms (default 2500)
        │
        ▼
 sample /proc → score + issues
        │
        ├─ update all graphs / tables
        │
        └─ if Autoheal ON and severity ≠ ok and cooldown elapsed
                 │
                 ▼
           MessageDialog Yes/No
                 │
            No ──┴── Yes
                      │
                      ▼
              for action in [drop_caches, purge_disk,
                             cpu_performance, io_boost,
                             power_performance]:
                    pkexec helper <action>
                      │
                      ▼
              Result popup + heal log entries
```

---

## 6. Privilege model

- GUI always runs as the **user**.
- Writes to sysfs / apt go through:

```
pkexec /usr/libexec/boss-sentinel/boss-sentinel-helper <action>
```

- Helper prints one JSON line:

```json
{"ok": true, "message": "…", "details": "…"}
```

- Polkit policy: `data/polkit/org.bosssentinel.policy`  
  Action id: `org.bosssentinel.helper`

### Helper actions

| Action | Effect |
|--------|--------|
| `cpu_performance` | CPU governor → performance (or powerprofilesctl) |
| `power_performance` | `powerprofilesctl set performance` |
| `io_boost` | Prefer fast block I/O schedulers |
| `drop_caches` | `echo 3 > /proc/sys/vm/drop_caches` |
| `renice_hogs` | Nice busy processes |
| `purge_disk` | Caches + apt-clean + temp cleanup |
| `apt_update` | `apt-get update` |
| `apt_upgrade` | `apt-get upgrade -y` |

---

## 7. Data & config

| File | Format |
|------|--------|
| `~/.config/boss-sentinel/settings.json` | `{"prompt_on_issue": true, "poll_ms": 2500}` |
| `~/.local/share/boss-sentinel/boss-sentinel.log` | Timestamped INFO lines |

---

## 8. Packaging & platform

- **Target:** Debian 12 / BOSS Linux, **glibc 2.36**
- Build `.deb` on bookworm (not Ubuntu 24.04) to avoid `GLIBC_2.38+`
- Package `Conflicts`/`Replaces`/`Provides`: `boss-optimize`
- Default Depends: `python3`, `python3-gi`, `python3-cairo`, `gir1.2-gtk-3.0`, `libgtk-3-0`

---

## 9. Why GTK3 by default

BOSS VMs often fail EGL/DRI2 authentication. GTK4’s GSK renderer then segfaults.  
GTK3 Cairo `DrawingArea` draws via X11/cairo without GSK → stable graphs on BOSS.

---

## 10. Related docs

- [FILE_STRUCTURE.md](FILE_STRUCTURE.md) — tree of every file  
- [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md) — line/module explanation  
- [USER_GUIDE.md](USER_GUIDE.md) — install, use, purge  
- [BUILD.md](BUILD.md) — compile & package  
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) — master index  
