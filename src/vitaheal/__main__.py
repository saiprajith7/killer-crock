"""Application entry points."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="boss-sentinel",
        description="BOSS-Sentinel — PC health monitoring & interactive autohealing",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run headless background watcher (use vitaheal-daemon instead)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print a single health snapshot as JSON and exit",
    )
    parser.add_argument(
        "--simulate-issue",
        choices=["cpu", "memory", "disk", "temp", "zombie", "swap", "gpu"],
        help="Inject a fake critical issue for UI / heal demos",
    )
    args = parser.parse_args(argv)

    if args.once:
        from vitaheal.monitor.engine import HealthEngine
        import json

        engine = HealthEngine(simulate=args.simulate_issue)
        print(json.dumps(engine.snapshot().as_dict(), indent=2))
        return 0

    if args.daemon:
        from vitaheal.daemon.watcher import main as daemon_main

        return daemon_main()

    from vitaheal.app import run_gui

    return run_gui(simulate=args.simulate_issue)


if __name__ == "__main__":
    sys.exit(main())
