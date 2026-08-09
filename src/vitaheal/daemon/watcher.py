"""Headless background watcher — emits desktop notifications for critical issues.

When run under a graphical session it can open the VitaHeal GUI heal prompt
via the desktop app; otherwise it logs to journal.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from vitaheal.monitor.engine import HealthEngine
from vitaheal.monitor.models import Severity

LOG = logging.getLogger("vitaheal.daemon")
STATE = Path.home() / ".cache" / "vitaheal" / "notified.ids"


def _notify(title: str, body: str) -> None:
    try:
        import subprocess

        subprocess.run(
            [
                "notify-send",
                "--app-name=VitaHeal",
                "--urgency=critical",
                "--icon=vitaheal",
                title,
                body + "\nOpen VitaHeal and choose Yes/No to heal.",
            ],
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, OSError):
        LOG.warning("notify-send unavailable: %s — %s", title, body)


def _load_seen() -> set[str]:
    if not STATE.exists():
        return set()
    try:
        return set(STATE.read_text().splitlines())
    except OSError:
        return set()


def _save_seen(seen: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("\n".join(sorted(seen)[-50:]))


def run_loop(interval: int = 15, simulate: str | None = None) -> int:
    engine = HealthEngine(simulate=simulate)
    seen = _load_seen()
    LOG.info("VitaHeal daemon started (interval=%ss)", interval)
    while True:
        snap = engine.snapshot()
        for issue in snap.issues:
            if issue.severity != Severity.CRITICAL:
                continue
            if issue.id in seen:
                continue
            _notify(issue.title, issue.description.split("\n")[0])
            seen.add(issue.id)
            _save_seen(seen)
            # Offer to launch GUI for Yes/No heal
            if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
                try:
                    import subprocess

                    subprocess.Popen(
                        ["vitaheal"],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except OSError:
                    pass
        # Clear seen for issues that recovered
        active = {i.id for i in snap.issues}
        seen = {i for i in seen if i in active} | (seen & active)
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(prog="vitaheal-daemon")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument(
        "--simulate-issue",
        choices=["cpu", "memory", "disk", "temp", "zombie", "swap"],
    )
    args = parser.parse_args(argv)
    try:
        return run_loop(interval=args.interval, simulate=args.simulate_issue)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
