"""Optimize action runner (pkexec helper IPC)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

HELPER = "/usr/libexec/boss-optimize/boss-optimize-helper"
DEV_HELPER = str(Path(__file__).resolve().parents[3] / "scripts" / "boss-optimize-helper")


@dataclass
class OptimizeResult:
    ok: bool
    action: str
    message: str
    details: str = ""


def perform_optimize(action: str, *args: str, timeout: int = 120) -> OptimizeResult:
    helper = HELPER if Path(HELPER).exists() else DEV_HELPER
    if not Path(helper).exists():
        return OptimizeResult(False, action, f"Helper missing: {helper}")

    cmd = ["pkexec", helper, action, *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        try:
            proc = subprocess.run([helper, action, *args], capture_output=True, text=True, timeout=timeout, check=False)
        except OSError as exc:
            return OptimizeResult(False, action, f"Could not launch helper: {exc}")
    except subprocess.TimeoutExpired:
        return OptimizeResult(False, action, "Optimization timed out")

    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {
            "ok": proc.returncode == 0,
            "message": proc.stdout.strip() or proc.stderr.strip() or "unknown",
        }
    return OptimizeResult(
        ok=bool(payload.get("ok", proc.returncode == 0)),
        action=action,
        message=str(payload.get("message", "done")),
        details=str(payload.get("details", proc.stderr.strip())),
    )


def apply_plan(action_ids: list[str], renice_pids: list[int] | None = None, ionice_pids: list[int] | None = None) -> list[OptimizeResult]:
    results: list[OptimizeResult] = []
    for aid in action_ids:
        if aid == "renice_background" and renice_pids:
            results.append(perform_optimize("renice_background", *[str(p) for p in renice_pids[:12]]))
        elif aid == "ionice_background" and ionice_pids:
            results.append(perform_optimize("ionice_background", *[str(p) for p in ionice_pids[:12]]))
        else:
            results.append(perform_optimize(aid))
    return results
