"""Track application sessions: open/close times + hardware usage per app."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bossoptimize.monitor.models import ProcessInfo

CONFIG_DIR = Path.home() / ".config" / "boss-optimize"
HISTORY_PATH = CONFIG_DIR / "app-sessions.json"

# Binary / process name → friendly application label
_APP_ALIASES = {
    "firefox": "Firefox",
    "firefox-bin": "Firefox",
    "firefox-esr": "Firefox",
    "chrome": "Google Chrome",
    "google-chrome": "Google Chrome",
    "chromium": "Chromium",
    "chromium-browser": "Chromium",
    "code": "VS Code",
    "code-oss": "VS Code",
    "cursor": "Cursor",
    "nautilus": "Files",
    "dolphin": "Files",
    "thunar": "Files",
    "gnome-terminal": "Terminal",
    "gnome-terminal-server": "Terminal",
    "kgx": "Console",
    "ptyxis": "Terminal",
    "xterm": "Terminal",
    "tilix": "Terminal",
    "libreoffice": "LibreOffice",
    "soffice.bin": "LibreOffice",
    "slack": "Slack",
    "discord": "Discord",
    "telegram-desktop": "Telegram",
    "spotify": "Spotify",
    "vlc": "VLC",
    "gimp": "GIMP",
    "inkscape": "Inkscape",
    "evince": "Document Viewer",
    "eog": "Image Viewer",
    "rhythmbox": "Rhythmbox",
    "totem": "Videos",
    "gedit": "Text Editor",
    "gnome-text-editor": "Text Editor",
    "snap-store": "App Center",
    "software-properties-gtk": "Software & Updates",
    "update-manager": "Update Manager",
    "gnome-control-center": "Settings",
    "gnome-system-monitor": "System Monitor",
    "boss-sentinel": "BOSS-Sentinel",
    "boss-optimize": "BOSS-Optimize",
}

_SKIP = {
    "systemd",
    "kworker",
    "kthreadd",
    "rcu_",
    "migration",
    "idle_inject",
    "cpuhp",
    "watchdog",
    "ksoftirqd",
    "irq/",
    "dbus-daemon",
    "pipewire",
    "wireplumber",
    "pulseaudio",
    "Xorg",
    "Xwayland",
    "gnome-shell",
    "gdm-wayland-session",
    "gdm-x-session",
}


@dataclass
class AppSession:
    app_id: str
    app_name: str
    pids: list[int] = field(default_factory=list)
    open_time: float = 0.0
    close_time: float | None = None
    running: bool = True
    cpu_percent: float = 0.0
    mem_percent: float = 0.0
    mem_rss_mb: float = 0.0
    io_total_bps: float = 0.0
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    gpu_percent: float = 0.0
    background: bool = False
    cmdline: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fmt_ts(ts: float | None) -> str:
    if not ts:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def format_open_close(session: AppSession) -> tuple[str, str]:
    opened = _fmt_ts(session.open_time)
    if session.running:
        closed = "still open"
    else:
        closed = _fmt_ts(session.close_time)
    return opened, closed


def _should_skip(name: str, cmdline: str) -> bool:
    low = f"{name} {cmdline}".lower()
    if name.startswith(("kworker", "kthread", "rcu", "migration", "irq/", "cpuhp")):
        return True
    for s in _SKIP:
        if name == s or name.startswith(s) or f"/{s}" in cmdline:
            return True
    # skip pure helpers / libraries
    if name.endswith(".so") or name.startswith("("):
        return True
    if low.strip() in {"", "[unknown]"}:
        return True
    return False


def classify_app(proc: ProcessInfo) -> tuple[str, str] | None:
    """Return (app_id, display_name) or None if not an application of interest."""
    if _should_skip(proc.name, proc.cmdline):
        return None

    base = proc.name.lower()
    # Extract binary from cmdline
    cmd0 = ""
    if proc.cmdline.strip():
        cmd0 = Path(proc.cmdline.split()[0]).name.lower()

    for key, label in _APP_ALIASES.items():
        if base == key or cmd0 == key or base.startswith(key) or cmd0.startswith(key):
            return key, label
        if f"/{key}" in proc.cmdline.lower() or f" {key}" in f" {proc.cmdline.lower()}":
            return key, label

    # Desktop-ish user apps: skip if clearly a tiny utility with no display intent
    # Keep foreground apps and known GUI-ish names
    if proc.background and proc.cpu_percent < 0.5 and proc.mem_rss_mb < 40:
        # still allow if name looks like a product
        if not re.search(r"[a-z]{3,}", base):
            return None

    # Generic: use process name as app id
    app_id = re.sub(r"[^a-z0-9._+-]+", "-", base).strip("-") or f"pid-{proc.pid}"
    label = proc.name
    return app_id, label


class AppSessionTracker:
    """Watch process snapshots and maintain open/close application sessions."""

    def __init__(self, history_limit: int = 200) -> None:
        self.history_limit = history_limit
        self._active: dict[str, AppSession] = {}
        self._closed: list[AppSession] = []
        self._load()

    def _load(self) -> None:
        if not HISTORY_PATH.exists():
            return
        try:
            data = json.loads(HISTORY_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            return
        for row in data.get("closed", [])[-self.history_limit :]:
            try:
                self._closed.append(
                    AppSession(
                        app_id=row["app_id"],
                        app_name=row["app_name"],
                        pids=list(row.get("pids", [])),
                        open_time=float(row.get("open_time", 0)),
                        close_time=row.get("close_time"),
                        running=False,
                        cpu_percent=float(row.get("cpu_percent", 0)),
                        mem_percent=float(row.get("mem_percent", 0)),
                        mem_rss_mb=float(row.get("mem_rss_mb", 0)),
                        io_total_bps=float(row.get("io_total_bps", 0)),
                        disk_read_bytes=int(row.get("disk_read_bytes", 0)),
                        disk_write_bytes=int(row.get("disk_write_bytes", 0)),
                        gpu_percent=float(row.get("gpu_percent", 0)),
                        background=bool(row.get("background", False)),
                        cmdline=str(row.get("cmdline", "")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue

    def _save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "closed": [s.as_dict() for s in self._closed[-self.history_limit :]],
            "saved_at": time.time(),
        }
        try:
            HISTORY_PATH.write_text(json.dumps(payload, indent=2))
        except OSError:
            pass

    def update(self, processes: list[ProcessInfo]) -> list[AppSession]:
        # Group current processes by app
        groups: dict[str, list[ProcessInfo]] = {}
        labels: dict[str, str] = {}
        for proc in processes:
            classified = classify_app(proc)
            if not classified:
                continue
            app_id, label = classified
            groups.setdefault(app_id, []).append(proc)
            labels[app_id] = label

        now = time.time()
        seen = set(groups.keys())

        # Update / open
        for app_id, procs in groups.items():
            cpu = sum(p.cpu_percent for p in procs)
            mem_pct = sum(p.mem_percent for p in procs)
            mem_mb = sum(p.mem_rss_mb for p in procs)
            io_bps = sum(p.io_total_bps for p in procs)
            r_b = sum(p.read_bytes for p in procs)
            w_b = sum(p.write_bytes for p in procs)
            gpu = max((p.gpu_percent for p in procs), default=0.0)
            pids = sorted(p.pid for p in procs)
            bg = all(p.background for p in procs)
            cmd = procs[0].cmdline

            if app_id in self._active:
                sess = self._active[app_id]
                sess.pids = pids
                sess.cpu_percent = round(cpu, 1)
                sess.mem_percent = round(mem_pct, 2)
                sess.mem_rss_mb = round(mem_mb, 1)
                sess.io_total_bps = round(io_bps, 1)
                sess.disk_read_bytes = r_b
                sess.disk_write_bytes = w_b
                sess.gpu_percent = round(gpu, 1)
                sess.background = bg
                sess.cmdline = cmd
                sess.running = True
                sess.close_time = None
                sess.app_name = labels.get(app_id, sess.app_name)
            else:
                self._active[app_id] = AppSession(
                    app_id=app_id,
                    app_name=labels.get(app_id, app_id),
                    pids=pids,
                    open_time=now,
                    close_time=None,
                    running=True,
                    cpu_percent=round(cpu, 1),
                    mem_percent=round(mem_pct, 2),
                    mem_rss_mb=round(mem_mb, 1),
                    io_total_bps=round(io_bps, 1),
                    disk_read_bytes=r_b,
                    disk_write_bytes=w_b,
                    gpu_percent=round(gpu, 1),
                    background=bg,
                    cmdline=cmd,
                )

        # Close vanished apps
        for app_id in list(self._active.keys()):
            if app_id in seen:
                continue
            sess = self._active.pop(app_id)
            sess.running = False
            sess.close_time = now
            sess.pids = []
            self._closed.append(sess)
            self._save()

        # Trim closed
        if len(self._closed) > self.history_limit:
            self._closed = self._closed[-self.history_limit :]

        # Running first, then recently closed
        running = sorted(
            self._active.values(),
            key=lambda s: (s.cpu_percent + s.mem_percent, s.app_name.lower()),
            reverse=True,
        )
        closed = list(reversed(self._closed[-80:]))
        return running + closed
