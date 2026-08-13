#!/usr/bin/env python3
"""BOSS-Sentinel rich GTK3 UI — tabs, graphs, disk pie, attractive autoheal.

Matches the confirmed prior Sentinel + Optimize product look, without GTK4/GSK.
"""

from __future__ import annotations

import json
import os
import pwd
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

# Allow running from /usr/lib/boss-sentinel or scripts/
_HERE = Path(__file__).resolve().parent
import sys

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from gauges_gtk3 import (  # noqa: E402
    BreathWave,
    DeviceGraph,
    DiskPie,
    HeroVitality,
    MultiCpuGraph,
    PerCpuMonitor,
)

HELPER_CANDIDATES = [
    os.environ.get("BOSS_SENTINEL_HELPER", ""),
    "/usr/libexec/boss-sentinel/boss-sentinel-helper",
    str(_HERE / "boss-sentinel-helper"),
    str(_HERE.parent / "scripts" / "boss-sentinel-helper"),
]
LOG_DIR = Path.home() / ".local" / "share" / "boss-sentinel"
LOG_FILE = LOG_DIR / "boss-sentinel.log"
CFG_DIR = Path.home() / ".config" / "boss-sentinel"
CFG_FILE = CFG_DIR / "settings.json"
CSS_CANDIDATES = [
    "/usr/share/boss-sentinel/style-gtk3.css",
    str(_HERE / "style-gtk3.css"),
    str(_HERE.parent / "scripts" / "style-gtk3.css"),
]


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [INFO] {msg}\n")


def load_settings() -> dict:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    if CFG_FILE.exists():
        try:
            return json.loads(CFG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"prompt_on_issue": True, "poll_ms": 2500}


def save_settings(data: dict) -> None:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    CFG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def find_helper() -> str:
    for c in HELPER_CANDIDATES:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    return ""


def run_helper(action: str) -> dict:
    helper = find_helper()
    if not helper:
        return {"ok": False, "message": "Helper missing", "details": ""}
    last = ""
    for cmd in (["pkexec", helper, action], [helper, action]):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            text = (proc.stdout or "").strip() or (proc.stderr or "").strip()
            lines = [ln for ln in text.splitlines() if ln.strip().startswith("{")]
            if lines:
                return json.loads(lines[-1])
            last = text or f"exit {proc.returncode}"
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
    return {"ok": False, "message": "Helper failed", "details": last}


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def sample_cpu() -> Tuple[float, List[float]]:
    def once():
        lines = _read("/proc/stat").splitlines()
        all_busy = all_total = 0
        cores = []
        for line in lines:
            if not line.startswith("cpu"):
                break
            parts = line.split()
            vals = list(map(int, parts[1:8]))
            busy = sum(vals) - vals[3]
            total = sum(vals)
            if parts[0] == "cpu":
                all_busy, all_total = busy, total
            else:
                cores.append((busy, total))
        return all_busy, all_total, cores

    if not hasattr(sample_cpu, "_prev"):
        sample_cpu._prev = once()  # type: ignore[attr-defined]
        return 0.0, [0.0] * len(sample_cpu._prev[2])  # type: ignore[attr-defined]
    b1, t1, c1 = sample_cpu._prev  # type: ignore[attr-defined]
    b2, t2, c2 = once()
    sample_cpu._prev = (b2, t2, c2)  # type: ignore[attr-defined]
    dt = t2 - t1
    overall = 0.0 if dt <= 0 else max(0.0, min(100.0, (b2 - b1) / dt * 100.0))
    per = []
    for i, (b, t) in enumerate(c2):
        if i < len(c1):
            db, dtot = b - c1[i][0], t - c1[i][1]
            per.append(0.0 if dtot <= 0 else max(0.0, min(100.0, db / dtot * 100.0)))
        else:
            per.append(0.0)
    return overall, per


def read_mem() -> Tuple[float, float, float, float, float]:
    info: Dict[str, int] = {}
    for line in _read("/proc/meminfo").splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        info[k] = int(v.strip().split()[0])
    total = info.get("MemTotal", 1)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    used = max(0, total - avail)
    swap_t = info.get("SwapTotal", 0)
    swap_f = info.get("SwapFree", 0)
    mem_pct = used / total * 100.0
    swap_pct = ((swap_t - swap_f) / swap_t * 100.0) if swap_t else 0.0
    return mem_pct, used / 1024.0, total / 1024.0, swap_pct, (swap_t - swap_f) / 1024.0


def read_disk(path: str = "/") -> Tuple[float, float, float]:
    st = os.statvfs(path)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - free
    pct = 0.0 if total <= 0 else used / total * 100.0
    return pct, used / (1024**3), free / (1024**3)


def human_gb(v: float) -> str:
    return f"{v:.1f}G"


def loadavg() -> str:
    parts = _read("/proc/loadavg").split()
    return " ".join(parts[:3]) if parts else "—"


def cpu_model() -> str:
    for line in _read("/proc/cpuinfo").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return "CPU"


def read_temp() -> float:
    for p in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            return int(p.read_text().strip()) / 1000.0
        except Exception:
            continue
    return 0.0


def list_processes(limit: int = 25) -> List[dict]:
    rows = []
    for ent in Path("/proc").iterdir():
        if not ent.name.isdigit():
            continue
        try:
            pid = int(ent.name)
            status = _read(str(ent / "status"))
            name = state = user = "?"
            rss = 0
            for line in status.splitlines():
                if line.startswith("Name:"):
                    name = line.split(None, 1)[1]
                elif line.startswith("State:"):
                    state = line.split()[1]
                elif line.startswith("Uid:"):
                    uid = int(line.split()[1])
                    try:
                        user = pwd.getpwuid(uid).pw_name
                    except Exception:
                        user = str(uid)
                elif line.startswith("VmRSS:"):
                    rss = int(line.split()[1])
            rows.append({"name": name, "pid": pid, "rss": rss / 1024.0, "user": user, "state": state})
        except Exception:
            continue
    rows.sort(key=lambda r: r["rss"], reverse=True)
    return rows[:limit]


def list_services(limit: int = 40) -> List[dict]:
    try:
        proc = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--no-legend", "--plain"],
            capture_output=True,
            text=True,
            timeout=6,
        )
    except Exception:
        return []
    out = []
    for line in proc.stdout.splitlines():
        line = line.strip().lstrip("●").strip()
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        out.append({"name": parts[0], "active": parts[2], "sub": parts[3], "desc": parts[4] if len(parts) > 4 else ""})
        if len(out) >= limit:
            break
    return out


def score_of(cpu, mem, disk, swap, temp):
    score = 100
    issues = []
    for name, val, warn, crit, unit in (
        ("CPU", cpu, 85, 95, "%"),
        ("RAM", mem, 85, 95, "%"),
        ("DISK", disk, 90, 97, "%"),
        ("SWAP", swap, 50, 80, "%"),
        ("TEMP", temp, 80, 90, "°C"),
    ):
        if val <= 0 and name == "TEMP":
            continue
        if val >= crit:
            score -= 22
            issues.append((name, "crit", val, unit))
        elif val >= warn:
            score -= 10
            issues.append((name, "warn", val, unit))
    score = max(0, min(100, score))
    overall = "crit" if any(i[1] == "crit" for i in issues) else "warn" if issues else "ok"
    return score, overall, issues


def _section(title: str) -> Gtk.Label:
    lab = Gtk.Label(label=title, xalign=0)
    lab.get_style_context().add_class("section-label")
    return lab


def _scroll(child: Gtk.Widget) -> Gtk.ScrolledWindow:
    sc = Gtk.ScrolledWindow()
    sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sc.set_vexpand(True)
    sc.add(child)
    return sc


class MainWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="BOSS-Sentinel")
        self.set_default_size(1280, 860)
        self.get_style_context().add_class("boss-sentinel-window")
        self.settings = load_settings()
        self.autoheal = bool(self.settings.get("prompt_on_issue", True))
        self.prompt_open = False
        self.busy = False
        self.last_prompt = 0.0
        self.heal_events: List[Tuple[str, str, str]] = []  # clock, title, detail
        self.trouble_events: List[Tuple[str, str, str]] = []
        self.update_events: List[Tuple[str, str, str]] = []
        self._upd_packages: List[dict] = []
        self._upd_busy = False
        self._load_css()
        self._build()
        log("BOSS-Sentinel rich GTK3 UI 2.2.1 starting")
        GLib.idle_add(self.refresh)
        GLib.timeout_add(int(self.settings.get("poll_ms", 2500)), self._tick)
        self.connect("destroy", Gtk.main_quit)
        self.show_all()

    def _load_css(self) -> None:
        css = Gtk.CssProvider()
        loaded = False
        for path in CSS_CANDIDATES:
            if Path(path).is_file():
                css.load_from_path(path)
                loaded = True
                break
        if not loaded:
            return
        from gi.repository import Gdk

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _page(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.get_style_context().add_class("tab-page")
        box.set_border_width(12)
        return box

    def _build(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)
        root.pack_start(self._build_topbar(), False, False, 0)
        root.pack_start(self._build_status(), False, False, 0)
        self.wave = BreathWave()
        self.wave.set_margin_start(20)
        self.wave.set_margin_end(20)
        root.pack_start(self.wave, False, False, 0)
        root.pack_start(self._build_chips(), False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_vexpand(True)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher.get_style_context().add_class("tab-switcher")
        switcher.set_halign(Gtk.Align.FILL)
        switcher.set_hexpand(True)
        bar = Gtk.Box()
        bar.get_style_context().add_class("tab-bar")
        bar.pack_start(switcher, True, True, 0)
        root.pack_start(bar, False, False, 0)

        self.stack.add_titled(_scroll(self._build_overview()), "overview", "Overview")
        self.stack.add_titled(_scroll(self._build_cpu()), "cpu", "CPU")
        self.stack.add_titled(_scroll(self._build_memory()), "memory", "Memory")
        self.stack.add_titled(_scroll(self._build_disk()), "disk", "Disk")
        self.stack.add_titled(self._build_processes(), "processes", "Processes")
        self.stack.add_titled(_scroll(self._build_services()), "services", "Services")
        self.stack.add_titled(_scroll(self._build_autoheal()), "autoheal", "Autoheal")
        self.stack.add_titled(_scroll(self._build_optimize()), "optimize", "Optimize")
        self.stack.add_titled(_scroll(self._build_updates()), "updates", "Updates")
        self.stack.add_titled(self._build_logs(), "logs", "Logs")
        root.pack_start(self.stack, True, True, 0)

        self.footer = Gtk.Label(label="BOSS-Sentinel · unified health + optimize", xalign=0)
        self.footer.get_style_context().add_class("footer-meta")
        root.pack_start(self.footer, False, False, 0)

    def _build_topbar(self) -> Gtk.Widget:
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        top.get_style_context().add_class("topbar")

        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        brand.set_hexpand(True)
        t = Gtk.Label(label="BOSS-SENTINEL", xalign=0)
        t.get_style_context().add_class("brand")
        s = Gtk.Label(label="SYSTEM HEALTH · AUTOHEAL · PERFORMANCE", xalign=0)
        s.get_style_context().add_class("brand-sub")
        brand.pack_start(t, False, False, 0)
        brand.pack_start(s, False, False, 0)
        top.pack_start(brand, True, True, 0)

        # Attractive autoheal segmented control (not a plain switch)
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        panel.get_style_context().add_class("autoheal-panel")
        title = Gtk.Label(label="AUTOHEAL GUARD", xalign=0)
        title.get_style_context().add_class("autoheal-panel-title")
        panel.pack_start(title, False, False, 0)

        seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        seg.get_style_context().add_class("autoheal-seg")
        self.btn_on = Gtk.Button(label="ON")
        self.btn_off = Gtk.Button(label="OFF")
        self.btn_on.set_tooltip_text("Ask Yes/No before heal + optimize when pressure is detected")
        self.btn_off.set_tooltip_text("Monitor only — no automatic prompts")
        self.btn_on.connect("clicked", lambda *_: self._set_autoheal(True))
        self.btn_off.connect("clicked", lambda *_: self._set_autoheal(False))
        seg.pack_start(self.btn_on, False, False, 0)
        seg.pack_start(self.btn_off, False, False, 0)
        panel.pack_start(seg, False, False, 0)
        self.auto_hint = Gtk.Label(label="Prompts on critical pressure", xalign=0)
        self.auto_hint.get_style_context().add_class("autoheal-panel-hint")
        panel.pack_start(self.auto_hint, False, False, 0)
        top.pack_start(panel, False, False, 0)
        self._sync_autoheal_buttons()

        close_btn = Gtk.Button(label="×")
        close_btn.get_style_context().add_class("close-x")
        close_btn.set_tooltip_text("Close")
        close_btn.connect("clicked", lambda *_: self.destroy())
        top.pack_start(close_btn, False, False, 0)
        return top

    def _sync_autoheal_buttons(self) -> None:
        for b in (self.btn_on, self.btn_off):
            b.get_style_context().remove_class("on-active")
            b.get_style_context().remove_class("off-active")
        if hasattr(self, "ah_tab_on"):
            for b in (self.ah_tab_on, self.ah_tab_off):
                b.get_style_context().remove_class("on-active")
                b.get_style_context().remove_class("off-active")
        if self.autoheal:
            self.btn_on.get_style_context().add_class("on-active")
            self.auto_hint.set_text("Live — will ask before heal + optimize")
            if hasattr(self, "ah_tab_on"):
                self.ah_tab_on.get_style_context().add_class("on-active")
                self.ah_tab_hint.set_text(
                    "ON — critical issues pop up Yes/No before any heal action. "
                    "Heal log below records every action."
                )
                self.ah_tab_title.set_text("Interactive autoheal is ON")
        else:
            self.btn_off.get_style_context().add_class("off-active")
            self.auto_hint.set_text("Quiet — monitoring only")
            if hasattr(self, "ah_tab_off"):
                self.ah_tab_off.get_style_context().add_class("off-active")
                self.ah_tab_hint.set_text(
                    "OFF — monitoring only. Turn ON for heal prompts, or run heal manually."
                )
                self.ah_tab_title.set_text("Interactive autoheal is OFF")

    def _set_autoheal(self, enabled: bool) -> None:
        prev = self.autoheal
        self.autoheal = enabled
        self.settings["prompt_on_issue"] = enabled
        save_settings(self.settings)
        self._sync_autoheal_buttons()
        if enabled != prev:
            self._note(
                "heal",
                "Autoheal enabled" if enabled else "Autoheal disabled",
                "User toggled autoheal " + ("ON" if enabled else "OFF"),
            )
        log(f"Autoheal {'enabled' if enabled else 'disabled'}")

    def _build_status(self) -> Gtk.Widget:
        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        status.get_style_context().add_class("status-strip")
        self.hero = HeroVitality()
        status.pack_start(self.hero, False, False, 0)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        col.set_valign(Gtk.Align.CENTER)
        col.set_hexpand(True)
        self.status_label = Gtk.Label(label="HEALTHY · SYSTEMS NOMINAL", xalign=0)
        self.status_label.get_style_context().add_class("hero-status")
        self.blurb = Gtk.Label(label="Live sensors online. Tabs for every subsystem.", xalign=0)
        self.blurb.get_style_context().add_class("hero-line")
        self.blurb.set_line_wrap(True)
        col.pack_start(self.status_label, False, False, 0)
        col.pack_start(self.blurb, False, False, 0)
        status.pack_start(col, True, True, 0)
        return status

    def _chip(self, title: str):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.get_style_context().add_class("metric-chip")
        box.set_hexpand(True)
        t = Gtk.Label(label=title, xalign=0)
        t.get_style_context().add_class("metric-title")
        v = Gtk.Label(label="—", xalign=0)
        v.get_style_context().add_class("metric-value")
        box.pack_start(t, False, False, 0)
        box.pack_start(v, False, False, 0)
        return box, v

    def _build_chips(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.get_style_context().add_class("metric-row")
        self.chip_cpu_b, self.chip_cpu = self._chip("CPU")
        self.chip_mem_b, self.chip_mem = self._chip("RAM")
        self.chip_disk_b, self.chip_disk = self._chip("DISK")
        self.chip_load_b, self.chip_load = self._chip("LOAD")
        for b in (self.chip_cpu_b, self.chip_mem_b, self.chip_disk_b, self.chip_load_b):
            row.pack_start(b, True, True, 0)
        return row

    def _cell(self, graph: Gtk.Widget) -> Gtk.Box:
        c = Gtk.Box()
        c.get_style_context().add_class("device-cell")
        c.set_hexpand(True)
        c.pack_start(graph, True, True, 0)
        return c

    def _build_overview(self) -> Gtk.Widget:
        page = self._page()
        page.pack_start(_section("LIVE DEVICE GRAPHS"), False, False, 0)
        grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, column_spacing=4, row_spacing=4)
        self.ov_cpu = DeviceGraph("CPU")
        self.ov_mem = DeviceGraph("MEMORY")
        self.ov_disk = DeviceGraph("DISK /")
        self.ov_swap = DeviceGraph("SWAP")
        grid.attach(self._cell(self.ov_cpu), 0, 0, 1, 1)
        grid.attach(self._cell(self.ov_mem), 1, 0, 1, 1)
        grid.attach(self._cell(self.ov_disk), 0, 1, 1, 1)
        grid.attach(self._cell(self.ov_swap), 1, 1, 1, 1)
        page.pack_start(grid, False, False, 0)

        page.pack_start(_section("AUTOHEAL"), False, False, 0)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.get_style_context().add_class("autoheal-card")
        self.ov_auto_title = Gtk.Label(label="Interactive autoheal is ON", xalign=0)
        self.ov_auto_body = Gtk.Label(
            label="When CPU, RAM, disk, or swap pressure rises, BOSS-Sentinel asks Yes/No, "
            "then heals and runs performance optimize.",
            xalign=0,
        )
        self.ov_auto_body.set_line_wrap(True)
        card.pack_start(self.ov_auto_title, False, False, 0)
        card.pack_start(self.ov_auto_body, False, False, 0)
        page.pack_start(card, False, False, 0)

        page.pack_start(_section("ACTIVE ISSUES"), False, False, 0)
        self.issues_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.issues_box.get_style_context().add_class("list-frame")
        page.pack_start(self.issues_box, False, False, 0)
        return page

    def _stat_tile(self, title: str):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.get_style_context().add_class("stat-tile")
        box.set_hexpand(True)
        t = Gtk.Label(label=title, xalign=0)
        t.get_style_context().add_class("stat-title")
        v = Gtk.Label(label="—", xalign=0)
        v.get_style_context().add_class("stat-value")
        d = Gtk.Label(label="", xalign=0)
        d.get_style_context().add_class("stat-detail")
        box.pack_start(t, False, False, 0)
        box.pack_start(v, False, False, 0)
        box.pack_start(d, False, False, 0)
        return box, v, d

    def _build_cpu(self) -> Gtk.Widget:
        page = self._page()
        tiles = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.tile_util_b, self.tile_util, self.tile_util_d = self._stat_tile("UTILIZATION")
        self.tile_cores_b, self.tile_cores, self.tile_cores_d = self._stat_tile("CORES")
        self.tile_threads_b, self.tile_threads, self.tile_threads_d = self._stat_tile("THREADS")
        self.tile_load_b, self.tile_load, self.tile_load_d = self._stat_tile("LOAD AVERAGE")
        for b in (self.tile_util_b, self.tile_cores_b, self.tile_threads_b, self.tile_load_b):
            tiles.pack_start(b, True, True, 0)
        page.pack_start(tiles, False, False, 0)
        self.model_line = Gtk.Label(label="", xalign=0)
        self.model_line.get_style_context().add_class("hero-line")
        page.pack_start(self.model_line, False, False, 0)

        # GNOME System Monitor–style per-CPU history (primary view)
        page.pack_start(_section("CPU HISTORY"), False, False, 0)
        self.multi_cpu = MultiCpuGraph()
        page.pack_start(self._cell(self.multi_cpu), False, False, 0)

        self.cpu_per_cpu = PerCpuMonitor("INDIVIDUAL CPUS")
        page.pack_start(self.cpu_per_cpu, False, False, 0)

        page.pack_start(_section("OVERALL"), False, False, 0)
        self.cpu_big = DeviceGraph("CPU UTILIZATION", height=160)
        page.pack_start(self._cell(self.cpu_big), False, False, 0)
        return page

    def _note(self, bucket: str, title: str, detail: str = "") -> None:
        entry = (time.strftime("%H:%M:%S"), title, detail)
        if bucket == "heal":
            self.heal_events.insert(0, entry)
            self.heal_events = self.heal_events[:120]
        elif bucket == "trouble":
            self.trouble_events.insert(0, entry)
            self.trouble_events = self.trouble_events[:120]
        else:
            self.update_events.insert(0, entry)
            self.update_events = self.update_events[:120]
        log(f"{bucket}: {title} — {detail}")
        self._paint_event_logs()

    def _build_autoheal(self) -> Gtk.Widget:
        page = self._page()
        page.pack_start(_section("AUTOHEAL CONTROL"), False, False, 0)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.get_style_context().add_class("autoheal-card")
        self.ah_tab_title = Gtk.Label(label="Interactive autoheal", xalign=0)
        self.ah_tab_hint = Gtk.Label(label="", xalign=0)
        self.ah_tab_hint.set_line_wrap(True)
        seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        seg.get_style_context().add_class("autoheal-seg")
        self.ah_tab_on = Gtk.Button(label="ON")
        self.ah_tab_off = Gtk.Button(label="OFF")
        self.ah_tab_on.connect("clicked", lambda *_: self._set_autoheal(True))
        self.ah_tab_off.connect("clicked", lambda *_: self._set_autoheal(False))
        seg.pack_start(self.ah_tab_on, False, False, 0)
        seg.pack_start(self.ah_tab_off, False, False, 0)
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        run = Gtk.Button(label="RUN HEAL + OPTIMIZE NOW")
        run.get_style_context().add_class("opt-yes")
        run.connect("clicked", lambda *_: self.run_heal_and_optimize(manual=True))
        btns.pack_start(run, False, False, 0)
        for w in (self.ah_tab_title, self.ah_tab_hint, seg, btns):
            card.pack_start(w, False, False, 0)
        page.pack_start(card, False, False, 0)

        page.pack_start(_section("WHAT BOSS-SENTINEL HEALED"), False, False, 0)
        self.ah_log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.ah_log_box.get_style_context().add_class("list-frame")
        page.pack_start(self.ah_log_box, False, False, 0)
        self._sync_autoheal_buttons()
        return page

    def _build_updates(self) -> Gtk.Widget:
        page = self._page()
        page.pack_start(_section("SYSTEM UPDATES"), False, False, 0)
        tiles = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.upd_count_b, self.upd_count_v, self.upd_count_d = self._stat_tile("AVAILABLE")
        self.upd_src_b, self.upd_src_v, self.upd_src_d = self._stat_tile("SOURCES")
        tiles.pack_start(self.upd_count_b, True, True, 0)
        tiles.pack_start(self.upd_src_b, True, True, 0)
        page.pack_start(tiles, False, False, 0)

        self.upd_summary = Gtk.Label(label="Press Check Updates to query your apt sources.", xalign=0)
        self.upd_summary.get_style_context().add_class("hero-line")
        self.upd_summary.set_line_wrap(True)
        page.pack_start(self.upd_summary, False, False, 0)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.upd_check_btn = Gtk.Button(label="CHECK UPDATES")
        self.upd_check_btn.get_style_context().add_class("opt-yes")
        self.upd_check_btn.connect("clicked", lambda *_: self._start_update_check())
        self.upd_install_btn = Gtk.Button(label="INSTALL UPDATES")
        self.upd_install_btn.get_style_context().add_class("opt-no")
        self.upd_install_btn.set_sensitive(False)
        self.upd_install_btn.connect("clicked", lambda *_: self._prompt_install_updates())
        btns.pack_start(self.upd_check_btn, False, False, 0)
        btns.pack_start(self.upd_install_btn, False, False, 0)
        page.pack_start(btns, False, False, 0)

        page.pack_start(_section("CONFIGURED SOURCES"), False, False, 0)
        self.upd_sources_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.upd_sources_box.get_style_context().add_class("list-frame")
        page.pack_start(self.upd_sources_box, False, False, 0)

        page.pack_start(_section("UPGRADABLE PACKAGES"), False, False, 0)
        self.upd_pkg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.upd_pkg_box.get_style_context().add_class("list-frame")
        page.pack_start(self.upd_pkg_box, False, False, 0)

        page.pack_start(_section("UPDATE LOG"), False, False, 0)
        self.upd_log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.upd_log_box.get_style_context().add_class("list-frame")
        page.pack_start(self.upd_log_box, False, False, 0)

        self._paint_update_sources()
        self.upd_src_v.set_text(str(len(self._read_apt_sources())))
        self.upd_src_d.set_text("from sources.list + sources.list.d")
        self.upd_count_v.set_text("—")
        self.upd_count_d.set_text("not checked yet")
        return page
    def _build_memory(self) -> Gtk.Widget:
        page = self._page()
        tiles = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.tile_ram_b, self.tile_ram, self.tile_ram_d = self._stat_tile("RAM")
        self.tile_swap_b, self.tile_swap, self.tile_swap_d = self._stat_tile("SWAP")
        tiles.pack_start(self.tile_ram_b, True, True, 0)
        tiles.pack_start(self.tile_swap_b, True, True, 0)
        page.pack_start(tiles, False, False, 0)
        grid = Gtk.Grid(column_homogeneous=True, column_spacing=4)
        self.mem_big = DeviceGraph("RAM", height=170)
        self.swap_big = DeviceGraph("SWAP", height=170)
        grid.attach(self._cell(self.mem_big), 0, 0, 1, 1)
        grid.attach(self._cell(self.swap_big), 1, 0, 1, 1)
        page.pack_start(grid, False, False, 0)
        return page

    def _build_disk(self) -> Gtk.Widget:
        page = self._page()
        page.pack_start(_section("DISK SPACE"), False, False, 0)
        self.disk_pie = DiskPie()
        page.pack_start(self._cell(self.disk_pie), False, False, 0)
        page.pack_start(_section("USAGE TREND"), False, False, 0)
        self.disk_big = DeviceGraph("DISK /", height=180)
        page.pack_start(self._cell(self.disk_big), False, False, 0)
        self.disk_detail = Gtk.Label(label="", xalign=0)
        self.disk_detail.get_style_context().add_class("hero-line")
        page.pack_start(self.disk_detail, False, False, 0)
        return page

    def _build_processes(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_border_width(12)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for title, chars in (("PROCESS", 22), ("PID", 8), ("RAM(MB)", 10), ("USER", 10), ("STATE", 8)):
            lab = Gtk.Label(label=title, xalign=0)
            lab.set_width_chars(chars)
            if title == "PROCESS":
                lab.set_hexpand(True)
            head.pack_start(lab, title == "PROCESS", True, 0)
        outer.pack_start(head, False, False, 0)
        self.proc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.proc_box.get_style_context().add_class("list-frame")
        outer.pack_start(_scroll(self.proc_box), True, True, 0)
        return outer

    def _build_services(self) -> Gtk.Widget:
        page = self._page()
        page.pack_start(_section("RUNNING SYSTEMD SERVICES"), False, False, 0)
        self.svc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.svc_box.get_style_context().add_class("list-frame")
        page.pack_start(self.svc_box, False, False, 0)
        return page

    def _build_optimize(self) -> Gtk.Widget:
        page = self._page()
        page.pack_start(_section("OPTIMIZE PERFORMANCE"), False, False, 0)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.get_style_context().add_class("opt-card")
        self.opt_title = Gtk.Label(label="Ready to allot hardware to active work?", xalign=0)
        self.opt_body = Gtk.Label(
            label="YES runs CPU performance, I/O boost, cache drop, and power profile "
            "(password prompt may appear via pkexec).",
            xalign=0,
        )
        self.opt_body.set_line_wrap(True)
        self.opt_plan = Gtk.Label(
            label="• CPU governor → performance\n• I/O scheduler boost\n• Drop caches\n• Power profile → performance",
            xalign=0,
        )
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        yes = Gtk.Button(label="YES — Optimize now")
        yes.get_style_context().add_class("opt-yes")
        yes.connect("clicked", lambda *_: self.run_heal_and_optimize(manual=True))
        no = Gtk.Button(label="NO — Keep current allotment")
        no.get_style_context().add_class("opt-no")
        no.connect("clicked", lambda *_: self._opt_skip())
        btns.pack_start(yes, False, False, 0)
        btns.pack_start(no, False, False, 0)
        self.opt_result = Gtk.Label(label="", xalign=0)
        self.opt_result.set_line_wrap(True)
        for w in (self.opt_title, self.opt_body, self.opt_plan, btns, self.opt_result):
            card.pack_start(w, False, False, 0)
        page.pack_start(card, False, False, 0)
        return page

    def _build_logs(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_border_width(8)
        log_stack = Gtk.Stack()
        log_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        log_stack.set_vexpand(True)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(log_stack)
        switcher.get_style_context().add_class("tab-switcher")
        switcher.set_halign(Gtk.Align.CENTER)
        bar = Gtk.Box()
        bar.set_halign(Gtk.Align.CENTER)
        bar.get_style_context().add_class("tab-bar")
        bar.pack_start(switcher, False, False, 0)
        outer.pack_start(bar, False, False, 0)

        def log_page(title: str, attr: str) -> Gtk.Widget:
            page = self._page()
            page.pack_start(_section(title), False, False, 0)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.get_style_context().add_class("list-frame")
            setattr(self, attr, box)
            page.pack_start(_scroll(box), True, True, 0)
            return page

        log_stack.add_titled(log_page("WHAT'S CAUSING TROUBLE", "trouble_box"), "trouble", "Trouble Log")
        log_stack.add_titled(log_page("WHAT BOSS-SENTINEL HEALED", "heal_box"), "heal", "Heal Log")
        log_stack.add_titled(log_page("SYSTEM UPDATE LOG", "update_log_box"), "updates", "Update Log")

        # Full file log
        file_page = self._page()
        file_page.pack_start(_section("EVENT LOG FILE"), False, False, 0)
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_buf = self.log_view.get_buffer()
        sc = Gtk.ScrolledWindow()
        sc.set_vexpand(True)
        sc.add(self.log_view)
        file_page.pack_start(sc, True, True, 0)
        log_stack.add_titled(file_page, "file", "Full Log")

        outer.pack_start(log_stack, True, True, 0)
        return outer

    def _read_apt_sources(self) -> List[dict]:
        out = []
        files = []
        sl = Path("/etc/apt/sources.list")
        sd = Path("/etc/apt/sources.list.d")
        if sl.exists():
            files.append(sl)
        if sd.exists():
            files.extend(sorted(sd.glob("*.list")))
            files.extend(sorted(sd.glob("*.sources")))
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    body = line.lstrip("#").strip()
                    if body.startswith(("deb ", "deb-src ", "Types:")):
                        out.append({"file": path.name, "line": body, "enabled": False})
                    continue
                if line.startswith(("deb ", "deb-src ", "Types:", "URIs:", "Suites:")):
                    out.append({"file": path.name, "line": line, "enabled": True})
        return out

    def _paint_update_sources(self) -> None:
        if not hasattr(self, "upd_sources_box"):
            return
        self._clear(self.upd_sources_box)
        sources = self._read_apt_sources()
        if not sources:
            self.upd_sources_box.pack_start(
                Gtk.Label(label="No apt sources found under /etc/apt/.", xalign=0), False, False, 0
            )
        else:
            for src in sources[:40]:
                flag = "ON" if src["enabled"] else "OFF"
                lab = Gtk.Label(
                    label=f"{src['file']} [{flag}]  ·  {src['line'][:90]}", xalign=0
                )
                lab.set_ellipsize(Pango.EllipsizeMode.END)
                self.upd_sources_box.pack_start(lab, False, False, 0)
        self.upd_sources_box.show_all()

    def _paint_update_packages(self) -> None:
        if not hasattr(self, "upd_pkg_box"):
            return
        self._clear(self.upd_pkg_box)
        if not self._upd_packages:
            self.upd_pkg_box.pack_start(
                Gtk.Label(label="No upgradable packages (run Check Updates).", xalign=0),
                False,
                False,
                0,
            )
        else:
            for pkg in self._upd_packages[:80]:
                lab = Gtk.Label(
                    label=f"{pkg['name']}  ·  {pkg['current']} → {pkg['candidate']}", xalign=0
                )
                self.upd_pkg_box.pack_start(lab, False, False, 0)
        self.upd_pkg_box.show_all()

    def _paint_event_logs(self) -> None:
        def fill(box_name: str, events: List[Tuple[str, str, str]], empty: str) -> None:
            if not hasattr(self, box_name):
                return
            box = getattr(self, box_name)
            self._clear(box)
            if not events:
                box.pack_start(Gtk.Label(label=empty, xalign=0), False, False, 0)
            else:
                for clock, title, detail in events[:80]:
                    lab = Gtk.Label(label=f"{clock}  ·  {title}  —  {detail}"[:140], xalign=0)
                    lab.set_ellipsize(Pango.EllipsizeMode.END)
                    box.pack_start(lab, False, False, 0)
            box.show_all()

        fill("ah_log_box", self.heal_events, "No heal actions yet.")
        fill("heal_box", self.heal_events, "No heal actions yet.")
        fill("trouble_box", self.trouble_events, "No trouble events yet.")
        fill("update_log_box", self.update_events, "No system update activity yet.")
        fill("upd_log_box", self.update_events, "No system update activity yet.")

    def _start_update_check(self) -> None:
        if self._upd_busy:
            return
        import threading

        self._upd_busy = True
        self.upd_check_btn.set_sensitive(False)
        self.upd_install_btn.set_sensitive(False)
        self.upd_summary.set_text("Checking apt sources…")
        self._note("update", "Checking for updates", "Reading sources and simulating upgrade")

        def work() -> None:
            # Refresh indexes via pkexec helper when available
            run_helper("apt_update")
            pkgs: List[dict] = []
            err = ""
            try:
                env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "LANG": "C"}
                proc = subprocess.run(
                    ["apt-get", "-s", "-o", "Debug::NoLocking=1", "upgrade"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env=env,
                )
                import re

                inst_re = re.compile(r"^Inst\s+(\S+)\s+(?:\[([^\]]*)\]\s+)?\(([^ )]+)")
                for line in (proc.stdout or "").splitlines():
                    m = inst_re.match(line.strip())
                    if m:
                        pkgs.append(
                            {
                                "name": m.group(1),
                                "current": m.group(2) or "?",
                                "candidate": m.group(3),
                            }
                        )
                if proc.returncode != 0 and not pkgs:
                    err = (proc.stderr or proc.stdout or "apt-get simulate failed")[:200]
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
            GLib.idle_add(self._finish_update_check, pkgs, err)

        threading.Thread(target=work, daemon=True).start()

    def _finish_update_check(self, pkgs: List[dict], err: str) -> bool:
        self._upd_busy = False
        self.upd_check_btn.set_sensitive(True)
        self._upd_packages = pkgs
        sources = self._read_apt_sources()
        self.upd_src_v.set_text(str(len(sources)))
        self.upd_src_d.set_text("from sources.list + sources.list.d")
        self.upd_count_v.set_text(str(len(pkgs)))
        self.upd_count_d.set_text("upgradable packages")
        self.upd_install_btn.set_sensitive(len(pkgs) > 0)
        if err and not pkgs:
            self.upd_summary.set_text(f"Check finished with error: {err}")
            self._note("update", "Update check error", err)
        elif pkgs:
            names = ", ".join(p["name"] for p in pkgs[:12])
            more = f" (+{len(pkgs) - 12} more)" if len(pkgs) > 12 else ""
            self.upd_summary.set_text(f"{len(pkgs)} update(s) available: {names}{more}")
            self._note("update", f"Update check complete — {len(pkgs)} available", names[:120])
        else:
            self.upd_summary.set_text("System is up to date.")
            self._note("update", "Update check complete — 0 available", "System is up to date")
        self._paint_update_sources()
        self._paint_update_packages()
        return False

    def _prompt_install_updates(self) -> None:
        if not self._upd_packages:
            return
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Install {len(self._upd_packages)} update(s)?",
        )
        dlg.format_secondary_text(
            "This runs apt-get upgrade via pkexec (password may be required).\n"
            + ", ".join(p["name"] for p in self._upd_packages[:20])
        )
        resp = dlg.run()
        dlg.destroy()
        if resp != Gtk.ResponseType.YES:
            self._note("update", "Updates declined", "User chose No")
            return
        self._note("update", "Installing updates", f"{len(self._upd_packages)} packages")
        res = run_helper("apt_upgrade")
        ok = bool(res.get("ok"))
        msg = res.get("message", "?")
        self._note("update", "apt-get upgrade", msg)
        self.upd_summary.set_text(("Installed: " if ok else "Failed: ") + msg)
        self._start_update_check()

    def _tick(self) -> bool:
        self.refresh()
        return True

    def _clear(self, box: Gtk.Box) -> None:
        for child in list(box.get_children()):
            box.remove(child)

    def refresh(self) -> None:
        try:
            cpu, per_cpu = sample_cpu()
            mem, used_mb, total_mb, swap, swap_used_mb = read_mem()
            disk, used_g, free_g = read_disk("/")
            temp = read_temp()
            score, overall, issues = score_of(cpu, mem, disk, swap, temp)

            self.hero.set_score(score, overall)
            self.wave.push(score)

            ctx = self.status_label.get_style_context()
            for c in ("warn", "crit"):
                ctx.remove_class(c)
            if overall == "crit":
                self.status_label.set_text("CRITICAL · ACTION NEEDED")
                ctx.add_class("crit")
            elif overall == "warn":
                self.status_label.set_text("WARNING · WATCH CLOSELY")
                ctx.add_class("warn")
            else:
                self.status_label.set_text("HEALTHY · SYSTEMS NOMINAL")
            self.blurb.set_text(
                f"{4 + len(per_cpu)} sensors · score {score}/100 · {len(issues)} issue(s) · "
                f"autoheal {'on' if self.autoheal else 'off'}"
            )
            self.ov_auto_title.set_text(
                f"Interactive autoheal is {'ON' if self.autoheal else 'OFF'}"
            )

            self.chip_cpu.set_text(f"{cpu:.0f}%")
            self.chip_mem.set_text(f"{mem:.0f}%")
            self.chip_disk.set_text(f"{disk:.0f}%")
            self.chip_load.set_text(loadavg().split()[0] if loadavg() != "—" else "—")

            model = cpu_model()
            self.ov_cpu.update(cpu, "%", model[:40])
            self.ov_mem.update(mem, "%", f"{used_mb:.0f}/{total_mb:.0f} MB")
            self.ov_disk.update(disk, "%", f"{human_gb(used_g)} used · {human_gb(free_g)} free")
            self.ov_swap.update(swap, "%", f"{swap_used_mb:.0f} MB used")

            self.cpu_big.update(cpu, "%", "live utilization")
            self.multi_cpu.update(per_cpu)
            self.cpu_per_cpu.update(per_cpu)
            self.tile_util.set_text(f"{cpu:.0f}%")
            self.tile_util_d.set_text("overall")
            ncpu = len(per_cpu) or 1
            self.tile_cores.set_text(str(ncpu))
            self.tile_cores_d.set_text("logical CPUs")
            self.tile_threads.set_text(str(ncpu))
            self.tile_threads_d.set_text("hardware threads")
            self.tile_load.set_text(loadavg())
            self.tile_load_d.set_text("1 / 5 / 15")
            self.model_line.set_text(model)

            self.mem_big.update(mem, "%", f"{used_mb:.0f} / {total_mb:.0f} MB")
            self.swap_big.update(swap, "%", f"{swap_used_mb:.0f} MB")
            self.tile_ram.set_text(f"{mem:.0f}%")
            self.tile_ram_d.set_text(f"{used_mb:.0f} / {total_mb:.0f} MB")
            self.tile_swap.set_text(f"{swap:.0f}%")
            self.tile_swap_d.set_text(f"{swap_used_mb:.0f} MB used")

            self.disk_pie.update(disk, human_gb(used_g), human_gb(free_g), "DISK /")
            self.disk_big.update(disk, "%", f"{human_gb(used_g)} used")
            self.disk_detail.set_text(
                f"Root volume · {human_gb(used_g)} used · {human_gb(free_g)} free · {disk:.1f}% full"
            )

            self._paint_issues(issues)
            self._paint_processes()
            self._paint_services()
            self._reload_log()
            self.footer.set_text(
                f"BOSS-Sentinel 2.2.1 · CPU {cpu:.0f}% · RAM {mem:.0f}% · DISK {disk:.0f}% · refreshed"
            )
            log(f"Snapshot score={score} cpu={cpu:.0f} mem={mem:.0f}")
            if issues:
                # Record new trouble only when severity changes set
                key = "|".join(f"{n}:{s}:{v:.0f}" for n, s, v, u in issues)
                if getattr(self, "_last_issue_key", "") != key:
                    self._last_issue_key = key
                    self._note(
                        "trouble",
                        f"{len(issues)} issue(s) detected",
                        ", ".join(f"{n} {v:.0f}{u}" for n, s, v, u in issues),
                    )
            self._maybe_prompt(overall, issues)
        except Exception as exc:  # noqa: BLE001
            log(f"refresh error: {exc}")

    def _paint_issues(self, issues) -> None:
        self._clear(self.issues_box)
        if not issues:
            lab = Gtk.Label(label="No active issues", xalign=0)
            self.issues_box.pack_start(lab, False, False, 0)
        else:
            for name, sev, val, unit in issues:
                row = Gtk.Label(label=f"• {name}  {val:.0f}{unit}  [{sev.upper()}]", xalign=0)
                row.get_style_context().add_class("issue-row")
                self.issues_box.pack_start(row, False, False, 0)
        self.issues_box.show_all()

    def _paint_processes(self) -> None:
        self._clear(self.proc_box)
        for p in list_processes():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.get_style_context().add_class("proc-row")
            cells = (
                (p["name"][:28], True, 22),
                (str(p["pid"]), False, 8),
                (f"{p['rss']:.0f}", False, 10),
                (str(p["user"])[:10], False, 10),
                (str(p["state"]), False, 8),
            )
            for text, expand, width in cells:
                lab = Gtk.Label(label=text, xalign=0)
                lab.set_width_chars(width)
                lab.set_ellipsize(Pango.EllipsizeMode.END)
                if expand:
                    lab.set_hexpand(True)
                row.pack_start(lab, expand, True, 0)
            self.proc_box.pack_start(row, False, False, 0)
        self.proc_box.show_all()

    def _paint_services(self) -> None:
        self._clear(self.svc_box)
        svcs = list_services()
        if not svcs:
            self.svc_box.pack_start(Gtk.Label(label="No systemd services listed", xalign=0), False, False, 0)
        for s in svcs:
            lab = Gtk.Label(label=f"{s['name']}  ·  {s['active']}/{s['sub']}  ·  {s['desc'][:48]}", xalign=0)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            lab.get_style_context().add_class("svc-row")
            self.svc_box.pack_start(lab, False, False, 0)
        self.svc_box.show_all()

    def _reload_log(self) -> None:
        if not LOG_FILE.exists():
            return
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]
        self.log_buf.set_text("\n".join(lines))

    def _maybe_prompt(self, overall, issues) -> None:
        if not self.autoheal or self.prompt_open or self.busy or overall == "ok":
            return
        if time.time() - self.last_prompt < 90:
            return
        self.prompt_open = True
        self.last_prompt = time.time()
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text="System pressure detected — autoheal?",
        )
        dlg.format_secondary_text(
            "Run heal actions and performance optimize now?\n\n"
            + "\n".join(f"{n} {v:.0f}{u} ({s})" for n, s, v, u in issues)
        )
        resp = dlg.run()
        dlg.destroy()
        self.prompt_open = False
        if resp == Gtk.ResponseType.YES:
            self.run_heal_and_optimize(manual=False)

    def _opt_skip(self) -> None:
        self.opt_result.set_text("Optimization skipped. Monitoring continues.")
        log("User declined optimize from Optimize tab")

    def run_heal_and_optimize(self, manual: bool = False) -> None:
        if self.busy:
            return
        self.busy = True
        actions = ["drop_caches", "purge_disk", "cpu_performance", "io_boost", "power_performance"]
        lines = []
        self._note("heal", "Heal + optimize started", "manual" if manual else "autoheal prompt")
        for act in actions:
            res = run_helper(act)
            ok = bool(res.get("ok"))
            msg = res.get("message", "?")
            lines.append(f"{'✓' if ok else '✗'} {act}: {msg}")
            self._note("heal", act, msg)
        self.busy = False
        text = "\n".join(lines)
        self.opt_result.set_text(text)
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="What was optimized",
        )
        dlg.format_secondary_text(text)
        dlg.run()
        dlg.destroy()
        self._reload_log()
        self._paint_event_logs()

def main() -> int:
    os.environ.setdefault("GDK_BACKEND", "x11")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    MainWindow()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
