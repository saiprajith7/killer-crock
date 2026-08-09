"""Thermal sensor collector via sysfs."""

from __future__ import annotations

from pathlib import Path

from vitaheal.monitor.models import MetricKind, MetricReading, Severity

HWMon = Path("/sys/class/hwmon")
THERMAL = Path("/sys/class/thermal")


def _read_temp_millic() -> list[tuple[str, float]]:
    temps: list[tuple[str, float]] = []
    if HWMon.exists():
        for hw in sorted(HWMon.glob("hwmon*")):
            name = (hw / "name").read_text().strip() if (hw / "name").exists() else hw.name
            for tf in sorted(hw.glob("temp*_input")):
                try:
                    millic = int(tf.read_text().strip())
                    label_path = tf.with_name(tf.name.replace("_input", "_label"))
                    label = label_path.read_text().strip() if label_path.exists() else tf.stem
                    temps.append((f"{name}/{label}", millic / 1000.0))
                except (OSError, ValueError):
                    continue
    if not temps and THERMAL.exists():
        for zone in sorted(THERMAL.glob("thermal_zone*")):
            try:
                millic = int((zone / "temp").read_text().strip())
                ztype = (zone / "type").read_text().strip() if (zone / "type").exists() else zone.name
                temps.append((ztype, millic / 1000.0))
            except (OSError, ValueError):
                continue
    return temps


class TempCollector:
    def read(self) -> list[MetricReading]:
        temps = _read_temp_millic()
        if not temps:
            return [
                MetricReading(
                    kind=MetricKind.TEMP,
                    label="Temp",
                    value=0.0,
                    unit="°C",
                    severity=Severity.OK,
                    detail="no sensors exposed",
                    threshold_warn=80,
                    threshold_crit=95,
                )
            ]
        # Prefer CPU package / hottest reading for the primary gauge
        temps.sort(key=lambda t: t[1], reverse=True)
        name, celsius = temps[0]
        sev = Severity.OK
        if celsius >= 95:
            sev = Severity.CRITICAL
        elif celsius >= 80:
            sev = Severity.WARN
        detail = " · ".join(f"{n} {v:.0f}°C" for n, v in temps[:4])
        return [
            MetricReading(
                kind=MetricKind.TEMP,
                label="Temp",
                value=round(celsius, 1),
                unit="°C",
                severity=sev,
                detail=detail,
                threshold_warn=80,
                threshold_crit=95,
            )
        ]
