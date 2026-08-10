#!/usr/bin/env python3
"""Tests for persistent autoheal settings."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaheal import settings as settings_mod  # noqa: E402


class SettingsTests(unittest.TestCase):
    def test_default_autoheal_is_off(self) -> None:
        self.assertFalse(settings_mod.DEFAULT_AUTOHEAL)

    def test_persist_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            with mock.patch.object(settings_mod, "SETTINGS_PATH", path), mock.patch.object(
                settings_mod, "CONFIG_DIR", Path(td)
            ):
                self.assertFalse(settings_mod.get_autoheal_enabled())
                settings_mod.set_autoheal_enabled(True)
                self.assertTrue(settings_mod.get_autoheal_enabled())
                raw = json.loads(path.read_text())
                self.assertTrue(raw["autoheal_enabled"])
                settings_mod.set_autoheal_enabled(False)
                self.assertFalse(settings_mod.get_autoheal_enabled())


if __name__ == "__main__":
    unittest.main()
