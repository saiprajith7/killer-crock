"""Connectivity checks: Repository, ISOC, Network."""

from __future__ import annotations

import configparser
import socket
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from boss_health.config import csv_list, get_float, load_config
from boss_health.models import CheckResult, CheckStatus


def _tcp_ok(host: str, port: int, timeout: float) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP {host}:{port} reachable"
    except OSError as exc:
        return False, f"TCP {host}:{port} failed: {exc}"


def _http_ok(url: str, timeout: float) -> tuple[bool, str]:
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            if 200 <= int(code) < 500:
                return True, f"HTTP {url} → {code}"
            return False, f"HTTP {url} → {code}"
    except urllib.error.HTTPError as exc:
        # Auth / redirect still means the mirror is reachable.
        if exc.code in {301, 302, 303, 307, 308, 401, 403}:
            return True, f"HTTP {url} reachable ({exc.code})"
        return False, f"HTTP {url} error {exc.code}"
    except Exception as exc:  # noqa: BLE001 — surface any probe failure
        return False, f"HTTP {url} failed: {exc}"


def _apt_uris() -> list[str]:
    uris: list[str] = []
    paths = [Path("/etc/apt/sources.list")]
    d = Path("/etc/apt/sources.list.d")
    if d.is_dir():
        paths.extend(sorted(d.glob("*.list")))
        paths.extend(sorted(d.glob("*.sources")))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # deb / deb-src style
            if line.startswith(("deb ", "deb-src ")):
                parts = line.split()
                if len(parts) >= 2:
                    uri = parts[1]
                    if uri.startswith("http"):
                        uris.append(uri.rstrip("/"))
            # deb822 URIs: field
            if line.lower().startswith("uris:"):
                for uri in line.split(":", 1)[1].split():
                    if uri.startswith("http"):
                        uris.append(uri.rstrip("/"))
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for u in uris:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def check_repository(cfg: configparser.ConfigParser | None = None) -> CheckResult:
    cfg = cfg or load_config()
    timeout = get_float(cfg, "connectivity", "timeout_seconds", 3.0)
    uris = _apt_uris()
    if not uris:
        return CheckResult(
            id="repository",
            category="connectivity",
            label="Repository",
            status=CheckStatus.FAIL,
            summary="No apt repositories configured",
            detail="No entries found in /etc/apt/sources.list or sources.list.d",
        )

    details: list[str] = []
    ok_count = 0
    for uri in uris[:6]:
        parsed = urlparse(uri)
        host = parsed.hostname
        if not host:
            details.append(f"{uri}: invalid host")
            continue
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        # Prefer HTTP probe on the repo root; fall back to TCP.
        probe_url = uri if uri.endswith("/") else uri + "/"
        http_ok, http_msg = _http_ok(probe_url, timeout)
        if http_ok:
            ok_count += 1
            details.append(http_msg)
            continue
        tcp_ok, tcp_msg = _tcp_ok(host, port, timeout)
        if tcp_ok:
            ok_count += 1
            details.append(f"{tcp_msg} (HTTP: {http_msg})")
        else:
            details.append(f"{host}: {http_msg}; {tcp_msg}")

    if ok_count == 0:
        status = CheckStatus.FAIL
        summary = "Repository not connected"
    elif ok_count < len(uris[:6]):
        status = CheckStatus.WARNING
        summary = f"Partial repository reachability ({ok_count}/{min(len(uris), 6)})"
    else:
        status = CheckStatus.PASS
        summary = f"Repository connected ({ok_count} mirror(s))"

    return CheckResult(
        id="repository",
        category="connectivity",
        label="Repository",
        status=status,
        summary=summary,
        detail="\n".join(details),
        value=f"{ok_count}/{min(len(uris), 6)}",
    )


def check_isoc(cfg: configparser.ConfigParser | None = None) -> CheckResult:
    cfg = cfg or load_config()
    timeout = get_float(cfg, "connectivity", "timeout_seconds", 3.0)
    hosts = csv_list(cfg, "connectivity", "isoc_hosts")
    port = int(get_float(cfg, "connectivity", "isoc_port", 443))
    if not hosts:
        return CheckResult(
            id="isoc",
            category="connectivity",
            label="ISOC",
            status=CheckStatus.FAIL,
            summary="No ISOC hosts configured",
            detail="Set isoc_hosts in /etc/boss-health/boss-health.conf",
        )

    details: list[str] = []
    ok = False
    for host in hosts:
        # Try HTTPS then TCP
        https_ok, https_msg = _http_ok(f"https://{host}/", timeout)
        if https_ok:
            ok = True
            details.append(https_msg)
            break
        tcp_ok, tcp_msg = _tcp_ok(host, port, timeout)
        details.append(f"{host}: {https_msg}; {tcp_msg}")
        if tcp_ok:
            ok = True
            break

    if ok:
        return CheckResult(
            id="isoc",
            category="connectivity",
            label="ISOC",
            status=CheckStatus.PASS,
            summary="ISOC connected",
            detail="\n".join(details),
            value=hosts[0],
        )
    return CheckResult(
        id="isoc",
        category="connectivity",
        label="ISOC",
        status=CheckStatus.FAIL,
        summary="ISOC not connected",
        detail="\n".join(details),
        value=", ".join(hosts),
    )


def check_network(cfg: configparser.ConfigParser | None = None) -> CheckResult:
    cfg = cfg or load_config()
    timeout = get_float(cfg, "connectivity", "timeout_seconds", 3.0)
    hosts = csv_list(cfg, "connectivity", "network_hosts")
    port = int(get_float(cfg, "connectivity", "network_port", 53))

    # Default route presence
    has_route = False
    route_detail = "no default route"
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "00000000":
                has_route = True
                route_detail = f"default route via iface {parts[0]}"
                break
    except OSError as exc:
        route_detail = f"route check failed: {exc}"

    details = [route_detail]
    dns_ok = False
    try:
        socket.getaddrinfo("dns.google", 443, type=socket.SOCK_STREAM)
        dns_ok = True
        details.append("DNS resolution OK (dns.google)")
    except OSError as exc:
        details.append(f"DNS resolution failed: {exc}")

    reach_ok = False
    for host in hosts:
        ok, msg = _tcp_ok(host, port, timeout)
        details.append(msg)
        if ok:
            reach_ok = True
            break
        # also try 443 for hostnames
        if not host.replace(".", "").isdigit():
            ok2, msg2 = _tcp_ok(host, 443, timeout)
            details.append(msg2)
            if ok2:
                reach_ok = True
                break

    if has_route and dns_ok and reach_ok:
        status = CheckStatus.PASS
        summary = "Network connected"
    elif has_route and (dns_ok or reach_ok):
        status = CheckStatus.WARNING
        summary = "Network partially available"
    else:
        status = CheckStatus.FAIL
        summary = "Network not connected"

    return CheckResult(
        id="network",
        category="connectivity",
        label="Network",
        status=status,
        summary=summary,
        detail="\n".join(details),
    )


def run_connectivity_checks(cfg: configparser.ConfigParser | None = None) -> list[CheckResult]:
    cfg = cfg or load_config()
    return [
        check_repository(cfg),
        check_isoc(cfg),
        check_network(cfg),
    ]
