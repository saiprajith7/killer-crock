"""Application entry points."""

from __future__ import annotations

import argparse
import sys


class _QuietStderr:
    """Drop known-harmless GPU/Mesa driver chatter from the terminal."""

    _DROP_FRAGMENTS = (
        "libEGL warning: DRI2: failed to authenticate",
        "libEGL warning: DRI3: failed to authenticate",
        "libEGL warning: failed to create dri2 display",
    )

    def __init__(self, real) -> None:
        self._real = real
        self._buf = ""

    def write(self, data: str) -> int:
        if not isinstance(data, str):
            data = str(data)
        self._buf += data
        written = 0
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if any(frag in line for frag in self._DROP_FRAGMENTS):
                continue
            written += self._real.write(line + "\n")
        return written

    def flush(self) -> None:
        if self._buf and not any(frag in self._buf for frag in self._DROP_FRAGMENTS):
            self._real.write(self._buf)
        self._buf = ""
        self._real.flush()

    def fileno(self) -> int:
        return self._real.fileno()

    def isatty(self) -> bool:
        return self._real.isatty()

    def __getattr__(self, name: str):
        return getattr(self._real, name)


def _quiet_graphics_warnings() -> None:
    if isinstance(sys.stderr, _QuietStderr):
        return
    sys.stderr = _QuietStderr(sys.stderr)


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

    _quiet_graphics_warnings()
    from vitaheal.app import run_gui

    return run_gui(simulate=args.simulate_issue)


if __name__ == "__main__":
    sys.exit(main())
