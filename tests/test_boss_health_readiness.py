"""Tests for BOSS Health readiness (reuses sentinel collectors)."""

from __future__ import annotations

import unittest

from boss_health.models import CheckStatus
from boss_health.readiness import aggregate_overall, run_all_checks, system_health_from_sentinel
from boss_health.models import CheckResult
from vitaheal.monitor.engine import HealthEngine


class TestBossHealthReadiness(unittest.TestCase):
    def test_system_health_reuses_sentinel_engine(self) -> None:
        engine = HealthEngine()
        checks = system_health_from_sentinel(engine)
        ids = {c.id for c in checks}
        self.assertEqual(ids, {"cpu", "ram", "disk", "overall_system"})
        for c in checks:
            self.assertEqual(c.category, "system")
            self.assertIn(c.status, list(CheckStatus))

    def test_run_all_checks_has_v1_suite(self) -> None:
        report = run_all_checks()
        ids = {c.id for c in report.checks}
        expected = {
            "repository",
            "isoc",
            "network",
            "cpu",
            "ram",
            "disk",
            "overall_system",
            "critical_services",
            "security_services",
        }
        self.assertTrue(expected.issubset(ids))
        self.assertIn(report.overall, list(CheckStatus))
        self.assertTrue(report.overall_label)

    def test_aggregate_overall(self) -> None:
        ok = CheckResult("a", "system", "A", CheckStatus.PASS)
        warn = CheckResult("b", "system", "B", CheckStatus.WARNING)
        fail = CheckResult("c", "system", "C", CheckStatus.FAIL)
        self.assertEqual(aggregate_overall([ok])[1], "SYSTEM READY")
        self.assertEqual(aggregate_overall([ok, warn])[1], "ACTION REQUIRED")
        self.assertEqual(aggregate_overall([ok, fail])[1], "SYSTEM NOT READY")

    def test_simulate_cpu_propagates_from_sentinel(self) -> None:
        report = run_all_checks(simulate="cpu")
        cpu = next(c for c in report.checks if c.id == "cpu")
        self.assertEqual(cpu.status, CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
