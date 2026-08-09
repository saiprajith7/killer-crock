"""CPU utilization and load average collectors."""

from __future__ import annotations

import os
import time
from pathlib import Path

from vitaheal.monitor.models import MetricKind, MetricReading, Severity


def _read_proc_stat() -> tuple[int, int]:
    line = Path("/proc/stat").read_text().splitlines()[0]
    parts = [int(x) for x in line.split()[1:]]
    idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
    total = sum(parts)
    return idle, total


class CpuCollector:
    def __init__(self) -> None:
        self._prev = _read_proc_stat()
        self._prev_ts = time.monotonic()

    def read(self) -> list[MetricReading]:
        time.sleep(0.05)
        idle, total = _read_proc_stat()
        d_idle = idle - self._prev[0]
        d_total = max(total - self._prev[1], 1)
        self._prev = (idle, total)
        usage = max(0.0, min(100.0, (1.0 - d_idle / d_total) * 100.0))

        load1, load5, load15 = os.getloadavg()
        ncpu = os.cpu_count() or 1
        load_norm = (load1 / ncpu) * 100.0

        cpu_sev = Severity.OK
        if usage >= 95:
            cpu_sev = Severity.CRITICAL
        elif usage >= 80:
            cpu_sev = Severity.WARN

        load_sev = Severity.OK
        if load_norm >= 150:
            load_sev = Severity.CRITICAL
        elif load_norm >= 100:
            load_sev = Severity.WARN

        return [
            MetricReading(
                kind=MetricKind.CPU,
                label="CPU",
                value=round(usage, 1),
                unit="%",
                severity=cpu_sev,
                detail=f"{ncpu} cores online",
                threshold_warn=80,
                threshold_crit=95,
            ),
            MetricReading(
                kind=MetricKind.LOAD,
                label="Load",
                value=round(load1, 2),
                unit=f"/{ncpu}",
                severity=load_sev,
                detail=f"1m={load1:.2f} 5m={load5:.2f} 15m={load15:.2f}",
                threshold_warn=ncpu,
                threshold_crit=ncpu * 1.5,
            ),
        ]
