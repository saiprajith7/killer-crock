"""Persistent user settings for BOSS-Sentinel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Default OFF — users opt in when they want interactive heal prompts.
DEFAULT_AUTOHEAL = False

CONFIG_DIR = Path.home() / ".config" / "boss-sentinel"
SETTINGS_PATH = CONFIG_DIR / "settings.json"


def _defaults() -> dict[str, Any]:
    return {
        "autoheal_enabled": DEFAULT_AUTOHEAL,
    }


def load_settings() -> dict[str, Any]:
    data = _defaults()
    if not SETTINGS_PATH.exists():
        return data
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data.update(raw)
    except (OSError, json.JSONDecodeError):
        pass
    return data


def save_settings(settings: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    merged = _defaults()
    merged.update(settings)
    SETTINGS_PATH.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_autoheal_enabled() -> bool:
    return bool(load_settings().get("autoheal_enabled", DEFAULT_AUTOHEAL))


def set_autoheal_enabled(enabled: bool) -> None:
    settings = load_settings()
    settings["autoheal_enabled"] = bool(enabled)
    save_settings(settings)
