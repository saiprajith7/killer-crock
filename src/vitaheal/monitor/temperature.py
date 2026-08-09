"""Thermal sensor collector via sysfs — primary + full sensor list."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from vitaheal.monitor.models import MetricKind, MetricReading, Severity

HWMon = Path("/sys/class/hwmon")
THERMAL = Path("/sys/class/thermal")


@dataclass
class TempSensor:
    name: str
    celsius: float


@dataclass
class TempState:
    sensors: list[TempSensor] = field(default_factory=list)


def _read_temp_millic() -> list[TempSensor]:
    temps: list[TempSensor] = []
    if HWMon.exists():
        for hw in sorted(HWMon.glob("hwmon*")):
            name = (hw / "name").read_text().strip() if (hw / "name").exists() else hw.name
            for tf in sorted(hw.glob("temp*_input")):
                try:
                    millic = int(tf.read_text().strip())
                    label_path = tf.with_name(tf.name.replace("_input", "_label"))
                    label = label_path.read_text().strip() if label_path.exists() else tf.stem
                    temps.append(TempSensor(f"{name} / {label}", millic / 1000.0))
                except (OSError, ValueError):
                    continue
    if not temps and THERMAL.exists():
        for zone in sorted(THERMAL.glob("thermal_zone*")):
            try:
                millic = int((zone / "temp").read_text().strip())
                ztype = (zone / "type").read_text().strip() if (zone / "type").exists() else zone.name
                temps.append(TempSensor(ztype, millic / 1000.0))
            except (OSError, ValueError):
                continue
    return temps


class TempCollector:
    def __init__(self) -> None:
        self.state = TempState()

    def read(self) -> list[MetricReading]:
        temps = _read_temp_millic()
        self.state = TempState(sensors=temps)
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
        ranked = sorted(temps, key=lambda t: t.celsius, reverse=True)
        hottest = ranked[0]
        sev = Severity.OK
        if hottest.celsius >= 95:
            sev = Severity.CRITICAL
        elif hottest.celsius >= 80:
            sev = Severity.WARN
        detail = " · ".join(f"{s.name} {s.celsius:.0f}°C" for s in ranked[:4])
        return [
            MetricReading(
                kind=MetricKind.TEMP,
                label="Temp",
                value=round(hottest.celsius, 1),
                unit="°C",
                severity=sev,
                detail=detail,
                threshold_warn=80,
                threshold_crit=95,
            )
        ]
