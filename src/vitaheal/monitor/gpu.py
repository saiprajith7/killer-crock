"""GPU utilization / VRAM / temperature collectors.

Supports:
  - NVIDIA via nvidia-smi
  - AMD via sysfs (amdgpu)
  - Intel via sysfs (i915 / Xe) when available
Gracefully reports "no GPU" when none are detected.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from vitaheal.monitor.models import MetricKind, MetricReading, Severity


@dataclass
class GpuInfo:
    vendor: str
    name: str
    util: float  # percent
    mem_used_mb: float
    mem_total_mb: float
    temp_c: Optional[float] = None
    power_w: Optional[float] = None


def _sev_pct(pct: float, warn: float = 85.0, crit: float = 95.0) -> Severity:
    if pct >= crit:
        return Severity.CRITICAL
    if pct >= warn:
        return Severity.WARN
    return Severity.OK


def _sev_temp(c: float) -> Severity:
    if c >= 95:
        return Severity.CRITICAL
    if c >= 85:
        return Severity.WARN
    return Severity.OK


def _nvidia() -> list[GpuInfo]:
    if not shutil.which("nvidia-smi"):
        return []
    query = (
        "name,utilization.gpu,memory.used,memory.total,"
        "temperature.gpu,power.draw"
    )
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                f"--query-gpu={query}",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []

    gpus: list[GpuInfo] = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            name = parts[0]
            util = float(parts[1])
            mem_used = float(parts[2])
            mem_total = float(parts[3])
            temp = float(parts[4]) if parts[4] not in {"[N/A]", "N/A", ""} else None
            power = None
            if len(parts) > 5 and parts[5] not in {"[N/A]", "N/A", ""}:
                power = float(parts[5])
        except ValueError:
            continue
        gpus.append(
            GpuInfo("nvidia", name, util, mem_used, mem_total, temp, power)
        )
    return gpus


def _read_float(path: Path) -> Optional[float]:
    try:
        return float(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _amd_sysfs() -> list[GpuInfo]:
    gpus: list[GpuInfo] = []
    drm = Path("/sys/class/drm")
    if not drm.exists():
        return []
    for card in sorted(drm.glob("card[0-9]")):
        # Skip render nodes like card0-DP-1
        if "-" in card.name:
            continue
        device = card / "device"
        vendor_id = (device / "vendor").read_text().strip() if (device / "vendor").exists() else ""
        # AMD PCI vendor 0x1002
        if vendor_id.lower() not in {"0x1002", "0x1002\n".strip()}:
            # Also accept if amdgpu hwmon exists under device
            if not any(device.glob("hwmon/hwmon*/temp1_input")):
                if not (device / "gpu_busy_percent").exists():
                    continue

        name = "AMD GPU"
        uevent = device / "uevent"
        if uevent.exists():
            text = uevent.read_text()
            m = re.search(r"DRIVER=(\w+)", text)
            if m:
                name = f"AMD ({m.group(1)})"
            m2 = re.search(r"PCI_SLOT_NAME=([^\n]+)", text)
            if m2:
                name = f"{name} {m2.group(1)}"

        util = _read_float(device / "gpu_busy_percent")
        if util is None:
            # Some kernels expose busy via debugfs only — treat missing as 0 if card exists
            util = 0.0

        mem_used = mem_total = 0.0
        # VRAM: mem_info_vram_used / mem_info_vram_total (bytes)
        used_b = _read_float(device / "mem_info_vram_used")
        total_b = _read_float(device / "mem_info_vram_total")
        if used_b is not None and total_b is not None and total_b > 0:
            mem_used = used_b / (1024 * 1024)
            mem_total = total_b / (1024 * 1024)

        temp = None
        for hw in device.glob("hwmon/hwmon*"):
            t = _read_float(hw / "temp1_input")
            if t is not None:
                temp = t / 1000.0
                break

        power = None
        for hw in device.glob("hwmon/hwmon*"):
            # Prefer average power
            for pname in ("power1_average", "power1_input"):
                p = _read_float(hw / pname)
                if p is not None:
                    power = p / 1_000_000.0  # microwatts → watts
                    break
            if power is not None:
                break

        gpus.append(GpuInfo("amd", name, util, mem_used, mem_total, temp, power))
    return gpus


def _intel_sysfs() -> list[GpuInfo]:
    gpus: list[GpuInfo] = []
    drm = Path("/sys/class/drm")
    if not drm.exists():
        return []
    for card in sorted(drm.glob("card[0-9]")):
        if "-" in card.name:
            continue
        device = card / "device"
        vendor_id = ""
        try:
            vendor_id = (device / "vendor").read_text().strip().lower()
        except OSError:
            continue
        # Intel PCI vendor 0x8086
        if vendor_id != "0x8086":
            continue
        name = "Intel GPU"
        uevent = device / "uevent"
        if uevent.exists():
            m = re.search(r"DRIVER=(\w+)", uevent.read_text())
            if m:
                name = f"Intel ({m.group(1)})"

        # Intel rarely exposes busy % in sysfs; gt_act_freq_mhz as activity hint
        util = 0.0
        act = _read_float(device / "gt_act_freq_mhz")
        maxf = _read_float(device / "gt_max_freq_mhz") or _read_float(device / "gt_RP0_freq_mhz")
        if act is not None and maxf and maxf > 0:
            util = min(100.0, (act / maxf) * 100.0)

        temp = None
        for hw in Path("/sys/class/hwmon").glob("hwmon*"):
            try:
                hname = (hw / "name").read_text().strip()
            except OSError:
                continue
            if hname in {"i915", "xe"}:
                t = _read_float(hw / "temp1_input")
                if t is not None:
                    temp = t / 1000.0
                    break

        gpus.append(GpuInfo("intel", name, util, 0.0, 0.0, temp, None))
    return gpus


def detect_gpus() -> list[GpuInfo]:
    gpus = _nvidia()
    if gpus:
        return gpus
    gpus = _amd_sysfs()
    if gpus:
        return gpus
    return _intel_sysfs()


class GpuCollector:
    def __init__(self) -> None:
        self.gpus: list[GpuInfo] = []

    def read(self) -> list[MetricReading]:
        gpus = detect_gpus()
        self.gpus = gpus
        if not gpus:
            return [
                MetricReading(
                    kind=MetricKind.GPU,
                    label="GPU",
                    value=0.0,
                    unit="%",
                    severity=Severity.OK,
                    detail="no GPU detected (nvidia-smi / amdgpu / intel)",
                    threshold_warn=85,
                    threshold_crit=95,
                )
            ]

        readings: list[MetricReading] = []
        for i, g in enumerate(gpus):
            suffix = "" if len(gpus) == 1 else f" {i}"
            detail_parts = [g.name, g.vendor.upper()]
            if g.temp_c is not None:
                detail_parts.append(f"{g.temp_c:.0f}°C")
            if g.power_w is not None:
                detail_parts.append(f"{g.power_w:.0f}W")
            if g.mem_total_mb > 0:
                detail_parts.append(
                    f"VRAM {g.mem_used_mb:.0f}/{g.mem_total_mb:.0f} MB"
                )

            readings.append(
                MetricReading(
                    kind=MetricKind.GPU,
                    label=f"GPU{suffix}",
                    value=round(g.util, 1),
                    unit="%",
                    severity=_sev_pct(g.util),
                    detail=" · ".join(detail_parts),
                    threshold_warn=85,
                    threshold_crit=95,
                )
            )

            if g.mem_total_mb > 0:
                mem_pct = (g.mem_used_mb / g.mem_total_mb) * 100.0
                readings.append(
                    MetricReading(
                        kind=MetricKind.GPU_MEM,
                        label=f"VRAM{suffix}",
                        value=round(mem_pct, 1),
                        unit="%",
                        severity=_sev_pct(mem_pct, warn=90, crit=98),
                        detail=f"{g.mem_used_mb:.0f}/{g.mem_total_mb:.0f} MB · {g.name}",
                        threshold_warn=90,
                        threshold_crit=98,
                    )
                )

            if g.temp_c is not None:
                readings.append(
                    MetricReading(
                        kind=MetricKind.GPU_TEMP,
                        label=f"GPU temp{suffix}",
                        value=round(g.temp_c, 1),
                        unit="°C",
                        severity=_sev_temp(g.temp_c),
                        detail=g.name,
                        threshold_warn=85,
                        threshold_crit=95,
                    )
                )
        return readings
