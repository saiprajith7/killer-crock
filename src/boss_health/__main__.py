"""Application entry points for BOSS Health."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="boss-health",
        description="BOSS Health — System Readiness dashboard for BOSS GNU/Linux",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run all checks once, print JSON, and exit (no GUI)",
    )
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Run as menu-bar / system-tray icon (click opens dashboard)",
    )
    parser.add_argument(
        "--simulate-issue",
        choices=["cpu", "memory", "disk", "temp", "zombie", "swap", "gpu"],
        help="Inject a sentinel simulated issue into system-health checks",
    )
    args = parser.parse_args(argv)

    if args.once:
        from boss_health.readiness import run_all_checks

        report = run_all_checks(simulate=args.simulate_issue)
        print(json.dumps(report.as_dict(), indent=2))
        return 0 if report.overall.value == "pass" else 1

    if args.tray:
        try:
            from boss_health.tray import run_tray
        except (ImportError, ValueError) as exc:
            print(f"BOSS Health tray unavailable ({exc}).", file=sys.stderr)
            return 2
        return run_tray()

    try:
        from boss_health.dashboard import run_dashboard
    except (ImportError, ValueError) as exc:
        print(
            f"BOSS Health GUI unavailable ({exc}). "
            "Install gir1.2-gtk-3.0 / python3-gi, or use --once.",
            file=sys.stderr,
        )
        return 2

    return run_dashboard(simulate=args.simulate_issue)


def tray_main(argv: list[str] | None = None) -> int:
    """Entry point for boss-health-tray."""
    return main(["--tray", *(argv or [])])


if __name__ == "__main__":
    raise SystemExit(main())
