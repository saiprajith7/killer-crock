#!/usr/bin/env python3
"""BOSS-Sentinel GTK3 UI — avoids GTK4/GSK/EGL crashes on BOSS Linux."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

APP_ID = "org.bosssentinel.BossSentinel"
HELPER_CANDIDATES = [
    os.environ.get("BOSS_SENTINEL_HELPER", ""),
    "/usr/libexec/boss-sentinel/boss-sentinel-helper",
    str(Path(__file__).resolve().parent / "boss-sentinel-helper"),
    str(Path(__file__).resolve().parent.parent / "scripts" / "boss-sentinel-helper"),
]
LOG_DIR = Path.home() / ".local" / "share" / "boss-sentinel"
LOG_FILE = LOG_DIR / "boss-sentinel.log"
CFG_DIR = Path.home() / ".config" / "boss-sentinel"
CFG_FILE = CFG_DIR / "settings.json"


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [INFO] {msg}\n"
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line)


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
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            text = (proc.stdout or "").strip() or (proc.stderr or "").strip()
            if text.startswith("{") or "\n{" in text:
                line = [ln for ln in text.splitlines() if ln.strip().startswith("{")][-1]
                return json.loads(line)
            last = text or f"exit {proc.returncode}"
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            continue
    return {"ok": False, "message": "Helper failed", "details": last}


def read_cpu() -> float:
    def sample():
        with open("/proc/stat", encoding="utf-8") as fh:
            parts = fh.readline().split()
        vals = list(map(int, parts[1:8]))
        idle = vals[3] + vals[4]
        total = sum(vals)
        return idle, total

    i1, t1 = sample()
    time.sleep(0.12)
    i2, t2 = sample()
    dt, di = (t2 - t1), (i2 - i1)
    if dt <= 0:
        return 0.0
    return max(0.0, min(100.0, (1.0 - di / dt) * 100.0))


def read_mem() -> tuple[float, float, float]:
    info = {}
    with open("/proc/meminfo", encoding="utf-8") as fh:
        for line in fh:
            key, val = line.split(":")
            info[key] = int(val.strip().split()[0])  # kB
    total = info.get("MemTotal", 1)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    used = max(0, total - avail)
    swap_t = info.get("SwapTotal", 0) or 1
    swap_f = info.get("SwapFree", 0)
    mem_pct = used / total * 100.0
    swap_pct = (swap_t - swap_f) / swap_t * 100.0 if info.get("SwapTotal", 0) else 0.0
    return mem_pct, used / 1024.0, total / 1024.0  # MB-ish for display we use %


def read_disk(path: str = "/") -> float:
    st = os.statvfs(path)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    if total <= 0:
        return 0.0
    return (1.0 - free / total) * 100.0


def read_load() -> str:
    try:
        with open("/proc/loadavg", encoding="utf-8") as fh:
            a, b, c, *_ = fh.read().split()
        return f"{a} {b} {c}"
    except OSError:
        return "—"


def score_of(cpu: float, mem: float, disk: float, swap: float):
    score = 100
    issues = []
    for name, val, warn, crit in (
        ("CPU", cpu, 85, 95),
        ("RAM", mem, 85, 95),
        ("DISK", disk, 90, 97),
        ("SWAP", swap, 50, 80),
    ):
        if val >= crit:
            score -= 25
            issues.append((name, "crit", val))
        elif val >= warn:
            score -= 12
            issues.append((name, "warn", val))
    score = max(0, min(100, score))
    overall = "ok"
    if any(i[1] == "crit" for i in issues):
        overall = "crit"
    elif issues:
        overall = "warn"
    return score, overall, issues


class MainWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="BOSS-Sentinel")
        self.set_default_size(980, 640)
        self.settings = load_settings()
        self.prompt_open = False
        self.busy = False
        self.last_prompt = 0.0

        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            window { background: #f1f5f9; }
            .brand { font-weight: 800; font-size: 18px; color: #1e40af; letter-spacing: 2px; }
            .sub { font-size: 11px; color: #64748b; letter-spacing: 1px; }
            .card { background: #ffffff; border: 1px solid rgba(15,23,42,0.10); border-radius: 6px; padding: 12px; }
            .metric { font-size: 28px; font-weight: 700; color: #1e40af; }
            .ok { color: #059669; }
            .warn { color: #d97706; }
            .crit { color: #dc2626; }
            .section { font-size: 11px; font-weight: 700; color: #1e40af; letter-spacing: 2px; margin-top: 8px; }
            """
        )
        try:
            from gi.repository import Gdk

            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception:
            pass

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_border_width(16)
        self.add(root)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="BOSS-SENTINEL", xalign=0)
        title.get_style_context().add_class("brand")
        sub = Gtk.Label(label="SYSTEM HEALTH · AUTOHEAL · PERFORMANCE  (GTK3)", xalign=0)
        sub.get_style_context().add_class("sub")
        brand.pack_start(title, False, False, 0)
        brand.pack_start(sub, False, False, 0)
        top.pack_start(brand, True, True, 0)

        self.autoheal = Gtk.Switch()
        self.autoheal.set_active(bool(self.settings.get("prompt_on_issue", True)))
        self.autoheal.connect("notify::active", self.on_autoheal)
        ah = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ah.pack_start(Gtk.Label(label="AUTOHEAL"), False, False, 0)
        ah.pack_start(self.autoheal, False, False, 0)
        top.pack_end(ah, False, False, 0)
        root.pack_start(top, False, False, 0)

        self.status = Gtk.Label(label="HEALTHY · SYSTEMS NOMINAL", xalign=0)
        self.status.get_style_context().add_class("ok")
        self.blurb = Gtk.Label(label="Live sensors online.", xalign=0)
        self.blurb.set_line_wrap(True)
        root.pack_start(self.status, False, False, 0)
        root.pack_start(self.blurb, False, False, 0)

        grid = Gtk.Grid(column_spacing=10, row_spacing=10, column_homogeneous=True)
        self.cpu_l = self._metric_card("CPU")
        self.mem_l = self._metric_card("RAM")
        self.disk_l = self._metric_card("DISK /")
        self.swap_l = self._metric_card("SWAP")
        grid.attach(self.cpu_l[0], 0, 0, 1, 1)
        grid.attach(self.mem_l[0], 1, 0, 1, 1)
        grid.attach(self.disk_l[0], 0, 1, 1, 1)
        grid.attach(self.swap_l[0], 1, 1, 1, 1)
        root.pack_start(grid, False, False, 0)

        self.load_l = Gtk.Label(label="LOAD: —", xalign=0)
        root.pack_start(self.load_l, False, False, 0)

        iss = Gtk.Label(label="ACTIVE ISSUES", xalign=0)
        iss.get_style_context().add_class("section")
        root.pack_start(iss, False, False, 0)
        self.issues = Gtk.Label(label="None", xalign=0)
        self.issues.set_line_wrap(True)
        root.pack_start(self.issues, False, False, 0)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        opt = Gtk.Button(label="Run Performance Optimize")
        opt.connect("clicked", self.on_optimize)
        heal = Gtk.Button(label="Run Auto-Heal Now")
        heal.connect("clicked", self.on_heal)
        btn_row.pack_start(opt, False, False, 0)
        btn_row.pack_start(heal, False, False, 0)
        root.pack_start(btn_row, False, False, 0)

        loglab = Gtk.Label(label="LOG", xalign=0)
        loglab.get_style_context().add_class("section")
        root.pack_start(loglab, False, False, 0)
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_buf = self.log_view.get_buffer()
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sc.set_vexpand(True)
        sc.add(self.log_view)
        root.pack_start(sc, True, True, 0)

        log("BOSS-Sentinel GTK3 UI starting")
        self.refresh()
        GLib.timeout_add(int(self.settings.get("poll_ms", 2500)), self._tick)
        self.connect("destroy", Gtk.main_quit)
        self.show_all()

    def _metric_card(self, title: str):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.get_style_context().add_class("card")
        t = Gtk.Label(label=title, xalign=0)
        t.get_style_context().add_class("sub")
        v = Gtk.Label(label="—", xalign=0)
        v.get_style_context().add_class("metric")
        b = Gtk.ProgressBar()
        b.set_show_text(False)
        box.pack_start(t, False, False, 0)
        box.pack_start(v, False, False, 0)
        box.pack_start(b, False, False, 0)
        return box, v, b

    def on_autoheal(self, *_args) -> None:
        self.settings["prompt_on_issue"] = bool(self.autoheal.get_active())
        save_settings(self.settings)

    def _tick(self) -> bool:
        self.refresh()
        return True

    def refresh(self) -> None:
        try:
            cpu = read_cpu()
            mem, _, _ = read_mem()
            # swap from meminfo again
            info = {}
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    k, v = line.split(":")
                    info[k] = int(v.strip().split()[0])
            swap_t = info.get("SwapTotal", 0)
            swap = ((swap_t - info.get("SwapFree", 0)) / swap_t * 100.0) if swap_t else 0.0
            disk = read_disk("/")
            score, overall, issues = score_of(cpu, mem, disk, swap)

            for widget, val in (
                (self.cpu_l, cpu),
                (self.mem_l, mem),
                (self.disk_l, disk),
                (self.swap_l, swap),
            ):
                widget[1].set_text(f"{val:.0f}%")
                widget[2].set_fraction(min(1.0, val / 100.0))

            self.load_l.set_text(f"LOAD: {read_load()}   ·   SCORE {score}/100")
            ctx = self.status.get_style_context()
            for c in ("ok", "warn", "crit"):
                ctx.remove_class(c)
            if overall == "crit":
                self.status.set_text("CRITICAL · ACTION NEEDED")
                ctx.add_class("crit")
            elif overall == "warn":
                self.status.set_text("WARNING · WATCH CLOSELY")
                ctx.add_class("warn")
            else:
                self.status.set_text("HEALTHY · SYSTEMS NOMINAL")
                ctx.add_class("ok")

            if issues:
                self.issues.set_text(
                    "\n".join(f"• {n} {v:.0f}% ({s})" for n, s, v in issues)
                )
            else:
                self.issues.set_text("None")

            self.blurb.set_text(
                f"Sensors online · autoheal {'on' if self.settings.get('prompt_on_issue') else 'off'} · GTK3 safe UI"
            )
            self._reload_log()
            self._maybe_prompt(overall, issues, cpu, mem, disk, swap)
            log(f"Snapshot score={score} cpu={cpu:.0f} mem={mem:.0f}")
        except Exception as exc:  # noqa: BLE001
            log(f"refresh error: {exc}")

    def _reload_log(self) -> None:
        if not LOG_FILE.exists():
            return
        text = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
        self.log_buf.set_text("\n".join(text))

    def _maybe_prompt(self, overall, issues, cpu, mem, disk, swap) -> None:
        if not self.settings.get("prompt_on_issue", True):
            return
        if self.prompt_open or self.busy or overall == "ok":
            return
        if time.time() - self.last_prompt < 60:
            return
        self.prompt_open = True
        self.last_prompt = time.time()
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text="System pressure detected",
        )
        dlg.format_secondary_text(
            "Auto-heal and performance optimize now?\n"
            + "\n".join(f"{n} {v:.0f}%" for n, _, v in issues)
        )
        resp = dlg.run()
        dlg.destroy()
        self.prompt_open = False
        if resp == Gtk.ResponseType.YES:
            self.run_heal_and_optimize(issues)

    def on_optimize(self, *_a) -> None:
        self.run_heal_and_optimize([])

    def on_heal(self, *_a) -> None:
        self.run_heal_and_optimize([("CPU", "warn", 0), ("RAM", "warn", 0), ("DISK", "warn", 0)])

    def run_heal_and_optimize(self, issues) -> None:
        if self.busy:
            return
        self.busy = True
        actions = []
        names = {i[0] for i in issues}
        if "RAM" in names or "SWAP" in names or not issues:
            actions.append("drop_caches")
        if "DISK" in names or not issues:
            actions.append("trim_journals")
        if "CPU" in names or not issues:
            actions.append("cpu_performance")
        for extra in ("io_boost", "power_performance"):
            if extra not in actions:
                actions.append(extra)

        lines = []
        for act in actions:
            res = run_helper(act)
            msg = res.get("message", "?")
            ok = res.get("ok", False)
            lines.append(f"{'✓' if ok else '✗'} {act}: {msg}")
            log(f"action {act} → {msg}")

        self.busy = False
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Optimization complete",
        )
        dlg.format_secondary_text("\n".join(lines))
        dlg.run()
        dlg.destroy()
        self._reload_log()


def main() -> int:
    # Soften any residual GL probing under X11
    os.environ.setdefault("GDK_BACKEND", "x11")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    win = MainWindow()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
