"""Network throughput collector."""

from __future__ import annotations

import time
from pathlib import Path

from vitaheal.monitor.models import MetricKind, MetricReading, Severity


def _netdev() -> dict[str, tuple[int, int]]:
    data: dict[str, tuple[int, int]] = {}
    lines = Path("/proc/net/dev").read_text().splitlines()[2:]
    for line in lines:
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name = name.strip()
        if name == "lo":
            continue
        cols = rest.split()
        rx, tx = int(cols[0]), int(cols[8])
        data[name] = (rx, tx)
    return data


class NetworkCollector:
    def __init__(self) -> None:
        self._prev = _netdev()
        self._prev_ts = time.monotonic()

    def read(self) -> list[MetricReading]:
        now = time.monotonic()
        cur = _netdev()
        dt = max(now - self._prev_ts, 0.001)
        rx_rate = tx_rate = 0.0
        for iface, (rx, tx) in cur.items():
            prx, ptx = self._prev.get(iface, (rx, tx))
            rx_rate += max(0, rx - prx) / dt
            tx_rate += max(0, tx - ptx) / dt
        self._prev = cur
        self._prev_ts = now

        def _fmt(bps: float) -> str:
            for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
                if bps < 1024:
                    return f"{bps:.1f} {unit}"
                bps /= 1024
            return f"{bps:.1f} TB/s"

        total = rx_rate + tx_rate
        # Network is informational; mark warn only at extreme saturation (~1 Gbps)
        sev = Severity.OK
        if total > 100_000_000:
            sev = Severity.WARN

        return [
            MetricReading(
                kind=MetricKind.NETWORK,
                label="Network",
                value=round(total / 1024, 1),
                unit="KB/s",
                severity=sev,
                detail=f"↓ {_fmt(rx_rate)}  ↑ {_fmt(tx_rate)}",
                threshold_warn=100_000,
                threshold_crit=1_000_000,
            )
        ]
