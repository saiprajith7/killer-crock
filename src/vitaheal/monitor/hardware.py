"""Hardware inventory + per-component health scores (incl. USB)."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from vitaheal.monitor.models import HealthSnapshot, MetricKind, Severity

# Below this health %, advise the user to replace the component.
REPLACE_THRESHOLD = 45.0

USB_SYS = Path("/sys/bus/usb/devices")
NET_SYS = Path("/sys/class/net")
BLOCK_SYS = Path("/sys/class/block")
DMI = Path("/sys/class/dmi/id")


@dataclass
class HardwareComponent:
    """One physical/logical hardware element with a health percentage."""

    id: str
    category: str  # cpu, memory, disk, gpu, network, usb, board, thermal
    name: str
    health: float  # 0–100
    detail: str = ""
    advice: str = ""
    replace: bool = False
    severity: Severity = Severity.OK
    meta: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(errors="ignore").strip()
    except OSError:
        return default


def _metric(snap: HealthSnapshot, kind: MetricKind):
    for m in snap.metrics:
        if m.kind == kind:
            return m
    return None


def _score_from_pressure(pressure_pct: float, weight: float = 0.85) -> float:
    """Map utilization/fill pressure to remaining health."""
    return _clamp(100.0 - pressure_pct * weight)


def _score_from_temp(celsius: float, warn: float = 75.0, crit: float = 90.0) -> float:
    if celsius <= 0:
        return 100.0
    if celsius >= crit:
        return 20.0
    if celsius >= warn:
        # Linear 70→45 between warn and crit-ish, then down
        span = max(crit - warn, 1.0)
        return _clamp(70.0 - ((celsius - warn) / span) * 40.0)
    # Cool → healthy
    return _clamp(100.0 - max(0.0, celsius - 40.0) * 0.6)


def _finalize(comp: HardwareComponent) -> HardwareComponent:
    h = _clamp(comp.health)
    comp.health = round(h, 1)
    if h < REPLACE_THRESHOLD:
        comp.replace = True
        comp.severity = Severity.CRITICAL
        comp.advice = (
            f"Health is {comp.health:.0f}% (below {REPLACE_THRESHOLD:.0f}%). "
            f"Replace this hardware component: {comp.name}."
        )
    elif h < 65:
        comp.replace = False
        comp.severity = Severity.WARN
        comp.advice = "Health is declining — monitor closely and plan maintenance."
    else:
        comp.replace = False
        comp.severity = Severity.OK
        comp.advice = "Component health is acceptable."
    return comp


def _board_components() -> list[HardwareComponent]:
    product = _read_text(DMI / "product_name", "Unknown system")
    vendor = _read_text(DMI / "sys_vendor", "")
    board = _read_text(DMI / "board_name", "")
    bios = _read_text(DMI / "bios_version", "")
    name = product if product else "System board"
    detail_parts = [p for p in (vendor, board, f"BIOS {bios}" if bios else "") if p]
    # Board itself has no live stress — report healthy if DMI readable.
    health = 92.0 if product or board else 55.0
    return [
        _finalize(
            HardwareComponent(
                id="board-system",
                category="board",
                name=name,
                health=health,
                detail=" · ".join(detail_parts) or "DMI identity",
                meta={"vendor": vendor, "board": board},
            )
        )
    ]


def _cpu_component(snap: HealthSnapshot, model: str, cores: int, threads: int) -> HardwareComponent:
    cpu = _metric(snap, MetricKind.CPU)
    temp = _metric(snap, MetricKind.TEMP)
    util = cpu.value if cpu else 0.0
    tscore = _score_from_temp(temp.value) if temp else 100.0
    uscore = _score_from_pressure(util, 0.55)
    health = min(tscore, uscore)
    detail = f"{cores} cores · {threads} threads"
    if temp:
        detail += f" · {temp.value:.0f}°C"
    if cpu:
        detail += f" · load {util:.0f}%"
    return _finalize(
        HardwareComponent(
            id="cpu-0",
            category="cpu",
            name=model or (cpu.detail if cpu else "CPU"),
            health=health,
            detail=detail,
        )
    )


def _memory_component(snap: HealthSnapshot) -> HardwareComponent:
    mem = _metric(snap, MetricKind.MEMORY)
    swap = _metric(snap, MetricKind.SWAP)
    used = mem.value if mem else 0.0
    health = _score_from_pressure(used, 0.9)
    if swap and swap.value >= 80:
        health = min(health, 40.0)
    elif swap and swap.value >= 50:
        health = min(health, 60.0)
    detail = mem.detail if mem else "RAM"
    if swap and swap.value > 0:
        detail += f" · swap {swap.value:.0f}%"
    return _finalize(
        HardwareComponent(
            id="memory-0",
            category="memory",
            name="System memory (RAM)",
            health=health,
            detail=detail,
        )
    )


def _disk_components(snap: HealthSnapshot) -> list[HardwareComponent]:
    out: list[HardwareComponent] = []
    for m in snap.metrics:
        if m.kind != MetricKind.DISK:
            continue
        health = _score_from_pressure(m.value, 0.95)
        # Extremely full disks → replace/expand advice via threshold
        out.append(
            _finalize(
                HardwareComponent(
                    id=f"disk-{m.label}",
                    category="disk",
                    name=f"Storage · {m.label}",
                    health=health,
                    detail=f"{m.value:.0f}% used · {m.detail}",
                )
            )
        )
    if not out:
        # Fallback: list block devices
        for entry in sorted(BLOCK_SYS.iterdir()) if BLOCK_SYS.exists() else []:
            name = entry.name
            if name.startswith(("loop", "ram", "dm-", "zram")):
                continue
            if any(name.startswith(p) and name != p for p in ("sd", "vd", "nvme", "mmcblk")):
                # skip partitions like sda1 — keep whole disks only roughly
                if name[-1].isdigit() and not name.startswith("nvme"):
                    continue
                if "p" in name and name.startswith("nvme") and name[-1].isdigit():
                    continue
            size = _read_text(entry / "size")
            detail = f"/dev/{name}"
            if size.isdigit():
                gb = int(size) * 512 / (1024**3)
                detail += f" · {gb:.1f} GB"
            out.append(
                _finalize(
                    HardwareComponent(
                        id=f"block-{name}",
                        category="disk",
                        name=f"Block device · {name}",
                        health=88.0,
                        detail=detail,
                    )
                )
            )
    return out


def _gpu_component(snap: HealthSnapshot, gpu_name: str = "GPU") -> Optional[HardwareComponent]:
    gpu = _metric(snap, MetricKind.GPU)
    if not gpu:
        return None
    gtemp = _metric(snap, MetricKind.GPU_TEMP)
    gmem = _metric(snap, MetricKind.GPU_MEM)
    uscore = _score_from_pressure(gpu.value, 0.55)
    tscore = _score_from_temp(gtemp.value, warn=80.0, crit=95.0) if gtemp else 100.0
    mscore = _score_from_pressure(gmem.value, 0.7) if gmem else 100.0
    health = min(uscore, tscore, mscore)
    detail = gpu.detail
    if gtemp:
        detail += f" · {gtemp.value:.0f}°C"
    return _finalize(
        HardwareComponent(
            id="gpu-0",
            category="gpu",
            name=gpu_name or "Graphics",
            health=health,
            detail=detail,
        )
    )


def _network_components() -> list[HardwareComponent]:
    out: list[HardwareComponent] = []
    if not NET_SYS.exists():
        return out
    virtual_prefixes = ("docker", "veth", "br-", "virbr", "tun", "tap", "wg", "vbox", "vmnet")
    for entry in sorted(NET_SYS.iterdir()):
        name = entry.name
        if name == "lo":
            continue
        oper = _read_text(entry / "operstate", "unknown")
        carrier = _read_text(entry / "carrier", "")
        speed = _read_text(entry / "speed", "")
        virtual = name.startswith(virtual_prefixes) or name.startswith("veth")
        if oper == "up" or carrier == "1":
            health = 95.0
            detail = "link up"
        elif oper == "down":
            # Don't scare users into replacing unused virtual bridges.
            health = 72.0 if virtual else 42.0
            detail = "link down" + (" (virtual)" if virtual else "")
        else:
            health = 70.0
            detail = f"state {oper}"
        if speed and speed not in {"-1", ""}:
            detail += f" · {speed} Mb/s"
        out.append(
            _finalize(
                HardwareComponent(
                    id=f"net-{name}",
                    category="network",
                    name=f"Network · {name}",
                    health=health,
                    detail=detail,
                    meta={"iface": name, "operstate": oper},
                )
            )
        )
    return out


def _usb_components() -> list[HardwareComponent]:
    """Enumerate USB devices from sysfs (skips root hubs when possible)."""
    out: list[HardwareComponent] = []
    if not USB_SYS.exists():
        return out

    seen: set[str] = set()
    for entry in sorted(USB_SYS.iterdir()):
        # Real devices look like 1-2, 1-1.3 — skip usb1 bus roots & endpoints
        name = entry.name
        if ":" in name:
            continue
        if name.startswith("usb") and name[3:].isdigit():
            continue
        if not (entry / "idVendor").exists():
            continue
        vid = _read_text(entry / "idVendor")
        pid = _read_text(entry / "idProduct")
        key = f"{vid}:{pid}:{name}"
        if key in seen:
            continue
        seen.add(key)

        manufacturer = _read_text(entry / "manufacturer")
        product = _read_text(entry / "product")
        serial = _read_text(entry / "serial")
        speed = _read_text(entry / "speed")
        removable = _read_text(entry / "removable")

        label = product or manufacturer or f"USB {vid}:{pid}"
        if manufacturer and product and manufacturer not in product:
            label = f"{manufacturer} · {product}"

        # Healthy if device enumerates with ids; soft-warn unknown/odd states.
        health = 96.0
        if not vid or not pid:
            health = 50.0
        if removable == "unknown":
            health = min(health, 90.0)

        detail_bits = [f"{vid}:{pid}", name]
        if speed:
            detail_bits.append(f"{speed} Mb/s")
        if serial:
            detail_bits.append(f"SN {serial[:24]}")
        out.append(
            _finalize(
                HardwareComponent(
                    id=f"usb-{name}",
                    category="usb",
                    name=f"USB · {label}",
                    health=health,
                    detail=" · ".join(detail_bits),
                    meta={
                        "vendor": vid,
                        "product": pid,
                        "path": name,
                        "removable": removable,
                    },
                )
            )
        )
    return out


def _thermal_component(snap: HealthSnapshot) -> Optional[HardwareComponent]:
    temp = _metric(snap, MetricKind.TEMP)
    if not temp:
        return None
    health = _score_from_temp(temp.value)
    return _finalize(
        HardwareComponent(
            id="thermal-package",
            category="thermal",
            name="Thermal package",
            health=health,
            detail=f"{temp.value:.0f}°C · {temp.detail}",
        )
    )


class HardwareCollector:
    """Build a live hardware health inventory from a snapshot + sysfs."""

    def inventory(
        self,
        snap: HealthSnapshot,
        *,
        cpu_model: str = "CPU",
        cpu_cores: int = 1,
        cpu_threads: int = 1,
        gpu_name: str = "GPU",
    ) -> list[HardwareComponent]:
        comps: list[HardwareComponent] = []
        comps.extend(_board_components())
        comps.append(_cpu_component(snap, cpu_model, cpu_cores, cpu_threads))
        comps.append(_memory_component(snap))
        comps.extend(_disk_components(snap))
        gpu = _gpu_component(snap, gpu_name)
        if gpu:
            comps.append(gpu)
        therm = _thermal_component(snap)
        if therm:
            comps.append(therm)
        comps.extend(_network_components())
        comps.extend(_usb_components())
        return comps

    @staticmethod
    def summary(components: list[HardwareComponent]) -> dict[str, Any]:
        if not components:
            return {
                "count": 0,
                "avg_health": 0.0,
                "replace_count": 0,
                "worst": None,
            }
        avg = sum(c.health for c in components) / len(components)
        replace = [c for c in components if c.replace]
        worst = min(components, key=lambda c: c.health)
        return {
            "count": len(components),
            "avg_health": round(avg, 1),
            "replace_count": len(replace),
            "worst": worst.name if worst else None,
            "worst_health": worst.health if worst else 0.0,
        }
