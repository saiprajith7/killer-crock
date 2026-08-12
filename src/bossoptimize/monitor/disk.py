"""Disk / SSD detection and I/O throughput."""

from __future__ import annotations

import os
import time
from pathlib import Path

from bossoptimize.monitor.models import DiskInfo

_PROC = Path("/proc")
_prev_disk: dict[str, tuple[int, int, float]] = {}


def _rotational(dev: str) -> str:
    # nvme0n1p1 -> nvme0n1 ; sda1 -> sda
    base = dev
    for prefix in ("nvme", "mmcblk", "vd", "sd", "hd", "xvd"):
        if base.startswith(prefix):
            # strip partition suffix
            while base and base[-1].isdigit():
                if "nvme" in base or "mmcblk" in base:
                    if "p" in base and base.rfind("p") > 0:
                        base = base[: base.rfind("p")]
                    break
                base = base[:-1]
            break
    path = Path(f"/sys/block/{base}/queue/rotational")
    if "nvme" in base:
        return "NVMe"
    if path.exists():
        try:
            rot = path.read_text().strip()
            return "HDD" if rot == "1" else "SSD"
        except OSError:
            pass
    return "Unknown"


def _parse_mounts() -> list[tuple[str, str, str]]:
    rows = []
    try:
        text = (_PROC / "mounts").read_text()
    except OSError:
        return rows
    interesting = {
        "ext4",
        "ext3",
        "xfs",
        "btrfs",
        "f2fs",
        "zfs",
        "vfat",
        "ntfs",
        "overlay",
        "virtiofs",
        "9p",
        "erofs",
    }
    skip_mnt = ("/snap", "/boot/efi", "/proc", "/sys", "/dev", "/run")
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        dev, mnt, fstype = parts[0], parts[1], parts[2]
        if fstype not in interesting:
            continue
        if not mnt.startswith("/"):
            continue
        if any(mnt == s or mnt.startswith(s + "/") for s in skip_mnt) and mnt != "/":
            continue
        rows.append((dev, mnt, fstype))
    # Always ensure root is represented when mounted
    if not any(r[1] == "/" for r in rows):
        rows.insert(0, ("rootfs", "/", "rootfs"))
    # Prefer unique mounts: /, /home, /var
    prefer = {"/", "/home", "/var", "/tmp"}
    rows.sort(key=lambda r: (0 if r[1] in prefer else 1, r[1]))
    seen = set()
    out = []
    for r in rows:
        if r[1] in seen:
            continue
        seen.add(r[1])
        out.append(r)
    return out[:12]


def _diskstats() -> dict[str, tuple[int, int]]:
    """device -> (sectors_read, sectors_written)."""
    out: dict[str, tuple[int, int]] = {}
    try:
        text = (_PROC / "diskstats").read_text()
    except OSError:
        return out
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        name = parts[2]
        try:
            sectors_r = int(parts[5])
            sectors_w = int(parts[9])
        except ValueError:
            continue
        out[name] = (sectors_r, sectors_w)
    return out


def list_disks() -> tuple[list[DiskInfo], float, float]:
    now = time.time()
    stats = _diskstats()
    disks: list[DiskInfo] = []
    total_r = total_w = 0.0

    for dev, mnt, fstype in _parse_mounts():
        try:
            st = os.statvfs(mnt)
        except OSError:
            continue
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = max(total - free, 0)
        used_pct = (used / total * 100.0) if total else 0.0

        # Match diskstats device
        short = Path(dev).name
        r_bps = w_bps = 0.0
        # try exact and parent disk name
        candidates = [short]
        if short.startswith("nvme") and "p" in short:
            candidates.append(short.rsplit("p", 1)[0])
        while candidates[-1] and candidates[-1][-1].isdigit() and not candidates[-1].startswith("nvme"):
            candidates.append(candidates[-1][:-1])
            break
        for cand in candidates:
            if cand not in stats:
                continue
            sr, sw = stats[cand]
            prev = _prev_disk.get(cand)
            if prev:
                dt = max(now - prev[2], 0.05)
                # sectors * 512 = bytes
                r_bps = max(0.0, (sr - prev[0]) * 512 / dt)
                w_bps = max(0.0, (sw - prev[1]) * 512 / dt)
            _prev_disk[cand] = (sr, sw, now)
            break

        total_r += r_bps
        total_w += w_bps
        kind = _rotational(short)
        disks.append(
            DiskInfo(
                device=dev,
                mount=mnt,
                fstype=fstype,
                total_gb=round(total / (1024**3), 2),
                used_gb=round(used / (1024**3), 2),
                used_percent=round(used_pct, 1),
                kind=kind,
                read_bps=round(r_bps, 1),
                write_bps=round(w_bps, 1),
            )
        )

    return disks, total_r, total_w
