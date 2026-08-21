"""System readiness orchestrator.

Reuses the existing BOSS-Sentinel (vitaheal) HealthEngine for CPU, RAM,
Disk, and overall system health. Adds Connectivity and Services checks.
"""

from __future__ import annotations

import time
from typing import Optional

from boss_health.config import load_config
from boss_health.connectivity import run_connectivity_checks
from boss_health.models import CheckResult, CheckStatus, ReadinessReport
from boss_health.services import run_service_checks

# Existing sentinel — do not duplicate CPU/RAM collectors.
from vitaheal.monitor.engine import HealthEngine
from vitaheal.monitor.models import HealthSnapshot, MetricKind, Severity


def _sev_to_status(sev: Severity) -> CheckStatus:
    if sev == Severity.OK:
        return CheckStatus.PASS
    if sev == Severity.WARN:
        return CheckStatus.WARNING
    return CheckStatus.FAIL


def _metric(snap: HealthSnapshot, kind: MetricKind):
    for m in snap.metrics:
        if m.kind == kind:
            return m
    return None


def _worst(*statuses: CheckStatus) -> CheckStatus:
    order = {
        CheckStatus.PASS: 0,
        CheckStatus.UNKNOWN: 1,
        CheckStatus.WARNING: 2,
        CheckStatus.FAIL: 3,
    }
    return max(statuses, key=lambda s: order.get(s, 0))


def system_health_from_sentinel(
    engine: Optional[HealthEngine] = None,
    *,
    simulate: Optional[str] = None,
) -> list[CheckResult]:
    """Build CPU / RAM / Disk / Overall checks from the existing sentinel engine."""
    engine = engine or HealthEngine(simulate=simulate)
    snap = engine.snapshot()

    results: list[CheckResult] = []

    cpu = _metric(snap, MetricKind.CPU)
    if cpu:
        results.append(
            CheckResult(
                id="cpu",
                category="system",
                label="CPU",
                status=_sev_to_status(cpu.severity),
                summary=f"CPU {cpu.value}{cpu.unit}",
                detail=cpu.detail or f"threshold warn={cpu.threshold_warn} crit={cpu.threshold_crit}",
                value=f"{cpu.value}{cpu.unit}",
            )
        )
    else:
        results.append(
            CheckResult(
                id="cpu",
                category="system",
                label="CPU",
                status=CheckStatus.UNKNOWN,
                summary="CPU reading unavailable",
                detail="Sentinel CpuCollector returned no CPU metric",
            )
        )

    mem = _metric(snap, MetricKind.MEMORY)
    if mem:
        results.append(
            CheckResult(
                id="ram",
                category="system",
                label="RAM",
                status=_sev_to_status(mem.severity),
                summary=f"RAM {mem.value}{mem.unit}",
                detail=mem.detail or f"threshold warn={mem.threshold_warn} crit={mem.threshold_crit}",
                value=f"{mem.value}{mem.unit}",
            )
        )
    else:
        results.append(
            CheckResult(
                id="ram",
                category="system",
                label="RAM",
                status=CheckStatus.UNKNOWN,
                summary="RAM reading unavailable",
                detail="Sentinel MemoryCollector returned no memory metric",
            )
        )

    disk = _metric(snap, MetricKind.DISK)
    if disk:
        results.append(
            CheckResult(
                id="disk",
                category="system",
                label="Disk",
                status=_sev_to_status(disk.severity),
                summary=f"Disk {disk.label} {disk.value}{disk.unit}",
                detail=disk.detail or f"threshold warn={disk.threshold_warn} crit={disk.threshold_crit}",
                value=f"{disk.value}{disk.unit}",
            )
        )
    else:
        results.append(
            CheckResult(
                id="disk",
                category="system",
                label="Disk",
                status=CheckStatus.UNKNOWN,
                summary="Disk reading unavailable",
                detail="Sentinel DiskCollector returned no disk metric",
            )
        )

    # Overall System Health — same score/overall as sentinel HealthEngine
    overall_status = _sev_to_status(snap.overall)
    results.append(
        CheckResult(
            id="overall_system",
            category="system",
            label="Overall System Health",
            status=overall_status,
            summary=f"Sentinel score {snap.score}/100 · {snap.overall.value}",
            detail=(
                f"Derived from BOSS-Sentinel HealthEngine. "
                f"Issues: {len(snap.issues)}. Score={snap.score}."
            ),
            value=f"{snap.score}/100",
        )
    )
    return results


def aggregate_overall(checks: list[CheckResult]) -> tuple[CheckStatus, str]:
    statuses = [c.status for c in checks]
    worst = _worst(*statuses) if statuses else CheckStatus.UNKNOWN
    if worst == CheckStatus.PASS:
        return CheckStatus.PASS, "SYSTEM READY"
    if worst == CheckStatus.WARNING or worst == CheckStatus.UNKNOWN:
        return CheckStatus.WARNING, "ACTION REQUIRED"
    return CheckStatus.FAIL, "SYSTEM NOT READY"


def run_all_checks(*, simulate: Optional[str] = None) -> ReadinessReport:
    """Run the full V1 readiness suite and return a report."""
    cfg = load_config()
    checks: list[CheckResult] = []
    checks.extend(run_connectivity_checks(cfg))
    checks.extend(system_health_from_sentinel(simulate=simulate))
    checks.extend(run_service_checks(cfg))
    overall, label = aggregate_overall(checks)
    return ReadinessReport(
        timestamp=time.time(),
        checks=checks,
        overall=overall,
        overall_label=label,
    )
