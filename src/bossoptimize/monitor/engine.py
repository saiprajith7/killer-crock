"""Aggregate performance snapshot + optimize plan."""

from __future__ import annotations

import os
import time
from pathlib import Path

from bossoptimize.monitor.disk import list_disks
from bossoptimize.monitor.gpu import read_gpu
from bossoptimize.monitor.models import OptimizeAction, PerformanceSnapshot
from bossoptimize.monitor.packages import list_packages_with_runtime
from bossoptimize.monitor.processes import list_processes
from bossoptimize.monitor.services import list_services

_PROC = Path("/proc")
_prev_cpu: tuple[float, float] | None = None


def _mem() -> tuple[float, float, float, float]:
    text = (_PROC / "meminfo").read_text()
    vals = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            vals[parts[0][:-1]] = float(parts[1])
    total = vals.get("MemTotal", 1.0)
    avail = vals.get("MemAvailable", vals.get("MemFree", 0.0))
    used = max(total - avail, 0.0)
    swap_t = vals.get("SwapTotal", 0.0)
    swap_f = vals.get("SwapFree", 0.0)
    swap_pct = ((swap_t - swap_f) / swap_t * 100.0) if swap_t else 0.0
    return used / total * 100.0, used / 1024 / 1024, total / 1024 / 1024, swap_pct


def _cpu_percent() -> float:
    global _prev_cpu
    line = (_PROC / "stat").read_text().splitlines()[0]
    parts = line.split()
    nums = [float(x) for x in parts[1:8]]
    total = sum(nums)
    idle = nums[3] + (nums[4] if len(nums) > 4 else 0)  # idle + iowait? GNOME counts iowait busy
    # Match GNOME-ish: iowait is busy
    idle_only = nums[3]
    busy = total - idle_only
    if _prev_cpu is None:
        _prev_cpu = (busy, total)
        time.sleep(0.15)
        return _cpu_percent()
    prev_busy, prev_total = _prev_cpu
    d_total = max(total - prev_total, 1.0)
    d_busy = max(busy - prev_busy, 0.0)
    _prev_cpu = (busy, total)
    return d_busy / d_total * 100.0


class OptimizeEngine:
    def snapshot(self) -> PerformanceSnapshot:
        cpu = round(_cpu_percent(), 1)
        mem_pct, mem_used, mem_total, swap_pct = _mem()
        try:
            load1 = os.getloadavg()[0]
        except OSError:
            load1 = 0.0
        threads = os.cpu_count() or 1

        services = list_services()
        processes = list_processes()
        packages, packages_total = list_packages_with_runtime(processes, running_only=False)
        disks, io_r, io_w = list_disks()
        gpu = read_gpu()

        bg = sum(1 for p in processes if p.background)
        fg = sum(1 for p in processes if not p.background)

        return PerformanceSnapshot(
            timestamp=time.time(),
            cpu_percent=cpu,
            mem_percent=round(mem_pct, 1),
            mem_used_gb=round(mem_used, 2),
            mem_total_gb=round(mem_total, 2),
            swap_percent=round(swap_pct, 1),
            load1=round(load1, 2),
            threads=threads,
            services=services,
            processes=processes,
            packages_running=[p for p in packages if p.running],
            packages_total=packages_total,
            disks=disks,
            gpu=gpu,
            io_read_bps=round(io_r, 1),
            io_write_bps=round(io_w, 1),
            background_count=bg,
            foreground_count=fg,
        )

    def build_optimize_plan(self, snap: PerformanceSnapshot | None = None) -> dict:
        snap = snap or self.snapshot()
        actions: list[OptimizeAction] = []

        # Always offer governor + I/O scheduling baseline
        actions.append(
            OptimizeAction(
                id="cpu_performance",
                title="Set CPU governor to performance",
                detail="Allot maximum CPU frequency scaling for active work.",
                impact="high",
            )
        )
        actions.append(
            OptimizeAction(
                id="io_boost",
                title="Prefer responsive I/O scheduling",
                detail="Raise priority for interactive disks and lower background flush pressure.",
                impact="medium",
            )
        )

        # Renice heavy background hogs
        hogs = [
            p
            for p in snap.processes
            if p.background and (p.cpu_percent >= 15.0 or p.mem_percent >= 5.0)
        ][:8]
        if hogs:
            names = ", ".join(f"{p.name}({p.pid})" for p in hogs[:5])
            actions.append(
                OptimizeAction(
                    id="renice_background",
                    title="Lower priority of background CPU/RAM hogs",
                    detail=f"Renice: {names}",
                    impact="high",
                )
            )

        # ionice heavy writers
        writers = sorted(
            [p for p in snap.processes if p.background and p.io_total_bps > 2_000_000],
            key=lambda p: p.io_total_bps,
            reverse=True,
        )[:5]
        if writers:
            names = ", ".join(f"{p.name}({p.pid})" for p in writers)
            actions.append(
                OptimizeAction(
                    id="ionice_background",
                    title="Throttle background disk I/O",
                    detail=f"ionice idle class: {names}",
                    impact="medium",
                )
            )

        # Memory pressure
        if snap.mem_percent >= 80 or snap.swap_percent >= 20:
            actions.append(
                OptimizeAction(
                    id="drop_caches",
                    title="Reclaim reclaimable page caches",
                    detail="Free unused file caches to allot RAM to active apps.",
                    impact="medium",
                )
            )

        # Optional power profile
        actions.append(
            OptimizeAction(
                id="power_performance",
                title="Switch platform profile to performance",
                detail="Use powerprofilesctl performance when available.",
                impact="medium",
            )
        )

        return {
            "summary": (
                f"CPU {snap.cpu_percent}% · RAM {snap.mem_percent}% · "
                f"BG procs {snap.background_count} · services running "
                f"{sum(1 for s in snap.services if s.running)}"
            ),
            "actions": [a.as_dict() for a in actions],
        }
