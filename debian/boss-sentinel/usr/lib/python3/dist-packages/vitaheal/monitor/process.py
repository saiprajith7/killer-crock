"""Process health: zombie count."""

from __future__ import annotations

from pathlib import Path

from vitaheal.monitor.models import MetricKind, MetricReading, Severity


class ProcessCollector:
    def read(self) -> list[MetricReading]:
        zombies = 0
        try:
            for status in Path("/proc").glob("[0-9]*/status"):
                try:
                    text = status.read_text()
                except OSError:
                    continue
                for line in text.splitlines():
                    if line.startswith("State:"):
                        if "Z (zombie)" in line or line.split()[1] == "Z":
                            zombies += 1
                        break
        except OSError:
            pass

        sev = Severity.OK
        if zombies >= 20:
            sev = Severity.CRITICAL
        elif zombies >= 5:
            sev = Severity.WARN

        return [
            MetricReading(
                kind=MetricKind.ZOMBIE,
                label="Zombies",
                value=float(zombies),
                unit="procs",
                severity=sev,
                detail=f"{zombies} zombie process(es)",
                threshold_warn=5,
                threshold_crit=20,
            )
        ]
