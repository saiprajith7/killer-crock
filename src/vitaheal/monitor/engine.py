"""Health engine — aggregates collectors and derives healable issues."""

from __future__ import annotations

import time
from typing import Optional

from vitaheal.monitor.cpu import CpuCollector
from vitaheal.monitor.disk import DiskCollector
from vitaheal.monitor.gpu import GpuCollector
from vitaheal.monitor.memory import MemoryCollector
from vitaheal.monitor.models import (
    HealthSnapshot,
    Issue,
    MetricKind,
    MetricReading,
    Severity,
)
from vitaheal.monitor.network import NetworkCollector
from vitaheal.monitor.process import ProcessCollector
from vitaheal.monitor.temperature import TempCollector


class HealthEngine:
    def __init__(self, simulate: Optional[str] = None) -> None:
        self.cpu = CpuCollector()
        self.memory = MemoryCollector()
        self.disk = DiskCollector()
        self.temp = TempCollector()
        self.network = NetworkCollector()
        self.process = ProcessCollector()
        self.gpu = GpuCollector()
        self.simulate = simulate

    def snapshot(self) -> HealthSnapshot:
        metrics: list[MetricReading] = []
        metrics.extend(self.cpu.read())
        metrics.extend(self.memory.read())
        metrics.extend(self.disk.read())
        metrics.extend(self.temp.read())
        metrics.extend(self.gpu.read())
        metrics.extend(self.network.read())
        metrics.extend(self.process.read())

        if self.simulate:
            metrics = self._apply_simulation(metrics)

        issues = self._derive_issues(metrics)
        overall = Severity.OK
        if any(i.severity == Severity.CRITICAL for i in issues):
            overall = Severity.CRITICAL
        elif any(i.severity == Severity.WARN for i in issues):
            overall = Severity.WARN
        elif any(m.severity == Severity.WARN for m in metrics):
            overall = Severity.WARN

        score = 100
        for m in metrics:
            if m.severity == Severity.WARN:
                score -= 8
            elif m.severity == Severity.CRITICAL:
                score -= 20
        score = max(0, min(100, score))

        return HealthSnapshot(
            timestamp=time.time(),
            metrics=metrics,
            issues=issues,
            overall=overall,
            score=score,
        )

    def _apply_simulation(self, metrics: list[MetricReading]) -> list[MetricReading]:
        kind_map = {
            "cpu": MetricKind.CPU,
            "memory": MetricKind.MEMORY,
            "disk": MetricKind.DISK,
            "temp": MetricKind.TEMP,
            "zombie": MetricKind.ZOMBIE,
            "swap": MetricKind.SWAP,
            "gpu": MetricKind.GPU,
        }
        target = kind_map.get(self.simulate or "")
        if not target:
            return metrics
        # Ensure a GPU metric exists so simulation works on GPU-less machines
        if target == MetricKind.GPU and not any(m.kind == MetricKind.GPU for m in metrics):
            metrics = list(metrics) + [
                MetricReading(
                    kind=MetricKind.GPU,
                    label="GPU",
                    value=0.0,
                    unit="%",
                    severity=Severity.OK,
                    detail="simulated GPU",
                    threshold_warn=85,
                    threshold_crit=95,
                )
            ]
        out: list[MetricReading] = []
        for m in metrics:
            if m.kind == target:
                out.append(
                    MetricReading(
                        kind=m.kind,
                        label=m.label,
                        value=99.0 if m.kind != MetricKind.ZOMBIE else 42.0,
                        unit=m.unit,
                        severity=Severity.CRITICAL,
                        detail=f"[SIMULATED] {m.detail}",
                        threshold_warn=m.threshold_warn,
                        threshold_crit=m.threshold_crit,
                    )
                )
            else:
                out.append(m)
        return out

    def _derive_issues(self, metrics: list[MetricReading]) -> list[Issue]:
        issues: list[Issue] = []
        for m in metrics:
            if m.severity == Severity.OK:
                continue
            issue = self._issue_for(m)
            if issue:
                issues.append(issue)
        return issues

    def _issue_for(self, m: MetricReading) -> Optional[Issue]:
        table = {
            MetricKind.CPU: (
                "CPU overload detected",
                "Processor utilization is critically high. VitaHeal can "
                "renice the heaviest non-critical user processes to ease pressure.",
                "renice_hogs",
                "Throttle CPU hogs",
                False,
            ),
            MetricKind.MEMORY: (
                "Memory pressure critical",
                "Available RAM is nearly exhausted. VitaHeal can drop page "
                "caches and sync dirty buffers to reclaim memory safely.",
                "drop_caches",
                "Drop page caches",
                False,
            ),
            MetricKind.SWAP: (
                "Swap thrashing",
                "Swap usage is elevated. VitaHeal can clear unused swap pages "
                "by cycling swapoff/swapon (requires confirmation).",
                "reset_swap",
                "Reset swap",
                False,
            ),
            MetricKind.DISK: (
                "Disk nearly full",
                f"{m.label} is critically full ({m.value}%). VitaHeal can purge "
                "package caches, journal leftovers, and temp files.",
                "purge_disk",
                "Purge caches & temp",
                False,
            ),
            MetricKind.INODE: (
                "Inode exhaustion",
                f"{m.label} is running out of inodes. VitaHeal can prune "
                "orphaned temp files under /tmp and /var/tmp.",
                "prune_tmp",
                "Prune temp inodes",
                False,
            ),
            MetricKind.TEMP: (
                "Thermal emergency",
                "System temperature is dangerously high. VitaHeal can force "
                "the CPU frequency governor to powersave to cool down.",
                "thermal_cooldown",
                "Force powersave cooling",
                False,
            ),
            MetricKind.GPU: (
                "GPU overload detected",
                "Graphics processor utilization is critically high. VitaHeal can "
                "force a GPU power-save / low-performance profile to cool and free load.",
                "gpu_cooldown",
                "Force GPU powersave",
                False,
            ),
            MetricKind.GPU_MEM: (
                "GPU VRAM exhausted",
                "Video memory is nearly full. VitaHeal can force a GPU powersave "
                "profile and attempt to ease pressure on the graphics stack.",
                "gpu_cooldown",
                "Force GPU powersave",
                False,
            ),
            MetricKind.GPU_TEMP: (
                "GPU thermal emergency",
                "GPU temperature is dangerously high. VitaHeal can switch the GPU "
                "into a low-power profile to cool down.",
                "gpu_cooldown",
                "Force GPU powersave",
                False,
            ),
            MetricKind.ZOMBIE: (
                "Zombie process swarm",
                "Many zombie processes are lingering. VitaHeal can signal "
                "their parent processes (SIGCHLD) to reap them.",
                "reap_zombies",
                "Reap zombie parents",
                False,
            ),
            MetricKind.LOAD: (
                "System load spike",
                "Load average exceeds core capacity. VitaHeal can pause "
                "non-essential background timers briefly.",
                "pause_timers",
                "Pause user timers",
                False,
            ),
        }
        if m.kind not in table:
            return None
        title, desc, action, label, safe = table[m.kind]
        return Issue(
            id=f"{m.kind.value}:{m.label}",
            kind=m.kind,
            title=title,
            description=f"{desc}\n\nReading: {m.value}{m.unit} — {m.detail}",
            severity=m.severity,
            heal_action=action,
            heal_label=label,
            auto_safe=safe,
        )
