"""Shared data models for BOSS-Optimize."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ServiceInfo:
    name: str
    load: str
    active: str
    sub: str
    description: str
    running: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessInfo:
    pid: int
    user: str
    name: str
    cmdline: str
    cpu_percent: float
    mem_percent: float
    mem_rss_mb: float
    read_bytes: int
    write_bytes: int
    io_total_bps: float
    gpu_percent: float
    state: str
    background: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PackageInfo:
    name: str
    version: str
    status: str
    running: bool
    background: bool
    pids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiskInfo:
    device: str
    mount: str
    fstype: str
    total_gb: float
    used_gb: float
    used_percent: float
    kind: str  # HDD / SSD / NVMe / Unknown
    read_bps: float
    write_bps: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GpuInfo:
    name: str
    util_percent: float
    mem_percent: float
    mem_used_mb: float
    mem_total_mb: float
    available: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizeAction:
    id: str
    title: str
    detail: str
    impact: str  # low / medium / high

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceSnapshot:
    timestamp: float
    cpu_percent: float
    mem_percent: float
    mem_used_gb: float
    mem_total_gb: float
    swap_percent: float
    load1: float
    threads: int
    services: list[ServiceInfo] = field(default_factory=list)
    processes: list[ProcessInfo] = field(default_factory=list)
    packages_running: list[PackageInfo] = field(default_factory=list)
    packages_total: int = 0
    disks: list[DiskInfo] = field(default_factory=list)
    gpu: GpuInfo | None = None
    io_read_bps: float = 0.0
    io_write_bps: float = 0.0
    background_count: int = 0
    foreground_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": self.cpu_percent,
            "mem_percent": self.mem_percent,
            "mem_used_gb": self.mem_used_gb,
            "mem_total_gb": self.mem_total_gb,
            "swap_percent": self.swap_percent,
            "load1": self.load1,
            "threads": self.threads,
            "services": [s.as_dict() for s in self.services],
            "processes": [p.as_dict() for p in self.processes],
            "packages_running": [p.as_dict() for p in self.packages_running],
            "packages_total": self.packages_total,
            "disks": [d.as_dict() for d in self.disks],
            "gpu": self.gpu.as_dict() if self.gpu else None,
            "io_read_bps": self.io_read_bps,
            "io_write_bps": self.io_write_bps,
            "background_count": self.background_count,
            "foreground_count": self.foreground_count,
        }
