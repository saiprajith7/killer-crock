"""CPU utilization, topology (cores/threads), and per-core usage."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from vitaheal.monitor.models import MetricKind, MetricReading, Severity


def _read_cpu_lines() -> list[tuple[str, int, int]]:
    """Return (name, idle, total) for aggregate + each logical CPU."""
    rows: list[tuple[str, int, int]] = []
    for line in Path("/proc/stat").read_text().splitlines():
        if not line.startswith("cpu"):
            break
        parts = line.split()
        name = parts[0]
        vals = [int(x) for x in parts[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        rows.append((name, idle, total))
    return rows


def _topology() -> tuple[int, int, str]:
    """Return (physical_cores, logical_threads, model_name)."""
    cpuinfo = Path("/proc/cpuinfo").read_text()
    model = "CPU"
    physical_ids: set[str] = set()
    core_ids: set[tuple[str, str]] = set()
    processors = 0
    cur_phys = "0"
    for line in cpuinfo.splitlines():
        if line.startswith("model name") or line.startswith("Hardware"):
            model = line.split(":", 1)[1].strip()
        elif line.startswith("processor"):
            processors += 1
        elif line.startswith("physical id"):
            cur_phys = line.split(":", 1)[1].strip()
            physical_ids.add(cur_phys)
        elif line.startswith("core id"):
            core_ids.add((cur_phys, line.split(":", 1)[1].strip()))
    threads = processors or (os.cpu_count() or 1)
    cores = len(core_ids) or len(physical_ids) or threads
    # If topology keys missing (some VMs), cores == threads
    if not core_ids and not physical_ids:
        cores = threads
    return cores, threads, model


@dataclass
class CpuTopology:
    model: str = "CPU"
    physical_cores: int = 1
    logical_threads: int = 1
    per_core: list[float] = field(default_factory=list)
    load1: float = 0.0
    load5: float = 0.0
    load15: float = 0.0


class CpuCollector:
    def __init__(self) -> None:
        self._prev = {name: (idle, total) for name, idle, total in _read_cpu_lines()}
        self.topology = CpuTopology()
        cores, threads, model = _topology()
        self.topology.physical_cores = cores
        self.topology.logical_threads = threads
        self.topology.model = model

    def read(self) -> list[MetricReading]:
        time.sleep(0.05)
        rows = _read_cpu_lines()
        usages: dict[str, float] = {}
        for name, idle, total in rows:
            prev = self._prev.get(name, (idle, total))
            d_idle = idle - prev[0]
            d_total = max(total - prev[1], 1)
            usages[name] = max(0.0, min(100.0, (1.0 - d_idle / d_total) * 100.0))
            self._prev[name] = (idle, total)

        usage = usages.get("cpu", 0.0)
        per_core = [usages[k] for k in sorted(usages) if k.startswith("cpu") and k != "cpu"]
        load1, load5, load15 = os.getloadavg()
        cores, threads, model = _topology()
        self.topology = CpuTopology(
            model=model,
            physical_cores=cores,
            logical_threads=threads,
            per_core=[round(x, 1) for x in per_core],
            load1=load1,
            load5=load5,
            load15=load15,
        )

        load_norm = (load1 / max(threads, 1)) * 100.0
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
                detail=f"{cores} cores · {threads} threads · {model[:48]}",
                threshold_warn=80,
                threshold_crit=95,
            ),
            MetricReading(
                kind=MetricKind.LOAD,
                label="Load",
                value=round(load1, 2),
                unit=f"/{threads}",
                severity=load_sev,
                detail=f"1m={load1:.2f} 5m={load5:.2f} 15m={load15:.2f}",
                threshold_warn=float(threads),
                threshold_crit=float(threads) * 1.5,
            ),
        ]
