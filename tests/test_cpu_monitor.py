#!/usr/bin/env python3
"""Focused tests for CPU monitor (per-CPU + System Monitor accounting)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("BOSS_SENTINEL_CPU_SAMPLE", "0.05")

from vitaheal.monitor.cpu import CpuCollector, _idle_total  # noqa: E402
from vitaheal.monitor.engine import HealthEngine  # noqa: E402
from vitaheal.monitor.models import MetricKind, Severity  # noqa: E402


class CpuMonitorTests(unittest.TestCase):
    def test_gnome_iowait_is_busy(self) -> None:
        # user nice system idle iowait irq softirq steal guest guest_nice
        vals = [200, 0, 100, 500, 100, 0, 0, 0, 10, 0]
        idle, total = _idle_total(vals)
        self.assertEqual(idle, 500)
        self.assertEqual(total, 900)  # guest excluded
        pct = (1.0 - idle / total) * 100.0
        self.assertAlmostEqual(pct, 400 / 900 * 100.0, places=4)

    def test_per_core_matches_thread_count(self) -> None:
        c = CpuCollector()
        c.read()
        self.assertGreaterEqual(c.topology.logical_threads, 1)
        self.assertEqual(len(c.topology.per_core), c.topology.logical_threads)
        for pct in c.topology.per_core:
            self.assertGreaterEqual(pct, 0.0)
            self.assertLessEqual(pct, 100.0)

    def test_overall_is_mean_of_per_core(self) -> None:
        c = CpuCollector()
        readings = c.read()
        cpu = next(m for m in readings if m.kind == MetricKind.CPU)
        if c.topology.per_core:
            mean = sum(c.topology.per_core) / len(c.topology.per_core)
            self.assertAlmostEqual(cpu.value, round(mean, 1), delta=0.15)

    def test_cpu_thresholds(self) -> None:
        c = CpuCollector()
        readings = c.read()
        cpu = next(m for m in readings if m.kind == MetricKind.CPU)
        self.assertEqual(cpu.threshold_warn, 80)
        self.assertEqual(cpu.threshold_crit, 95)

    def test_simulate_marks_each_needed_field(self) -> None:
        snap = HealthEngine(simulate="cpu").snapshot()
        cpu = next(m for m in snap.metrics if m.kind == MetricKind.CPU)
        self.assertEqual(cpu.severity, Severity.CRITICAL)
        self.assertTrue(any(i.heal_action == "renice_hogs" for i in snap.issues))


if __name__ == "__main__":
    unittest.main()
