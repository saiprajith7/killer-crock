#!/usr/bin/env python3
"""Tests for hardware inventory / replace threshold / USB enumeration."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("BOSS_SENTINEL_CPU_SAMPLE", "0.05")

from vitaheal.monitor.engine import HealthEngine  # noqa: E402
from vitaheal.monitor.hardware import (  # noqa: E402
    REPLACE_THRESHOLD,
    HardwareCollector,
    _finalize,
    HardwareComponent,
)
from vitaheal.monitor.models import Severity  # noqa: E402


class HardwareTests(unittest.TestCase):
    def test_replace_threshold_constant(self) -> None:
        self.assertEqual(REPLACE_THRESHOLD, 45.0)

    def test_finalize_marks_replace_below_45(self) -> None:
        low = _finalize(
            HardwareComponent(
                id="x",
                category="disk",
                name="Dead disk",
                health=30.0,
                detail="full",
            )
        )
        self.assertTrue(low.replace)
        self.assertEqual(low.severity, Severity.CRITICAL)
        self.assertIn("Replace this hardware", low.advice)

        ok = _finalize(
            HardwareComponent(
                id="y",
                category="cpu",
                name="CPU",
                health=80.0,
                detail="fine",
            )
        )
        self.assertFalse(ok.replace)
        self.assertEqual(ok.severity, Severity.OK)

    def test_inventory_includes_core_categories(self) -> None:
        snap = HealthEngine().snapshot()
        comps = HardwareCollector().inventory(snap, cpu_model="TestCPU", cpu_cores=2, cpu_threads=4)
        cats = {c.category for c in comps}
        self.assertIn("cpu", cats)
        self.assertIn("memory", cats)
        self.assertIn("board", cats)
        for c in comps:
            self.assertGreaterEqual(c.health, 0.0)
            self.assertLessEqual(c.health, 100.0)
            if c.health < REPLACE_THRESHOLD:
                self.assertTrue(c.replace)

    def test_usb_enumeration_handles_missing_sysfs(self) -> None:
        with mock.patch("vitaheal.monitor.hardware.USB_SYS", Path("/nonexistent/usb")):
            from vitaheal.monitor import hardware as hw

            self.assertEqual(hw._usb_components(), [])

    def test_summary_counts_replace(self) -> None:
        comps = [
            _finalize(HardwareComponent("a", "cpu", "A", 90)),
            _finalize(HardwareComponent("b", "disk", "B", 20)),
        ]
        summary = HardwareCollector.summary(comps)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["replace_count"], 1)
        self.assertEqual(summary["worst"], "B")


if __name__ == "__main__":
    unittest.main()
