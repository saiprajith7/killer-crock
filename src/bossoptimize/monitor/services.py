"""Systemd service listing."""

from __future__ import annotations

import subprocess

from bossoptimize.monitor.models import ServiceInfo


def list_services(limit: int = 400) -> list[ServiceInfo]:
    """Return systemd services (system scope), preferring running ones first."""
    rows: list[ServiceInfo] = []
    for scope in ([], ["--user"]):
        try:
            proc = subprocess.run(
                [
                    "systemctl",
                    *scope,
                    "list-units",
                    "--type=service",
                    "--all",
                    "--no-pager",
                    "--no-legend",
                    "--plain",
                ],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

        for line in proc.stdout.splitlines():
            line = line.strip().lstrip("●").strip()
            if not line:
                continue
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            name, load, active, sub = parts[0], parts[1], parts[2], parts[3]
            desc = parts[4] if len(parts) > 4 else ""
            if not name.endswith(".service"):
                continue
            is_run = active == "active" and sub == "running"
            rows.append(
                ServiceInfo(
                    name=name,
                    load=load,
                    active=active,
                    sub=sub,
                    description=desc,
                    running=is_run,
                )
            )
        if rows:
            break

    # Deduplicate by name
    seen = set()
    uniq: list[ServiceInfo] = []
    for s in rows:
        if s.name in seen:
            continue
        seen.add(s.name)
        uniq.append(s)
    uniq.sort(key=lambda s: (not s.running, s.name.lower()))
    return uniq[:limit]
