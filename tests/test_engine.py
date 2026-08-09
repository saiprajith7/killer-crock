#!/usr/bin/env python3
"""Unit tests for VitaHeal collectors / engine / heal (no GUI)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaheal.heal import actions as heal_actions  # noqa: E402
from vitaheal.monitor.engine import HealthEngine  # noqa: E402
from vitaheal.monitor.models import MetricKind, Severity  # noqa: E402


class EngineTests(unittest.TestCase):
    def test_snapshot_has_core_metrics(self) -> None:
        snap = HealthEngine().snapshot()
        kinds = {m.kind for m in snap.metrics}
        self.assertIn(MetricKind.CPU, kinds)
        self.assertIn(MetricKind.MEMORY, kinds)
        self.assertIn(MetricKind.DISK, kinds)
        self.assertTrue(0 <= snap.score <= 100)

    def test_simulate_memory_critical(self) -> None:
        snap = HealthEngine(simulate="memory").snapshot()
        mem = next(m for m in snap.metrics if m.kind == MetricKind.MEMORY)
        self.assertEqual(mem.severity, Severity.CRITICAL)
        self.assertTrue(any(i.kind == MetricKind.MEMORY for i in snap.issues))
        self.assertTrue(any(i.heal_action == "drop_caches" for i in snap.issues))

    def test_simulate_cpu_issue_payload(self) -> None:
        snap = HealthEngine(simulate="cpu").snapshot()
        issue = next(i for i in snap.issues if i.kind == MetricKind.CPU)
        self.assertEqual(issue.heal_action, "renice_hogs")
        self.assertIn("CPU", issue.title)
        self.assertTrue(issue.heal_label)

    def test_snapshot_json_serializable(self) -> None:
        raw = HealthEngine().snapshot().as_dict()
        json.dumps(raw)  # must not raise


class HealTests(unittest.TestCase):
    def test_local_simulate_ok(self) -> None:
        result = heal_actions.perform_heal("simulate_ok")
        self.assertTrue(result.ok)

    def test_local_prune_tmp(self) -> None:
        result = heal_actions._local_prune_tmp()
        self.assertTrue(result.ok)

    def test_helper_script_parses(self) -> None:
        helper = ROOT / "scripts" / "vitaheal-helper"
        self.assertTrue(helper.exists())
        src = helper.read_text()
        self.assertIn("drop_caches", src)
        compile(src, str(helper), "exec")


if __name__ == "__main__":
    unittest.main()
