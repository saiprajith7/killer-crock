"""Load BOSS Health configuration from /etc or bundled defaults."""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any

# Prefer system config; fall back to packaged sample.
CONFIG_PATHS = (
    Path("/etc/boss-health/boss-health.conf"),
    Path("/usr/share/boss-health/boss-health.conf"),
    Path(__file__).resolve().parents[2] / "data" / "config" / "boss-health.conf",
)

DEFAULTS: dict[str, dict[str, str]] = {
    "connectivity": {
        # ISOC endpoints used by BOSS client sites (override per deployment).
        "isoc_hosts": "isoc.nic.in,isoc.gov.in",
        "isoc_port": "443",
        "network_hosts": "1.1.1.1,8.8.8.8,dns.google",
        "network_port": "53",
        "timeout_seconds": "3",
    },
    "services": {
        "critical": "dbus,NetworkManager,networking,systemd-logind,cron,rsyslog",
        "security": "ssh,sshd,apparmor,fail2ban,clamav-daemon,clamav-freshclam",
    },
    "thresholds": {
        "cpu_warn": "80",
        "cpu_fail": "95",
        "ram_warn": "85",
        "ram_fail": "95",
        "disk_warn": "85",
        "disk_fail": "95",
    },
}


def load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    for section, values in DEFAULTS.items():
        cfg[section] = values
    for path in CONFIG_PATHS:
        if path.is_file():
            cfg.read(path)
            break
    return cfg


def csv_list(cfg: configparser.ConfigParser, section: str, key: str) -> list[str]:
    raw = cfg.get(section, key, fallback="")
    return [p.strip() for p in raw.split(",") if p.strip()]


def get_float(cfg: configparser.ConfigParser, section: str, key: str, default: float) -> float:
    try:
        return float(cfg.get(section, key, fallback=str(default)))
    except (TypeError, ValueError):
        return default


def config_snapshot(cfg: configparser.ConfigParser | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    return {s: dict(cfg.items(s)) for s in cfg.sections()}
