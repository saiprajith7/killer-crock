"""Tests for BOSS-Optimize collectors and optimize plan."""

from __future__ import annotations

import unittest

from bossoptimize.monitor.appsessions import AppSessionTracker, classify_app
from bossoptimize.monitor.engine import OptimizeEngine
from bossoptimize.monitor.disk import list_disks
from bossoptimize.monitor.gpu import read_gpu
from bossoptimize.monitor.models import ProcessInfo
from bossoptimize.monitor.processes import list_processes
from bossoptimize.monitor.services import list_services


class EngineTests(unittest.TestCase):
    def test_snapshot_core_fields(self) -> None:
        snap = OptimizeEngine().snapshot()
        self.assertGreaterEqual(snap.cpu_percent, 0.0)
        self.assertLessEqual(snap.cpu_percent, 100.0)
        self.assertGreater(snap.mem_total_gb, 0.0)
        self.assertIsInstance(snap.processes, list)
        self.assertIsInstance(snap.services, list)
        self.assertIsInstance(snap.disks, list)
        self.assertIsNotNone(snap.gpu)
        d = snap.as_dict()
        self.assertIn("processes", d)
        self.assertIn("services", d)

    def test_optimize_plan_has_actions(self) -> None:
        eng = OptimizeEngine()
        plan = eng.build_optimize_plan()
        self.assertIn("actions", plan)
        self.assertTrue(len(plan["actions"]) >= 1)
        ids = {a["id"] for a in plan["actions"]}
        self.assertIn("cpu_performance", ids)


class CollectorTests(unittest.TestCase):
    def test_processes_nonempty(self) -> None:
        rows = list_processes(limit=50)
        self.assertTrue(len(rows) >= 1)
        self.assertTrue(hasattr(rows[0], "cpu_percent"))

    def test_services_parser_runs(self) -> None:
        rows = list_services(limit=50)
        self.assertIsInstance(rows, list)

    def test_disks_and_gpu(self) -> None:
        disks, r, w = list_disks()
        self.assertIsInstance(disks, list)
        self.assertGreaterEqual(r, 0.0)
        gpu = read_gpu()
        self.assertIsNotNone(gpu.name)


class AppSessionTests(unittest.TestCase):
    def test_classify_firefox(self) -> None:
        proc = ProcessInfo(
            pid=100,
            user="boss",
            name="firefox",
            cmdline="/usr/lib/firefox/firefox",
            cpu_percent=12.0,
            mem_percent=5.0,
            mem_rss_mb=400.0,
            read_bytes=1,
            write_bytes=2,
            io_total_bps=1000.0,
            gpu_percent=0.0,
            state="S",
            background=False,
        )
        got = classify_app(proc)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got[1], "Firefox")

    def test_open_and_close_session(self) -> None:
        tracker = AppSessionTracker(history_limit=20)
        tracker._closed.clear()
        tracker._active.clear()
        open_proc = ProcessInfo(
            pid=42,
            user="boss",
            name="firefox",
            cmdline="/usr/lib/firefox/firefox",
            cpu_percent=10.0,
            mem_percent=4.0,
            mem_rss_mb=300.0,
            read_bytes=10,
            write_bytes=20,
            io_total_bps=5000.0,
            gpu_percent=1.0,
            state="S",
            background=False,
        )
        rows = tracker.update([open_proc])
        running = [r for r in rows if r.running and r.app_id == "firefox"]
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0].pids, [42])
        self.assertIsNone(running[0].close_time)

        rows2 = tracker.update([])  # app closed
        closed = [r for r in rows2 if not r.running and r.app_id == "firefox"]
        self.assertTrue(len(closed) >= 1)
        self.assertIsNotNone(closed[0].close_time)


if __name__ == "__main__":
    unittest.main()
