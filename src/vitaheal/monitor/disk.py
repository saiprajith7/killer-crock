"""Disk space and inode collectors."""

from __future__ import annotations

import os
from pathlib import Path

from vitaheal.monitor.models import MetricKind, MetricReading, Severity


def _mounts() -> list[str]:
    roots = {"/", "/home", "/var", "/tmp"}
    found: list[str] = []
    try:
        for line in Path("/proc/mounts").read_text().splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            mnt, fstype = parts[1], parts[2]
            if fstype in {"ext4", "ext3", "xfs", "btrfs", "zfs", "f2fs"} and mnt in roots:
                found.append(mnt)
    except OSError:
        pass
    if "/" not in found:
        found.insert(0, "/")
    return found


class DiskCollector:
    def read(self) -> list[MetricReading]:
        readings: list[MetricReading] = []
        for mnt in _mounts():
            try:
                st = os.statvfs(mnt)
            except OSError:
                continue
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            pct = (used / total * 100.0) if total else 0.0

            inodes_total = st.f_files
            inodes_free = st.f_ffree
            inode_pct = (
                ((inodes_total - inodes_free) / inodes_total * 100.0)
                if inodes_total
                else 0.0
            )

            sev = Severity.OK
            if pct >= 95:
                sev = Severity.CRITICAL
            elif pct >= 85:
                sev = Severity.WARN

            inode_sev = Severity.OK
            if inode_pct >= 95:
                inode_sev = Severity.CRITICAL
            elif inode_pct >= 85:
                inode_sev = Severity.WARN

            gb = lambda n: f"{n / (1024**3):.1f} GB"
            readings.append(
                MetricReading(
                    kind=MetricKind.DISK,
                    label=f"Disk {mnt}",
                    value=round(pct, 1),
                    unit="%",
                    severity=sev,
                    detail=f"{gb(used)} / {gb(total)}",
                    threshold_warn=85,
                    threshold_crit=95,
                )
            )
            readings.append(
                MetricReading(
                    kind=MetricKind.INODE,
                    label=f"Inodes {mnt}",
                    value=round(inode_pct, 1),
                    unit="%",
                    severity=inode_sev,
                    detail=f"{inodes_total - inodes_free} / {inodes_total}",
                    threshold_warn=85,
                    threshold_crit=95,
                )
            )
        return readings
