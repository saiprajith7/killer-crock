"""CPU utilization, topology (cores/threads), and per-core usage.

Utilization is derived the same way as psutil / GNOME System Monitor:
  busy = user + nice + system + irq + softirq + steal
  idle = idle + iowait
  %%   = busy / (busy + idle) * 100

guest / guest_nice are already included in user / nice and must not be
added again (doing so skews the total).

Samples use a minimum ~1s window (typical for desktop monitors) and a
light EMA so brief spikes do not read far above System Monitor.
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
# EMA: 1.0 = raw only; lower = smoother / closer to System Monitor feel.
_EMA_ALPHA = 0.45


def _idle_total(vals: list[int]) -> tuple[int, int]:
    """Return (idle_all, total) from one /proc/stat cpu* field list."""
    # user nice system idle [iowait irq softirq steal guest guest_nice]
    user = vals[0] if len(vals) > 0 else 0
    nice = vals[1] if len(vals) > 1 else 0
    system = vals[2] if len(vals) > 2 else 0
    idle = vals[3] if len(vals) > 3 else 0
    iowait = vals[4] if len(vals) > 4 else 0
    irq = vals[5] if len(vals) > 5 else 0
    softirq = vals[6] if len(vals) > 6 else 0
    steal = vals[7] if len(vals) > 7 else 0
    # Do NOT add guest / guest_nice — already counted inside user / nice.
    idle_all = idle + iowait
    busy = user + nice + system + irq + softirq + steal
    total = idle_all + busy
    return idle_all, total


def _read_cpu_lines() -> list[tuple[str, int, int]]:
    """Return (name, idle_all, total) for aggregate + each logical CPU."""
    rows: list[tuple[str, int, int]] = []
    for line in Path("/proc/stat").read_text().splitlines():
        if not line.startswith("cpu"):
            break
        parts = line.split()
        name = parts[0]
        vals = [int(x) for x in parts[1:]]
        idle_all, total = _idle_total(vals)
        rows.append((name, idle_all, total))
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
        # Enforce a System-Monitor-like sample window (avoid 50ms spike noise).
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
                    # Clamp rare counter wrap / race leftovers.
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
