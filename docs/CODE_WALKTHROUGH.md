# BOSS-Sentinel — Code Walkthrough (Step by Step)

**Version:** 2.2.2  
**Audience:** You want every module explained, line by line where files are small, and block-by-block where files are large.

Open each source file beside this document and follow the section numbers.

---

# Part A — How the process starts

## A1. `scripts/boss-sentinel` (bash launcher)

This is what `/usr/bin/boss-sentinel` is.

| Lines | What they do |
|-------|----------------|
| `1` | Shebang — run with bash |
| `2–3` | Comments: default UI is GTK3 because GTK4 crashes on many BOSS VMs |
| `4` | `set -euo pipefail` — exit on error, treat unset vars as errors, fail pipelines |
| `6` | Resolve repo root when running from a checkout (`scripts/../`) |
| `7–15` | Search for `boss-sentinel-gtk3.py` in install path, next to launcher, or `scripts/` |
| `17–25` | Set `BOSS_SENTINEL_HELPER` to the pkexec helper path (install or dev) |
| `27–36` | **Default path:** unless `BOSS_SENTINEL_UI=cpp`, `exec python3` the GTK3 UI (replaces this process) |
| `28–34` | Export safe graphics env for X11 / software GL |
| `38–46` | Fallback: find C++ binary `boss-sentinel-bin` |
| `47–50` | Error if nothing found |
| `52–55` | If bundled gtkmm libs exist beside the binary, prepend `LD_LIBRARY_PATH` |
| `57–66` | Force GSK cairo / software GL for the C++ path |
| `68` | `exec` the C++ binary |

**Mental model:** launcher never draws UI; it only chooses which program becomes the UI.

---

## A2. `scripts/boss-sentinel-helper` (privileged Python)

Runs as root via `pkexec`. Prints **one JSON object** to stdout.

### Imports & contract (lines 1–18)

| Lines | Meaning |
|-------|---------|
| `1` | Python 3 shebang |
| `2–4` | Docstring: stdout contract |
| `7` | Future annotations |
| `9–13` | stdlib: JSON, OS, subprocess, Path |
| `16–18` | `emit()` prints `{"ok","message","details"}` and returns exit 0/1 |

### Action: `cpu_performance` (21–43)

1. Walk `/sys/devices/system/cpu/cpuN/cpufreq/scaling_governor`.  
2. Write `performance` to each writable governor.  
3. If none writable, try `powerprofilesctl set performance`.  
4. Emit success or failure JSON.

### Action: `power_performance` (46–60)

Only `powerprofilesctl set performance`, with clear error messages.

### Action: `io_boost` (63–80)

1. For each `/sys/block/*/queue/scheduler`, read available schedulers.  
2. Prefer `none` → `mq-deadline` → `kyber` → `bfq`.  
3. Write choice; collect details like `sda=mq-deadline`.

### Action: `drop_caches` (83–89)

`os.sync()` then write `3` to `/proc/sys/vm/drop_caches` (drop pagecache + dentries + inodes).

### Action: `renice_hogs` (92–117)

1. `ps` sorted by CPU.  
2. For top PIDs (skip PID 1), `os.setpriority(..., 5)` to lower priority.  

### Action: `purge_disk` (120–147)

Caches + `apt-get clean` + delete obvious temp junk under `/tmp` and `/var/tmp`.

### Actions: `apt_update` / `apt_upgrade` (150–186)

Noninteractive apt with timeouts; truncate stderr into `details`.

### Dispatch table (188–213)

| Lines | Meaning |
|-------|---------|
| `188–197` | `ACTIONS` maps CLI name → function |
| `200–209` | `main()`: require argv[1], look up action, run it |
| `212–213` | Classic `if __name__ == "__main__"` entry |

**Call pattern from the UI:**

```bash
pkexec /usr/libexec/boss-sentinel/boss-sentinel-helper drop_caches
# → {"ok": true, "message": "Page caches dropped", "details": ""}
```

---

# Part B — GTK3 gauges (`scripts/gauges_gtk3.py`)

Cairo drawings on **GTK3** `DrawingArea` (no GTK4 GSK).

## B1. Colors & helpers (1–32)

| Lines | Meaning |
|-------|---------|
| `1–2` | Shebang + module docstring |
| `4–8` | Imports: math, deque, typing |
| `10–14` | `cairo` + `gi` → Gtk 3.0 |
| `16–24` | RGB tuples matching product CSS (canvas, blue, ok, amber, fault…) |
| `27–32` | `_color_for(pct, warn, crit)` → FAULT / AMBER / BLUE |

## B2. `_CairoArea` base (35–52)

| Lines | Meaning |
|-------|---------|
| `35` | Subclass of `Gtk.DrawingArea` |
| `36–40` | Size request, expand, connect `"draw"` signal |
| `42–49` | On draw: get width/height, call `_paint`, never throw out of draw |
| `51–52` | Abstract `_paint` for subclasses |

**Why `"draw"`?** GTK3 API. GTK4 uses `set_draw_func` instead.

## B3. `DeviceGraph` (55–…)

Live area chart used on Overview / CPU / Memory / Disk.

| Method | Behavior |
|--------|----------|
| `__init__` | Title, history deque of 60 samples, 500 ms animation tick |
| `update(...)` | Store value/unit/detail/thresholds; append clamped sample; `queue_draw()` |
| `_tick` | Advance sine phase for subtle motion; keep timer alive |
| `_paint` | White card → title → big value → detail → filled area polyline → stroke → tip dot |

Color of the line comes from `_color_for` vs warn/crit thresholds.

## B4. `HeroVitality`

Circular health score (breathing ring). `set_score(score, overall)` changes color (`ok`/`warn`/`crit`).

## B5. `BreathWave`

Full-width waveform of recent health scores.

## B6. `DiskPie`

Donut chart:

1. Draw used wedge (severity color).  
2. Draw free wedge (teal).  
3. Punch center hole + center `%`.  
4. Legend on the right: Used / Free with human sizes.

## B7. `MultiCpuGraph` (GNOME System Monitor style)

| Idea | Implementation |
|------|----------------|
| One history series per logical CPU | `list[deque]` length 60 |
| One colored line per CPU | `_CPU_LINE_COLORS` cycle (red, orange, blue, …) |
| Grid | Horizontal 0/25/50/75/100% lines |
| Legend | `CPU1: 12.3%` color swatches along the bottom |

This is the “how much load on each CPU” graph you asked for.

## B8. `CpuCoreMeter` + `PerCpuMonitor`

- Meter = label `CPU{n}` + ProgressBar + percent.  
- Monitor = FlowBox grid of meters, grown/shrunk as core count changes.

---

# Part C — Main GTK3 UI (`scripts/boss-sentinel-gtk3.py`)

~1200 lines. Explained **in execution order** and by function.

## C1. Imports & paths (1–52)

| Block | Meaning |
|-------|---------|
| Future + stdlib | json, os, pwd, subprocess, Path, typing |
| `gi.require_version("Gtk","3.0")` | Must run before importing Gtk |
| `_HERE` + `sys.path` | So `import gauges_gtk3` works from `/usr/lib/boss-sentinel/` |
| Import gauges | DeviceGraph, DiskPie, MultiCpuGraph, PerCpuMonitor, … |
| Path constants | Helper candidates, log file, settings file, CSS candidates |

## C2. Persistence helpers (55–73)

| Function | Lines of logic |
|----------|----------------|
| `log(msg)` | Ensure log dir exists; append timestamped INFO line |
| `load_settings()` | Read JSON or default `{prompt_on_issue: true, poll_ms: 2500}` |
| `save_settings(data)` | Write pretty JSON |

## C3. Helper IPC (76–…)

| Function | Logic |
|----------|-------|
| `find_helper()` | First executable path in `HELPER_CANDIDATES` |
| `run_helper(action)` | Try `pkexec helper action`, then plain helper; parse last `{...}` JSON line |

## C4. Sampling (`sample_cpu`, `read_mem`, `read_disk`, …)

### `sample_cpu`

1. Read `/proc/stat` once → busy/total for `cpu` and each `cpuN`.  
2. First call: store previous sample, return `0.0` (no UI-thread sleep).  
3. Later calls: delta busy/total → overall % and per-core % list.

### `read_mem`

Parse `/proc/meminfo` → mem %, used/total MB, swap %, swap used.

### `read_disk`

`os.statvfs("/")` → used %, used GiB, free GiB.

### `score_of`

Start at 100; subtract for warn/crit on CPU/RAM/DISK/SWAP/TEMP; return `(score, overall, issues)`.

### `list_processes` / `list_services`

Walk `/proc` for RSS-sorted processes; `systemctl list-units --state=running` for services.

## C5. Widget helpers

| Helper | Role |
|--------|------|
| `_section(title)` | Styled section label |
| `_scroll(child)` | Vertical ScrolledWindow |
| `_chip` / `_stat_tile` | Metric chip / tile factories |
| `_cell(graph)` | White rounded frame around a gauge |

## C6. `MainWindow.__init__`

1. Window title/size + CSS class.  
2. Load settings; init autoheal flag; empty event lists (heal/trouble/update).  
3. `_load_css()` → `_build()` → log start.  
4. `GLib.idle_add(self.refresh)` first paint after loop starts.  
5. `GLib.timeout_add(poll_ms, self._tick)` periodic refresh.  
6. `show_all()`.

## C7. `_build` — layout skeleton

```
root VERTICAL
  topbar (brand + AUTOHEAL GUARD + close)
  status strip (HeroVitality + status text)
  BreathWave
  metric chips (CPU RAM DISK LOAD)
  tab bar (StackSwitcher)
  Stack pages…
  footer
```

Stack pages registered:

Overview · CPU · Memory · Disk · Processes · Services · **Autoheal** · Optimize · **Updates** · Logs

## C8. Autoheal control (`_build_topbar`, `_set_autoheal`)

Segmented **ON** / **OFF** buttons (not a plain Switch):

- ON → green active class; prompts enabled  
- OFF → dark active class; quiet monitoring  
- Persists via `save_settings`  
- Writes a heal-log note when toggled  

## C9. Tab builders (summary)

| Method | Builds |
|--------|--------|
| `_build_overview` | 2×2 DeviceGraphs, autoheal card, issues list |
| `_build_cpu` | tiles, **MultiCpuGraph**, **PerCpuMonitor**, overall DeviceGraph |
| `_build_memory` | RAM/SWAP tiles + graphs |
| `_build_disk` | **DiskPie** + trend DeviceGraph |
| `_build_processes` | header + scrollable rows |
| `_build_services` | running units list |
| `_build_autoheal` | control card + **heal log box** + run-now button |
| `_build_optimize` | plan text + YES/NO buttons + result label |
| `_build_updates` | tiles, Check/Install, sources, packages, update log |
| `_build_logs` | inner stack: Trouble / Heal / Update / Full TextView |

## C10. `refresh()` — the heart of the UI loop

Every poll:

1. Sample CPU/mem/disk/temp.  
2. Compute score/issues.  
3. Update hero, wave, chips, all graphs, pie, process/service tables.  
4. If new issue set → `_note("trouble", ...)`.  
5. `_maybe_prompt` if autoheal on.  
6. Update footer + file log.

## C11. Heal / optimize (`run_heal_and_optimize`)

For each action in  
`drop_caches, purge_disk, cpu_performance, io_boost, power_performance`:

1. `run_helper(action)`  
2. Append to result lines  
3. `_note("heal", action, message)`  

Then show MessageDialog “What was optimized”.

## C12. Updates flow

| Step | Code |
|------|------|
| Check | Background thread: `run_helper("apt_update")` + `apt-get -s upgrade` parse `Inst` lines |
| Finish | Update tiles, package list, `_note("update", …)` on UI thread via `GLib.idle_add` |
| Install | Confirm dialog → `run_helper("apt_upgrade")` → re-check |

## C13. Event logs (`_note`, `_paint_event_logs`)

In-memory lists:

- `heal_events`  
- `trouble_events`  
- `update_events`  

Each entry = `(HH:MM:SS, title, detail)`.  
Painted into Autoheal tab, Updates tab, and Logs sub-tabs.

## C14. `main()`

```python
os.environ.setdefault("GDK_BACKEND", "x11")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
MainWindow()
Gtk.main()
```

---

# Part D — Theme `scripts/style-gtk3.css`

Explains the look without changing logic.

| Selector group | Purpose |
|----------------|---------|
| `@define-color …` | Palette variables (canvas, blue, ok, fault) |
| `window.boss-sentinel-window` | App background |
| `.brand` / `.brand-sub` | Top-left product name |
| `.autoheal-panel` / `.autoheal-seg` | Attractive ON/OFF control |
| `.tab-switcher button:checked` | Active tab = blue pill |
| `.device-cell` | Graph frames |
| `.opt-yes` / `.opt-no` | Optimize buttons |
| `.cpu-core-meter` | Individual CPU tiles |

---

# Part E — Install / purge scripts

## E1. `install-unified.sh`

1. Purge packages `boss-sentinel`, `boss-optimize`, …  
2. Delete `boss-sentinel*.deb` / `boss-optimize*.deb` under Home/Downloads/tmp (keep the new one).  
3. Download `boss-sentinel_2.2.2-1_amd64.deb` into `~/boss-sentinel/`.  
4. Install GTK3 deps (python3-gi, python3-cairo, …) via cache or apt.  
5. `dpkg -i` the new package.

## E2. `purge-boss-sentinel.sh`

1. Kill running processes.  
2. `dpkg --purge` related packages.  
3. `rm -rf` `/usr/bin/boss-sentinel`, `/usr/lib/boss-sentinel`, configs, icons, polkit, desktop files.  
4. Wipe user `~/.config` / `~/.local/share` / Downloads leftovers.  
5. Delete leftover `.deb`s; refresh desktop DB; verify clean.

---

# Part F — Optional C++ GTK4 path (`src/`)

Used only when `BOSS_SENTINEL_UI=cpp`. Same product ideas.

## F1. `src/main.cpp` (line by line)

| Line(s) | Meaning |
|---------|---------|
| `1` | Include Application |
| `3` | `cstdlib` for `setenv` |
| `5` | Logger |
| `7–22` | Anonymous namespace: `force_safe_graphics()` sets GSK/Mesa/GDK env **before** GTK init |
| `26–36` | `main`: force graphics → log start → `Application::create()->run` → log exit |

## F2. `src/core/types.hpp`

Defines shared structs: `Severity`, `Metric`, `Issue`, `ProcessRow`, `ServiceRow`, `Snapshot`, `ActionResult`, plus `now_iso()` / `bytes_human()`.

## F3. `src/core/logger.*`

Singleton logger writing to `~/.local/share/boss-sentinel/boss-sentinel.log`.

## F4. `src/core/settings.*`

Load/save `settings.json` (`prompt_on_issue`, `poll_ms`).

## F5. `src/core/paths.*`

Find helper script and CSS next to binary or in `/usr`.

## F6. `src/monitor/engine.*`

C++ sampler for `/proc/stat`, meminfo, disk, processes, services → `Snapshot` + issues.  
**Important:** first CPU sample returns 0 without sleeping on the GTK thread.

## F7. `src/heal/healer.*` & `src/optimize/optimizer.*`

`popen("pkexec helper <action>")`, parse JSON `"ok"` / `"message"`.  
Optimizer runs the fixed suite of four performance actions.

## F8. `src/app/application.*`

`Gtk::Application` subclass; `on_activate` creates `MainWindow`, handles close via idle delete.

## F9. `src/ui/*`

| File | Role |
|------|------|
| `main_window.*` | GTK4 tabs (Overview…Logs) |
| `gauges.*` | LevelBar/Label gauges (Cairo DrawingArea removed for BOSS safety) |
| `dialogs.*` | Yes/No `MessageDialog` |
| `style.css` | GTK4 stylesheet |

---

# Part G — Packaging

## G1. `CMakeLists.txt`

- Project `boss-sentinel` version from `project(... VERSION x.y.z)`  
- C++20 executable `boss-sentinel-bin` from all `src/*.cpp`  
- Links gtkmm-4.0 / glibmm  

## G2. `packaging/build-deb.sh`

1. Read version from CMakeLists.  
2. Configure + build Release.  
3. **Reject** binaries needing GLIBC 2.38+.  
4. Stage tree under `build/stage/…/usr/...`  
5. Install GTK3 scripts + CSS + helper + optional C++ binary + docs.  
6. Write `DEBIAN/control` (Depends on python3-gi/cairo/gtk3).  
7. `dpkg-deb --build` → `releases/boss-sentinel_<ver>-1_amd64.deb`.

## G3. Desktop / polkit / icon

| File | Role |
|------|------|
| `data/desktop/….desktop` | Menu entry; `Exec=env … boss-sentinel` |
| `data/polkit/….policy` | Allows pkexec helper |
| `data/icons/….svg` | App icon |

---

# Part H — End-to-end story (one sentence each)

1. User runs `boss-sentinel`.  
2. Launcher starts **GTK3** Python UI.  
3. UI polls `/proc`, draws graphs/pie/GNOME CPU lines.  
4. Pressure + Autoheal ON → Yes/No dialog.  
5. Yes → `pkexec` helper actions → JSON results → popup + heal log.  
6. Everything appends to `boss-sentinel.log`.

---

# Part I — How to read the big UI file yourself

For `boss-sentinel-gtk3.py`, search these anchors in order:

```
def sample_cpu
def score_of
class MainWindow
def _build_topbar
def _build_cpu
def _build_autoheal
def _build_updates
def _build_logs
def refresh
def run_heal_and_optimize
def _start_update_check
def main
```

Each function’s docstring / first comment block matches a section above.

---

# Part J — Related documents

- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)  
- [FILE_STRUCTURE.md](FILE_STRUCTURE.md)  
- [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)  
- [USER_GUIDE.md](USER_GUIDE.md)  
- [BUILD.md](BUILD.md)  
