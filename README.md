# BOSS Health — System Readiness

One application for **BOSS GNU/Linux** (Cinnamon / Army & Navy client OS): Connectivity, System Health, and Services in a single readiness dashboard.

CPU, RAM, Disk, and Overall System Health **reuse the existing BOSS-Sentinel collectors** (`CpuCollector`, `MemoryCollector`, `DiskCollector`, `HealthEngine`). They are not duplicated.

## Architecture

```
                    BOSS HEALTH
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   CONNECTIVITY     SYSTEM HEALTH      SERVICES
   Repo · ISOC ·    CPU · RAM · Disk   Critical ·
   Network          · Overall          Security
                    (sentinel)
```

## Install

```bash
sudo dpkg -i ./dist/boss-sentinel_1.3.0-1_all.deb
sudo apt -f install   # if dependencies are missing
```

Then:

```bash
boss-health              # GTK readiness dashboard
boss-health --once       # JSON results (no GUI)
boss-sentinel            # full existing sentinel monitor (unchanged)
```

### Cinnamon panel icon

1. Right-click panel → **Applets** → add **BOSS Health**
2. Click the panel icon → runs checks → opens the dashboard

## Run from source

```bash
PYTHONPATH=src python3 -m boss_health
PYTHONPATH=src python3 -m boss_health --once
make test
```

## What was reused vs added

| Reused (sentinel) | Added (BOSS Health) |
|-------------------|---------------------|
| `vitaheal.monitor.cpu.CpuCollector` | Repository / ISOC / Network checks |
| `vitaheal.monitor.memory.MemoryCollector` | Critical / Security services checks |
| `vitaheal.monitor.disk.DiskCollector` | Readiness orchestrator + GTK dashboard |
| `vitaheal.monitor.engine.HealthEngine` overall score | Cinnamon applet + `/etc/boss-health` config |

See [TREE.md](TREE.md) for the full file tree.

## Dashboard

- ✓ green = PASS · ⚠ yellow = WARNING · ✗ red = FAIL
- Overall: SYSTEM READY / ACTION REQUIRED / SYSTEM NOT READY
- Buttons: **View Details** · **Run Check Again** · **Close**

## Configure

Edit `/etc/boss-health/boss-health.conf` for ISOC hosts and service lists.
