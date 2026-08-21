"""Shared readiness check models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    UNKNOWN = "unknown"

    @property
    def symbol(self) -> str:
        return {
            CheckStatus.PASS: "✓",
            CheckStatus.WARNING: "⚠",
            CheckStatus.FAIL: "✗",
            CheckStatus.UNKNOWN: "?",
        }[self]

    @property
    def css_class(self) -> str:
        return {
            CheckStatus.PASS: "status-pass",
            CheckStatus.WARNING: "status-warn",
            CheckStatus.FAIL: "status-fail",
            CheckStatus.UNKNOWN: "status-unknown",
        }[self]


@dataclass
class CheckResult:
    id: str
    category: str  # connectivity | system | services
    label: str
    status: CheckStatus
    summary: str = ""
    detail: str = ""
    value: str = ""  # e.g. "42%"

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class ReadinessReport:
    timestamp: float
    checks: list[CheckResult] = field(default_factory=list)
    overall: CheckStatus = CheckStatus.UNKNOWN
    overall_label: str = "UNKNOWN"

    def checks_in(self, category: str) -> list[CheckResult]:
        return [c for c in self.checks if c.category == category]

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall": self.overall.value,
            "overall_label": self.overall_label,
            "checks": [c.as_dict() for c in self.checks],
        }
