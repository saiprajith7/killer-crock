# BOSS-Sentinel — System Design

## Goals

Merge the former **BOSS-Sentinel** (health / auto-heal) and **BOSS-Optimize** (performance allotment) products into one C++ GTK4 application named **BOSS-Sentinel** that:

1. Monitors system health continuously.
2. Asks the user before healing.
3. On confirmation, **heals and optimizes performance**.
4. Logs every action.
5. Reports what performance steps ran, then closes the result popup.

## High-level architecture

```
┌──────────────────────────────────────────────────────────┐
│                     GTK4 UI (gtkmm)                       │
│  MainWindow · AlertDialog (Yes/No) · ResultPopup          │
└───────────────┬─────────────────────────────┬────────────┘
                │                             │
                ▼                             ▼
        MonitorEngine                   Healer + Optimizer
        (/proc, systemd)                (pkexec helper IPC)
                │                             │
                └──────────► Logger ◄─────────┘
                     ~/.local/share/boss-sentinel/
```

### Components

| Module | Role |
|--------|------|
| `src/app` | `Gtk::Application` lifecycle, APP_ID `org.bosssentinel.BossSentinel` |
| `src/monitor` | Snapshot: CPU, memory, disk, top processes, running services, derived issues |
| `src/heal` | Maps issues → privileged actions (`drop_caches`, `renice_hogs`, `purge_disk`, …) |
| `src/optimize` | Performance suite: CPU governor, I/O scheduler, drop caches, power profile |
| `src/core` | Shared types, ring + file logger, settings JSON |
| `src/ui` | Attractive hero UI, tabs, dialogs, CSS |
| `scripts/boss-sentinel-helper` | Root-capable Python helper invoked via `pkexec` |

## Auto-heal + optimize flow

```
poll every N ms
    │
    ▼
snapshot → derive issues (Warn / Critical)
    │
    ├─ none → update UI only
    │
    └─ pressure + prompts enabled + cooldown elapsed
            │
            ▼
      AlertDialog: "Auto-heal and optimize?"
            │
       No ──┴── Yes
                 │
                 ▼
         Healer.run_issue_heals(issues)
                 │
                 ▼
         Optimizer.run_all()
           · cpu_performance
           · io_boost
           · drop_caches
           · power_performance
                 │
                 ▼
         ResultPopup (lists actions) → auto-close
                 │
                 ▼
         Logger writes EVENT/heal & EVENT/optimize lines
```

## Privilege model

- The GUI always runs as the user.
- Destructive / sysfs writes go through `pkexec` → `boss-sentinel-helper`.
- Polkit action: `org.bosssentinel.helper` (`data/polkit/org.bosssentinel.policy`).
- Helper returns JSON `{ "ok": bool, "message": str }` parsed by C++ callers.

## Logging

Every important step uses `boss::Logger`:

- Snapshot summaries (`INFO`)
- UI prompts (`EVENT/ui`)
- Heal / optimize outcomes (`EVENT/heal`, `EVENT/optimize`)
- Settings changes (`EVENT/settings`)

Persisted under `~/.local/share/boss-sentinel/boss-sentinel.log` and mirrored in the **Logs** tab.

## UI principles

- Brand **BOSS-SENTINEL** is the hero signal (teal industrial theme).
- First composition: brand, one tagline, controls, live score — not a dense dashboard of cards.
- Motion via CSS fade / hover transitions on chips and tabs.
- Popups are modal, short, and the optimize summary auto-closes.

## Packaging

- Native C++ binary installed to `/usr/lib/boss-sentinel/boss-sentinel-bin`.
- Wrapper `/usr/bin/boss-sentinel`.
- Assets: CSS, desktop file, SVG icon, polkit policy.
- Artifact built by `packaging/build-deb.sh`.

## Extensibility

- New heal actions: add to helper `ACTIONS` map + issue mapping in `MonitorEngine::derive_issues`.
- New optimize steps: append to the list in `Optimizer::run_all`.
- Settings already gate prompts and poll rate without recompilation.
