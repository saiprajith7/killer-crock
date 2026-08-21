"""Memory and swap collectors."""

from __future__ import annotations

from pathlib import Path

from vitaheal.monitor.models import MetricKind, MetricReading, Severity


def _meminfo() -> dict[str, int]:
    info: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, raw = line.split(":", 1)
        info[key] = int(raw.strip().split()[0]) * 1024
    return info


class MemoryCollector:
    def read(self) -> list[MetricReading]:
        m = _meminfo()
        total = m.get("MemTotal", 1)
        available = m.get("MemAvailable", m.get("MemFree", 0))
        used = total - available
        pct = (used / total) * 100.0

        swap_total = m.get("SwapTotal", 0)
        swap_free = m.get("SwapFree", 0)
        swap_used = max(0, swap_total - swap_free)
        swap_pct = (swap_used / swap_total * 100.0) if swap_total else 0.0

        mem_sev = Severity.OK
        if pct >= 95:
            mem_sev = Severity.CRITICAL
        elif pct >= 85:
            mem_sev = Severity.WARN

        swap_sev = Severity.OK
        if swap_total and swap_pct >= 80:
            swap_sev = Severity.CRITICAL
        elif swap_total and swap_pct >= 50:
            swap_sev = Severity.WARN

        def _fmt(n: float) -> str:
            size = float(n)
            for unit in ("B", "KB", "MB", "GB", "TB"):
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} PB"

        return [
            MetricReading(
                kind=MetricKind.MEMORY,
                label="Memory",
                value=round(pct, 1),
                unit="%",
                severity=mem_sev,
                detail=f"{_fmt(used)} / {_fmt(total)}",
                threshold_warn=85,
                threshold_crit=95,
            ),
            MetricReading(
                kind=MetricKind.SWAP,
                label="Swap",
                value=round(swap_pct, 1),
                unit="%",
                severity=swap_sev,
                detail=(
                    f"{_fmt(swap_used)} / {_fmt(swap_total)}"
                    if swap_total
                    else "no swap configured"
                ),
                threshold_warn=50,
                threshold_crit=80,
            ),
        ]
