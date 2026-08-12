"""CLI entry for BOSS-Optimize."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="boss-optimize",
        description="BOSS-Optimize — list services/processes/packages and optimize performance",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print one JSON performance snapshot and exit",
    )
    parser.add_argument(
        "--optimize-plan",
        action="store_true",
        help="Print the proposed optimization plan as JSON and exit",
    )
    args = parser.parse_args(argv)

    if args.once or args.optimize_plan:
        from bossoptimize.monitor.engine import OptimizeEngine

        engine = OptimizeEngine()
        snap = engine.snapshot()
        if args.optimize_plan:
            plan = engine.build_optimize_plan(snap)
            print(json.dumps(plan, indent=2))
        else:
            print(json.dumps(snap.as_dict(), indent=2))
        return 0

    from bossoptimize.app import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
