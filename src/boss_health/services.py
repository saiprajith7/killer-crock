"""Critical and Security services checks."""

from __future__ import annotations

import configparser
import shutil
import subprocess
from pathlib import Path

from boss_health.config import csv_list, load_config
from boss_health.models import CheckResult, CheckStatus


def _systemctl(*args: str) -> tuple[int, str]:
    exe = shutil.which("systemctl")
    if not exe:
        return 127, "systemctl not found"
    try:
        proc = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode, out
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def _unit_active(name: str) -> tuple[bool, str]:
    """Return (active, detail) for a service unit name (with or without .service)."""
    unit = name if name.endswith((".service", ".socket", ".target")) else f"{name}.service"
    code, out = _systemctl("is-active", unit)
    state = (out.splitlines()[0] if out else "unknown").strip()
    if code == 0 and state == "active":
        return True, f"{unit}: active"
    # Not installed / not found is different from failed
    code2, out2 = _systemctl("status", unit, "--no-pager", "-n", "0")
    detail = f"{unit}: {state}"
    if out2:
        detail += f"\n{out2[:400]}"
    return False, detail


def _unit_exists(name: str) -> bool:
    unit = name if name.endswith((".service", ".socket", ".target")) else f"{name}.service"
    code, out = _systemctl("list-unit-files", unit)
    if code != 0:
        # Fallback: unit file on disk
        for base in ("/lib/systemd/system", "/usr/lib/systemd/system", "/etc/systemd/system"):
            if Path(base, unit).is_file():
                return True
        return False
    return unit in out or "enabled" in out or "disabled" in out or "static" in out


def _evaluate_group(
    check_id: str,
    label: str,
    names: list[str],
    *,
    require_all_installed: bool = False,
) -> CheckResult:
    if not names:
        return CheckResult(
            id=check_id,
            category="services",
            label=label,
            status=CheckStatus.WARNING,
            summary=f"No {label.lower()} configured",
            detail="Configure service list in /etc/boss-health/boss-health.conf",
        )

    if shutil.which("systemctl") is None:
        return CheckResult(
            id=check_id,
            category="services",
            label=label,
            status=CheckStatus.UNKNOWN,
            summary="systemd unavailable",
            detail="systemctl not found — cannot verify services",
        )

    details: list[str] = []
    considered = 0
    active = 0
    missing = 0
    failed = 0

    for name in names:
        exists = _unit_exists(name)
        if not exists:
            missing += 1
            details.append(f"{name}: not installed")
            if require_all_installed:
                failed += 1
            continue
        considered += 1
        ok, detail = _unit_active(name)
        details.append(detail)
        if ok:
            active += 1
        else:
            failed += 1

    if considered == 0 and missing == len(names):
        # Nothing from the list is installed — soft warning, not hard fail.
        return CheckResult(
            id=check_id,
            category="services",
            label=label,
            status=CheckStatus.WARNING,
            summary=f"No {label.lower()} packages installed",
            detail="\n".join(details),
            value=f"0/{len(names)} present",
        )

    if failed == 0 and active > 0:
        status = CheckStatus.PASS
        summary = f"{label} OK ({active} active)"
    elif active > 0 and failed > 0:
        status = CheckStatus.WARNING
        summary = f"{label} partial ({active} active, {failed} not active)"
    else:
        status = CheckStatus.FAIL
        summary = f"{label} not ready"

    return CheckResult(
        id=check_id,
        category="services",
        label=label,
        status=status,
        summary=summary,
        detail="\n".join(details),
        value=f"{active}/{considered} active",
    )


def check_critical_services(cfg: configparser.ConfigParser | None = None) -> CheckResult:
    cfg = cfg or load_config()
    names = csv_list(cfg, "services", "critical")
    # Critical: at least the installed ones should be active; missing optional alts OK.
    return _evaluate_group("critical_services", "Critical Services", names)


def check_security_services(cfg: configparser.ConfigParser | None = None) -> CheckResult:
    cfg = cfg or load_config()
    names = csv_list(cfg, "services", "security")
    return _evaluate_group("security_services", "Security Services", names)


def run_service_checks(cfg: configparser.ConfigParser | None = None) -> list[CheckResult]:
    cfg = cfg or load_config()
    return [
        check_critical_services(cfg),
        check_security_services(cfg),
    ]
