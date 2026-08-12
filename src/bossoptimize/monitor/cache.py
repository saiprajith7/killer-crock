"""Cache inventory — system page cache, disk cache dirs, per-process memory."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from bossoptimize.monitor.models import ProcessInfo

_PROC = Path("/proc")


@dataclass
class CacheEntry:
    name: str
    kind: str  # system / directory / process
    size_mb: float
    detail: str
    pid: int | None = None
    cpu_percent: float = 0.0
    mem_percent: float = 0.0
    io_total_bps: float = 0.0
    gpu_percent: float = 0.0
    clearable: bool = False
    clear_action: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CacheSnapshot:
    ram_cached_mb: float
    ram_buffers_mb: float
    ram_reclaimable_mb: float
    ram_total_mb: float
    ram_used_percent: float
    entries: list[CacheEntry]
    total_clearable_mb: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "ram_cached_mb": self.ram_cached_mb,
            "ram_buffers_mb": self.ram_buffers_mb,
            "ram_reclaimable_mb": self.ram_reclaimable_mb,
            "ram_total_mb": self.ram_total_mb,
            "ram_used_percent": self.ram_used_percent,
            "entries": [e.as_dict() for e in self.entries],
            "total_clearable_mb": self.total_clearable_mb,
        }


def _meminfo() -> dict[str, float]:
    vals: dict[str, float] = {}
    try:
        text = (_PROC / "meminfo").read_text()
    except OSError:
        return vals
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            try:
                vals[parts[0][:-1]] = float(parts[1])  # kB
            except ValueError:
                continue
    return vals


def _dir_size_mb(path: Path, max_files: int = 8000) -> float:
    if not path.exists():
        return 0.0
    total = 0
    n = 0
    try:
        if path.is_file():
            return path.stat().st_size / (1024 * 1024)
        for root, dirs, files in os.walk(path):
            # skip huge / sensitive trees
            dirs[:] = [d for d in dirs if d not in {".git", "proc", "sys"}]
            for name in files:
                fp = Path(root) / name
                try:
                    total += fp.stat().st_size
                except OSError:
                    continue
                n += 1
                if n >= max_files:
                    return total / (1024 * 1024)
    except OSError:
        return total / (1024 * 1024)
    return total / (1024 * 1024)


def collect_cache(processes: list[ProcessInfo] | None = None) -> CacheSnapshot:
    mem = _meminfo()
    cached_kb = mem.get("Cached", 0.0)
    buffers_kb = mem.get("Buffers", 0.0)
    reclaim_kb = mem.get("SReclaimable", 0.0)
    total_kb = mem.get("MemTotal", 1.0)
    avail_kb = mem.get("MemAvailable", mem.get("MemFree", 0.0))
    used_pct = max(total_kb - avail_kb, 0.0) / total_kb * 100.0 if total_kb else 0.0

    entries: list[CacheEntry] = []

    # System RAM caches
    entries.append(
        CacheEntry(
            name="Page cache (Cached)",
            kind="system",
            size_mb=round(cached_kb / 1024, 1),
            detail="File data kept in RAM for speed — safe to reclaim",
            clearable=True,
            clear_action="drop_caches",
        )
    )
    entries.append(
        CacheEntry(
            name="Block buffers",
            kind="system",
            size_mb=round(buffers_kb / 1024, 1),
            detail="Block device buffers in RAM",
            clearable=True,
            clear_action="drop_caches",
        )
    )
    entries.append(
        CacheEntry(
            name="Slab reclaimable",
            kind="system",
            size_mb=round(reclaim_kb / 1024, 1),
            detail="Kernel slab objects that can be reclaimed",
            clearable=True,
            clear_action="drop_caches",
        )
    )

    # Directory caches
    home = Path.home()
    dir_targets = [
        (home / ".cache", "User ~/.cache", "clear_user_cache"),
        (Path("/var/cache/apt/archives"), "APT package cache", "clear_apt_cache"),
        (Path("/tmp"), "Temporary files (/tmp)", "clear_tmp_scratch"),
        (Path("/var/tmp"), "Temporary files (/var/tmp)", "clear_tmp_scratch"),
        (home / ".cache" / "mozilla", "Firefox / Mozilla cache", "clear_user_cache"),
        (home / ".cache" / "google-chrome", "Chrome cache", "clear_user_cache"),
        (home / ".cache" / "chromium", "Chromium cache", "clear_user_cache"),
        (home / ".cache" / "thumbnails", "Thumbnail cache", "clear_user_cache"),
    ]
    seen_paths: set[str] = set()
    for path, label, action in dir_targets:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        size = _dir_size_mb(path) if path.exists() else 0.0
        if size <= 0.05 and not path.exists():
            continue
        entries.append(
            CacheEntry(
                name=label,
                kind="directory",
                size_mb=round(size, 1),
                detail=str(path),
                clearable=size > 0.1,
                clear_action=action,
            )
        )

    # Processes with largest RAM (often hold mapped/cached file pages)
    procs = processes or []
    top = sorted(procs, key=lambda p: p.mem_rss_mb, reverse=True)[:40]
    for p in top:
        if p.mem_rss_mb < 30:
            continue
        entries.append(
            CacheEntry(
                name=f"{p.name} memory footprint",
                kind="process",
                size_mb=round(p.mem_rss_mb, 1),
                detail=p.cmdline[:120] or p.name,
                pid=p.pid,
                cpu_percent=p.cpu_percent,
                mem_percent=p.mem_percent,
                io_total_bps=p.io_total_bps,
                gpu_percent=p.gpu_percent,
                clearable=False,
                clear_action="",
            )
        )

    clearable = sum(e.size_mb for e in entries if e.clearable and e.kind in {"system", "directory"})
    # Avoid double-counting all system rows as fully additive for display estimate
    sys_clear = (cached_kb + buffers_kb + reclaim_kb) / 1024
    dir_clear = sum(e.size_mb for e in entries if e.clearable and e.kind == "directory")
    total_clearable = round(sys_clear + dir_clear, 1)

    return CacheSnapshot(
        ram_cached_mb=round(cached_kb / 1024, 1),
        ram_buffers_mb=round(buffers_kb / 1024, 1),
        ram_reclaimable_mb=round(reclaim_kb / 1024, 1),
        ram_total_mb=round(total_kb / 1024, 1),
        ram_used_percent=round(used_pct, 1),
        entries=entries,
        total_clearable_mb=total_clearable,
    )
