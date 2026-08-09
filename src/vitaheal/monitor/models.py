"""Shared health data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"


class MetricKind(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    TEMP = "temp"
    NETWORK = "network"
    LOAD = "load"
    ZOMBIE = "zombie"
    SWAP = "swap"
    INODE = "inode"


@dataclass
class MetricReading:
    kind: MetricKind
    label: str
    value: float
    unit: str
    severity: Severity
    detail: str = ""
    threshold_warn: float = 0.0
    threshold_crit: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["severity"] = self.severity.value
        return d


@dataclass
class Issue:
    id: str
    kind: MetricKind
    title: str
    description: str
    severity: Severity
    heal_action: str
    heal_label: str
    auto_safe: bool = False

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["severity"] = self.severity.value
        return d


@dataclass
class HealthSnapshot:
    timestamp: float
    metrics: list[MetricReading] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    overall: Severity = Severity.OK
    score: int = 100

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall": self.overall.value,
            "score": self.score,
            "metrics": [m.as_dict() for m in self.metrics],
            "issues": [i.as_dict() for i in self.issues],
        }
