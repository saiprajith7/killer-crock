"""Heal action catalog and privileged helper IPC."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


HELPER = "/usr/libexec/vitaheal/vitaheal-helper"
# Fallback for development / unpackaged runs
DEV_HELPER = str(
    Path(__file__).resolve().parents[3] / "scripts" / "vitaheal-helper"
)


@dataclass
class HealResult:
    ok: bool
    action: str
    message: str
    details: str = ""


def _run_helper(action: str, *args: str) -> HealResult:
    helper = HELPER if Path(HELPER).exists() else DEV_HELPER
    if not Path(helper).exists():
        # In-process fallback for demos without packaging
        return _local_heal(action, *args)

    cmd = ["pkexec", helper, action, *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        # pkexec missing — try direct helper (may fail without privileges)
        try:
            proc = subprocess.run(
                [helper, action, *args],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except OSError as exc:
            return HealResult(False, action, f"Could not launch helper: {exc}")
    except subprocess.TimeoutExpired:
        return HealResult(False, action, "Heal action timed out")

    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {
            "ok": proc.returncode == 0,
            "message": proc.stdout.strip() or proc.stderr.strip() or "unknown",
        }

    return HealResult(
        ok=bool(payload.get("ok", proc.returncode == 0)),
        action=action,
        message=str(payload.get("message", "done")),
        details=str(payload.get("details", proc.stderr.strip())),
    )


def _local_heal(action: str, *args: str) -> HealResult:
    """Best-effort unprivileged / demo heal implementations."""
    handlers: dict[str, Callable[..., HealResult]] = {
        "drop_caches": _local_drop_caches,
        "purge_disk": _local_purge_disk,
        "prune_tmp": _local_prune_tmp,
        "renice_hogs": _local_renice,
        "reap_zombies": _local_reap,
        "thermal_cooldown": _local_thermal,
        "gpu_cooldown": _local_gpu_cooldown,
        "reset_swap": _local_swap,
        "pause_timers": _local_pause_timers,
        "simulate_ok": lambda: HealResult(True, "simulate_ok", "Simulation acknowledged"),
    }
    fn = handlers.get(action)
    if not fn:
        return HealResult(False, action, f"Unknown action: {action}")
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001
        return HealResult(False, action, f"Heal failed: {exc}")


def _local_drop_caches() -> HealResult:
    path = Path("/proc/sys/vm/drop_caches")
    if path.exists() and os.access(path, os.W_OK):
        Path("/proc/sys/vm/drop_caches").write_text("3\n")
        return HealResult(True, "drop_caches", "Page caches dropped")
    # Unprivileged: sync only
    os.sync()
    return HealResult(
        True,
        "drop_caches",
        "Synced dirty buffers (full cache drop needs privileges — install package)",
    )


def _local_purge_disk() -> HealResult:
    freed = 0
    targets = [
        Path.home() / ".cache" / "vitaheal-tmp",
        Path("/tmp") / "vitaheal-scratch",
    ]
    # apt clean requires root; clear only our scratch + journal user scope hint
    for t in targets:
        if t.exists():
            for p in t.rglob("*"):
                if p.is_file():
                    try:
                        freed += p.stat().st_size
                        p.unlink()
                    except OSError:
                        pass
    # Clear pip/user cache leftovers that are safe
    user_tmp = Path(tempfile.gettempdir())
    for pattern in ("vitaheal-*",):
        for p in user_tmp.glob(pattern):
            try:
                if p.is_file():
                    freed += p.stat().st_size
                    p.unlink()
                elif p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass
    mb = freed / (1024 * 1024)
    return HealResult(
        True,
        "purge_disk",
        f"Purged safe temp/cache (~{mb:.1f} MB). Full apt/journal clean needs package install.",
    )


def _local_prune_tmp() -> HealResult:
    removed = 0
    for root in (Path("/tmp"), Path("/var/tmp"), Path(tempfile.gettempdir())):
        if not root.exists():
            continue
        for p in root.glob("vitaheal-*"):
            try:
                if p.is_file():
                    p.unlink()
                    removed += 1
                elif p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                    removed += 1
            except OSError:
                pass
    return HealResult(True, "prune_tmp", f"Pruned {removed} temp entries")


def _local_renice() -> HealResult:
    # Renice own process group as demo; real helper renices system hogs
    try:
        os.nice(5)
        return HealResult(True, "renice_hogs", "Lowered priority of current session (demo mode)")
    except OSError as exc:
        return HealResult(False, "renice_hogs", str(exc))


def _local_reap() -> HealResult:
    # Best effort: wait on any children we own
    reaped = 0
    try:
        while True:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            reaped += 1
    except ChildProcessError:
        pass
    return HealResult(
        True,
        "reap_zombies",
        f"Reaped {reaped} owned children; system-wide reap needs helper privileges",
    )


def _local_thermal() -> HealResult:
    gov = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    if gov.exists() and os.access(gov, os.W_OK):
        for cpu in Path("/sys/devices/system/cpu").glob("cpu[0-9]*"):
            g = cpu / "cpufreq" / "scaling_governor"
            if g.exists():
                try:
                    g.write_text("powersave")
                except OSError:
                    pass
        return HealResult(True, "thermal_cooldown", "Governor set to powersave")
    return HealResult(
        True,
        "thermal_cooldown",
        "Thermal cooldown requires privileges — install VitaHeal package for full heal",
    )


def _local_gpu_cooldown() -> HealResult:
    notes: list[str] = []
    # AMD: try low performance level without root when writable
    drm = Path("/sys/class/drm")
    if drm.exists():
        for card in drm.glob("card[0-9]"):
            if "-" in card.name:
                continue
            level = card / "device" / "power_dpm_force_performance_level"
            if level.exists() and os.access(level, os.W_OK):
                try:
                    level.write_text("low")
                    notes.append(f"{card.name}=low")
                except OSError as exc:
                    notes.append(f"{card.name} failed: {exc}")
    if notes:
        return HealResult(True, "gpu_cooldown", "GPU powersave applied", "; ".join(notes))
    return HealResult(
        True,
        "gpu_cooldown",
        "GPU powersave needs privileges (nvidia-smi / amdgpu) — install package for full heal",
    )


def _local_swap() -> HealResult:
    return HealResult(
        True,
        "reset_swap",
        "Swap reset requires privileges — install VitaHeal package for full heal",
    )


def _local_pause_timers() -> HealResult:
    try:
        subprocess.run(
            ["systemctl", "--user", "list-timers", "--no-pager"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return HealResult(
            True,
            "pause_timers",
            "Inspected user timers (full pause needs package helper)",
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return HealResult(True, "pause_timers", "Timer pause skipped (systemd user not available)")


def perform_heal(action: str) -> HealResult:
    if action == "simulate_ok":
        return HealResult(True, action, "Simulated heal completed")
    return _run_helper(action)


ACTION_LABELS = {
    "drop_caches": "Drop page caches",
    "purge_disk": "Purge caches & temp",
    "prune_tmp": "Prune temp inodes",
    "renice_hogs": "Throttle CPU hogs",
    "reap_zombies": "Reap zombie parents",
    "thermal_cooldown": "Force powersave cooling",
    "gpu_cooldown": "Force GPU powersave",
    "reset_swap": "Reset swap",
    "pause_timers": "Pause user timers",
}
