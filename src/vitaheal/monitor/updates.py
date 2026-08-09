"""Lightweight apt update / upgrade inspection via system sources.

Designed to stay cheap:
  - Never polls apt on the health refresh timer
  - Reads /etc/apt/sources.list(+.d) for display
  - Lists upgradable packages with `apt-get -s upgrade` (simulation)
  - Full `apt-get update` / `upgrade` go through the privileged helper
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


SOURCES_LIST = Path("/etc/apt/sources.list")
SOURCES_DIR = Path("/etc/apt/sources.list.d")


@dataclass
class AptSource:
    file: str
    line: str
    enabled: bool = True


@dataclass
class UpgradablePackage:
    name: str
    current: str
    candidate: str


@dataclass
class UpdateStatus:
    sources: list[AptSource] = field(default_factory=list)
    packages: list[UpgradablePackage] = field(default_factory=list)
    last_check: float = 0.0
    last_error: str = ""
    checking: bool = False

    @property
    def count(self) -> int:
        return len(self.packages)


def read_sources() -> list[AptSource]:
    """Parse apt sources from sources.list and sources.list.d (read-only)."""
    out: list[AptSource] = []
    files: list[Path] = []
    if SOURCES_LIST.exists():
        files.append(SOURCES_LIST)
    if SOURCES_DIR.exists():
        files.extend(sorted(SOURCES_DIR.glob("*.list")))
        files.extend(sorted(SOURCES_DIR.glob("*.sources")))

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                # keep commented mirror lines as disabled sources (useful context)
                body = line.lstrip("#").strip()
                if body.startswith(("deb ", "deb-src ", "Types:")):
                    out.append(AptSource(path.name, body, enabled=False))
                continue
            if line.startswith(("deb ", "deb-src ", "Types:", "URIs:", "Suites:")):
                out.append(AptSource(path.name, line, enabled=True))
    return out


def _parse_simulate_upgrade(text: str) -> list[UpgradablePackage]:
    """Parse `apt-get -s upgrade` Inst/Conf lines for package versions."""
    pkgs: dict[str, UpgradablePackage] = {}
    # Example: Inst foo [1.0] (1.1 Debian:12.1 [amd64])
    inst_re = re.compile(
        r"^Inst\s+(\S+)\s+(?:\[([^\]]*)\]\s+)?\(([^ )]+)"
    )
    for line in text.splitlines():
        m = inst_re.match(line.strip())
        if not m:
            continue
        name, cur, cand = m.group(1), m.group(2) or "?", m.group(3)
        pkgs[name] = UpgradablePackage(name=name, current=cur, candidate=cand)
    return sorted(pkgs.values(), key=lambda p: p.name.lower())


def list_upgradable(refresh_index: bool = False) -> UpdateStatus:
    """Return upgradable packages. Optionally refresh apt lists first (needs root)."""
    status = UpdateStatus(sources=read_sources(), last_check=time.time())
    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "LANG": "C"}

    if refresh_index:
        try:
            subprocess.run(
                ["apt-get", "update", "-qq"],
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            status.last_error = f"apt-get update failed: {exc}"
            return status

    try:
        proc = subprocess.run(
            ["apt-get", "-s", "-o", "Debug::NoLocking=1", "upgrade"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,
        )
    except FileNotFoundError:
        status.last_error = "apt-get not found"
        return status
    except subprocess.TimeoutExpired:
        status.last_error = "apt-get simulate timed out"
        return status

    if proc.returncode != 0 and not proc.stdout:
        status.last_error = (proc.stderr or proc.stdout or "apt-get -s failed").strip()[:300]
        return status

    status.packages = _parse_simulate_upgrade(proc.stdout)
    if not status.packages and proc.stderr and "lock" in proc.stderr.lower():
        status.last_error = "apt lock busy — try again in a moment"
    return status


def summarize_packages(packages: list[UpgradablePackage], limit: int = 12) -> str:
    if not packages:
        return "System is up to date against current apt indexes."
    names = ", ".join(p.name for p in packages[:limit])
    more = "" if len(packages) <= limit else f" (+{len(packages) - limit} more)"
    return f"{len(packages)} package(s): {names}{more}"
