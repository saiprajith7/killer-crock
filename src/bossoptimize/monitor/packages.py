"""Installed packages + running / background status."""

from __future__ import annotations

import subprocess
from pathlib import Path

from bossoptimize.monitor.models import PackageInfo, ProcessInfo


def _dpkg_packages(limit: int = 8000) -> list[tuple[str, str, str]]:
    try:
        proc = subprocess.run(
            ["dpkg-query", "-W", "-f=${Package}\\t${Version}\\t${Status}\\n"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    rows: list[tuple[str, str, str]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name, ver, status = parts[0], parts[1], parts[2]
        if "installed" not in status:
            continue
        rows.append((name, ver, status))
        if len(rows) >= limit:
            break
    return rows


def _exec_to_package_hints(cmdline: str, name: str) -> set[str]:
    hints: set[str] = set()
    base = Path(cmdline.split()[0]).name if cmdline.strip() else name
    if base:
        hints.add(base.lower())
        hints.add(base.lower().replace("_", "-"))
    # Drop common prefixes
    for prefix in ("gnome-", "xdg-", "gsd-", "ibus-"):
        if base.startswith(prefix):
            hints.add(base[len(prefix) :].lower())
    return hints


def list_packages_with_runtime(
    processes: list[ProcessInfo],
    *,
    running_only: bool = False,
    limit: int = 500,
) -> tuple[list[PackageInfo], int]:
    """
    Map processes onto installed packages (best-effort by binary name).
    Returns (interesting package rows, total installed count).
    """
    installed = _dpkg_packages()
    total = len(installed)
    by_name = {n: (v, s) for n, v, s in installed}

    # Aggregate process activity by package-ish key
    activity: dict[str, dict] = {}
    for proc in processes:
        hints = _exec_to_package_hints(proc.cmdline, proc.name)
        matched = None
        for h in hints:
            if h in by_name:
                matched = h
                break
            # fuzzy: package provides similarly named binary
            for pkg in by_name:
                if pkg == h or pkg.endswith(f"-{h}") or pkg.startswith(f"{h}-"):
                    matched = pkg
                    break
            if matched:
                break
        if not matched:
            # Synthetic row for running unknown binaries
            matched = proc.name.lower()
            if matched not in by_name:
                by_name[matched] = ("(runtime)", "running only")
        slot = activity.setdefault(
            matched,
            {"pids": [], "background": True, "cpu": 0.0, "mem": 0.0},
        )
        slot["pids"].append(proc.pid)
        slot["cpu"] += proc.cpu_percent
        slot["mem"] += proc.mem_percent
        if not proc.background:
            slot["background"] = False

    rows: list[PackageInfo] = []
    for name, meta in activity.items():
        ver, status = by_name.get(name, ("?", "?"))
        rows.append(
            PackageInfo(
                name=name,
                version=ver,
                status=status,
                running=True,
                background=bool(meta["background"]),
                pids=list(meta["pids"]),
            )
        )

    if not running_only:
        # Add a sample of installed-but-not-running packages for the Packages tab
        running_names = {r.name for r in rows}
        extras = 0
        for name, ver, status in installed:
            if name in running_names:
                continue
            rows.append(
                PackageInfo(
                    name=name,
                    version=ver,
                    status=status,
                    running=False,
                    background=False,
                    pids=[],
                )
            )
            extras += 1
            if extras >= max(50, limit // 2):
                break

    rows.sort(key=lambda p: (not p.running, p.background, p.name.lower()))
    return rows[:limit], total
