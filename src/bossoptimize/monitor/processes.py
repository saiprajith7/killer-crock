"""Process collector — CPU, RAM, I/O, GPU hints, background detection."""

from __future__ import annotations

import os
import time
from pathlib import Path

from bossoptimize.monitor.models import ProcessInfo

_PROC = Path("/proc")
_prev_cpu: dict[int, tuple[float, float]] = {}
_prev_io: dict[int, tuple[int, int, float]] = {}
_prev_total_jiffies: float | None = None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")
    except OSError:
        return ""


def _total_jiffies() -> float:
    line = _read_text(_PROC / "stat").splitlines()[0] if (_PROC / "stat").exists() else ""
    parts = line.split()
    if len(parts) < 5:
        return 0.0
    # user nice system idle ...
    vals = [float(x) for x in parts[1:8]]
    return sum(vals)


def _uid_to_name(uid: int) -> str:
    try:
        import pwd

        return pwd.getpwuid(uid).pw_name
    except Exception:  # noqa: BLE001
        return str(uid)


def _parse_status(pid: int) -> tuple[str, int, str, int]:
    """Return name, uid, state, rss_kb."""
    text = _read_text(_PROC / str(pid) / "status")
    name, uid, state, rss = f"pid-{pid}", 0, "?", 0
    for line in text.splitlines():
        if line.startswith("Name:"):
            name = line.split(None, 1)[1].strip()
        elif line.startswith("Uid:"):
            uid = int(line.split()[1])
        elif line.startswith("State:"):
            state = line.split()[1]
        elif line.startswith("VmRSS:"):
            rss = int(line.split()[1])
    return name, uid, state, rss


def _cmdline(pid: int) -> str:
    raw = _read_text(_PROC / str(pid) / "cmdline")
    return raw.replace("\x00", " ").strip() or f"[{pid}]"


def _proc_cpu_jiffies(pid: int) -> float:
    stat = _read_text(_PROC / str(pid) / "stat")
    if not stat:
        return 0.0
    # After comm in parens — find last )
    try:
        rparen = stat.rfind(")")
        fields = stat[rparen + 2 :].split()
        utime = float(fields[11])
        stime = float(fields[12])
        return utime + stime
    except (IndexError, ValueError):
        return 0.0


def _proc_io(pid: int) -> tuple[int, int]:
    text = _read_text(_PROC / str(pid) / "io")
    r = w = 0
    for line in text.splitlines():
        if line.startswith("read_bytes:"):
            r = int(line.split()[1])
        elif line.startswith("write_bytes:"):
            w = int(line.split()[1])
    return r, w


def _is_background(pid: int, uid: int, name: str, cmdline: str) -> bool:
    """Heuristic: user services/daemons without a controlling TTY, or system daemons."""
    try:
        tty = os.readlink(f"/proc/{pid}/fd/0")
        has_tty = tty.startswith("/dev/tty") or tty.startswith("/dev/pts")
    except OSError:
        has_tty = False

    low = f"{name} {cmdline}".lower()
    daemonish = any(
        k in low
        for k in (
            "daemon",
            "systemd",
            "pipewire",
            "pulse",
            "dbus",
            "gvfs",
            "tracker",
            "snapd",
            "cupsd",
            "nginx",
            "apache",
            "docker",
            "containerd",
            "cron",
            "udevd",
        )
    )
    if uid == 0 and not has_tty:
        return True
    if daemonish and not has_tty:
        return True
    if not has_tty and name.endswith("d"):
        return True
    return not has_tty and uid != os.getuid()


def _gpu_by_pid() -> dict[int, float]:
    """Best-effort NVIDIA per-process GPU util via nvidia-smi."""
    import subprocess

    out: dict[int, float] = {}
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_gpu_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return out
    for line in proc.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
            mem = float(parts[1])
        except ValueError:
            continue
        # Memory used as a rough activity signal (0-100 capped later by engine)
        out[pid] = max(out.get(pid, 0.0), min(100.0, mem / 16.0))
    return out


def list_processes(limit: int = 250) -> list[ProcessInfo]:
    global _prev_total_jiffies

    now = time.time()
    total_now = _total_jiffies()
    total_delta = 0.0
    if _prev_total_jiffies is not None:
        total_delta = max(total_now - _prev_total_jiffies, 1.0)
    _prev_total_jiffies = total_now

    gpu_map = _gpu_by_pid()
    hz = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", "SC_CLK_TCK")) if hasattr(os, "sysconf") else 100
    try:
        hz = float(os.sysconf("SC_CLK_TCK"))
    except (ValueError, OSError, AttributeError):
        hz = 100.0

    meminfo = _read_text(_PROC / "meminfo")
    mem_total_kb = 0
    for line in meminfo.splitlines():
        if line.startswith("MemTotal:"):
            mem_total_kb = int(line.split()[1])
            break

    rows: list[ProcessInfo] = []
    for entry in _PROC.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            name, uid, state, rss_kb = _parse_status(pid)
            cmdline = _cmdline(pid)
            cpu_j = _proc_cpu_jiffies(pid)
            r_b, w_b = _proc_io(pid)
        except Exception:  # noqa: BLE001
            continue

        cpu_pct = 0.0
        prev = _prev_cpu.get(pid)
        if prev and total_delta > 0:
            cpu_pct = max(0.0, (cpu_j - prev[0]) / total_delta * 100.0)
        _prev_cpu[pid] = (cpu_j, now)

        io_bps = 0.0
        prev_io = _prev_io.get(pid)
        if prev_io:
            dt = max(now - prev_io[2], 0.05)
            io_bps = max(0.0, ((r_b - prev_io[0]) + (w_b - prev_io[1])) / dt)
        _prev_io[pid] = (r_b, w_b, now)

        mem_pct = (rss_kb / mem_total_kb * 100.0) if mem_total_kb else 0.0
        user = _uid_to_name(uid)
        bg = _is_background(pid, uid, name, cmdline)

        rows.append(
            ProcessInfo(
                pid=pid,
                user=user,
                name=name,
                cmdline=cmdline[:180],
                cpu_percent=round(cpu_pct, 1),
                mem_percent=round(mem_pct, 2),
                mem_rss_mb=round(rss_kb / 1024.0, 1),
                read_bytes=r_b,
                write_bytes=w_b,
                io_total_bps=round(io_bps, 1),
                gpu_percent=round(gpu_map.get(pid, 0.0), 1),
                state=state,
                background=bg,
            )
        )

    # Drop stale cache entries
    live = {p.pid for p in rows}
    for cache in (_prev_cpu, _prev_io):
        for dead in [k for k in cache if k not in live]:
            del cache[dead]

    rows.sort(key=lambda p: (p.cpu_percent + p.mem_percent * 0.5), reverse=True)
    return rows[:limit]
