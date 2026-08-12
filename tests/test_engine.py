"""Tests for BOSS-Optimize collectors and optimize plan."""

from __future__ import annotations

import unittest

from bossoptimize.monitor.engine import OptimizeEngine
from bossoptimize.monitor.disk import list_disks
from bossoptimize.monitor.gpu import read_gpu
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


if __name__ == "__main__":
    unittest.main()
