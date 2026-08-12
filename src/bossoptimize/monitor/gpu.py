"""GPU utilization collector."""

from __future__ import annotations

import subprocess
from pathlib import Path

from bossoptimize.monitor.models import GpuInfo


def read_gpu() -> GpuInfo:
    # NVIDIA
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parts = [p.strip() for p in proc.stdout.splitlines()[0].split(",")]
            if len(parts) >= 4:
                name = parts[0]
                util = float(parts[1])
                used = float(parts[2])
                total = float(parts[3])
                mem_pct = (used / total * 100.0) if total else 0.0
                return GpuInfo(
                    name=name,
                    util_percent=round(util, 1),
                    mem_percent=round(mem_pct, 1),
                    mem_used_mb=round(used, 1),
                    mem_total_mb=round(total, 1),
                    available=True,
                    detail="NVIDIA",
                )
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    # AMD/Intel sysfs busy percent if present
    drm = Path("/sys/class/drm")
    if drm.exists():
        for card in sorted(drm.glob("card[0-9]")):
            busy = card / "device" / "gpu_busy_percent"
            if busy.exists():
                try:
                    util = float(busy.read_text().strip())
                except (OSError, ValueError):
                    util = 0.0
                return GpuInfo(
                    name=card.name,
                    util_percent=round(util, 1),
                    mem_percent=0.0,
                    mem_used_mb=0.0,
                    mem_total_mb=0.0,
                    available=True,
                    detail="DRM sysfs",
                )

    return GpuInfo(
        name="No discrete GPU detected",
        util_percent=0.0,
        mem_percent=0.0,
        mem_used_mb=0.0,
        mem_total_mb=0.0,
        available=False,
        detail="CPU graphics / unavailable",
    )
