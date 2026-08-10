"""CPU utilization, topology (cores/threads), and per-core usage.

Aligned with GNOME System Monitor / libgtop Resources view:
  total = user + nice + system + idle + iowait + irq + softirq + steal
  %%CPU = 100 * (1 - idle / total)

iowait is treated as busy (not idle), matching System Monitor.
guest / guest_nice are already inside user / nice — never add them again.

Samples use a ~1s window; light EMA keeps the trace readable without
lagging far behind System Monitor.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from vitaheal.monitor.models import MetricKind, MetricReading, Severity

# Match common desktop monitors (GNOME ~1s updates).
# Override with BOSS_SENTINEL_CPU_SAMPLE (seconds) for tests.
_MIN_SAMPLE_SEC = float(os.environ.get("BOSS_SENTINEL_CPU_SAMPLE", "1.0"))
# High alpha ≈ System Monitor responsiveness (was 0.45 and lagged badly).
_EMA_ALPHA = float(os.environ.get("BOSS_SENTINEL_CPU_EMA", "0.85"))


def _idle_total(vals: list[int]) -> tuple[int, int]:
    """Return (idle, total) using GNOME System Monitor accounting.

    idle = idle field only (iowait counts as busy — same as GSM Resources).
    total excludes guest/guest_nice (already inside user/nice).
    """
    # user nice system idle [iowait irq softirq steal guest guest_nice]
    user = vals[0] if len(vals) > 0 else 0
    nice = vals[1] if len(vals) > 1 else 0
    system = vals[2] if len(vals) > 2 else 0
    idle = vals[3] if len(vals) > 3 else 0
    iowait = vals[4] if len(vals) > 4 else 0
    irq = vals[5] if len(vals) > 5 else 0
    softirq = vals[6] if len(vals) > 6 else 0
    steal = vals[7] if len(vals) > 7 else 0
    total = user + nice + system + idle + iowait + irq + softirq + steal
    return idle, total


def _read_cpu_lines() -> list[tuple[str, int, int]]:
    """Return (name, idle, total) for aggregate + each logical CPU."""
    rows: list[tuple[str, int, int]] = []
    for line in Path("/proc/stat").read_text().splitlines():
        if not line.startswith("cpu"):
            break
        parts = line.split()
        name = parts[0]
        vals = [int(x) for x in parts[1:]]
        idle, total = _idle_total(vals)
        rows.append((name, idle, total))
    return rows


def _topology() -> tuple[int, int, str]:
    """Return (physical_cores, logical_threads, model_name).

    Logical threads = online processors in /proc/cpuinfo (same set System
    Monitor graphs). Physical cores prefer unique (physical_id, core_id).
    """
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
    # Prefer counting online logical CPUs from /proc/stat when topology
    # keys under-count hybrid / partially offlined chips.
    stat_threads = sum(
        1
        for line in Path("/proc/stat").read_text().splitlines()
        if line.startswith("cpu") and line[3:4].isdigit()
    )
    if stat_threads > threads:
        threads = stat_threads
    cores = len(core_ids) or len(physical_ids) or threads
    if not core_ids and not physical_ids:
        cores = threads
    # Never report more physical cores than online threads.
    cores = min(cores, threads)
    return cores, threads, model


def _core_sort_key(name: str) -> tuple[int, str]:
    """Sort cpu0..cpu9..cpu10 numerically, not lexicographically."""
    if name.startswith("cpu") and name[3:].isdigit():
        return (int(name[3:]), name)
    return (10_000, name)


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
        self._last_ts = time.monotonic()
        self._ema: dict[str, float] = {}
        self.topology = CpuTopology()
        cores, threads, model = _topology()
        self.topology.physical_cores = cores
        self.topology.logical_threads = threads
        self.topology.model = model

    def _smooth(self, name: str, raw: float) -> float:
        prev = self._ema.get(name)
        if prev is None:
            self._ema[name] = raw
        else:
            self._ema[name] = (_EMA_ALPHA * raw) + ((1.0 - _EMA_ALPHA) * prev)
        return self._ema[name]

    def read(self) -> list[MetricReading]:
        now = time.monotonic()
        wait = _MIN_SAMPLE_SEC - (now - self._last_ts)
        if wait > 0:
            time.sleep(wait)

        rows = _read_cpu_lines()
        self._last_ts = time.monotonic()
        usages: dict[str, float] = {}
        for name, idle, total in rows:
            prev = self._prev.get(name)
            if prev is None:
                raw = 0.0
            else:
                d_idle = idle - prev[0]
                d_total = total - prev[1]
                if d_total <= 0:
                    raw = self._ema.get(name, 0.0)
                else:
                    d_idle = max(0, min(d_idle, d_total))
                    raw = (1.0 - (d_idle / d_total)) * 100.0
                    raw = max(0.0, min(100.0, raw))
            self._prev[name] = (idle, total)
            usages[name] = self._smooth(name, raw)

        usage = usages.get("cpu", 0.0)
        per_core = [
            usages[k]
            for k in sorted(usages, key=_core_sort_key)
            if k.startswith("cpu") and k != "cpu"
        ]
        # Prefer mean of per-CPU when available (matches how users read GSM).
        if per_core:
            usage = sum(per_core) / len(per_core)

        load1, load5, load15 = os.getloadavg()
        cores, threads, model = _topology()
        # Prefer actual online CPU count from samples.
        if per_core:
            threads = max(threads, len(per_core))
            cores = min(cores, threads)
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
