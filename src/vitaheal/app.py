"""GTK4 / libadwaita application bootstrap."""

from __future__ import annotations

import sys
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from vitaheal import APP_ID
from vitaheal.ui.window import VitaHealWindow

# Must match installed icon + desktop file so the taskbar shows our logo
# (not a generic settings/gear fallback).
ICON_NAME = "org.bosssentinel.BossSentinel"


class VitaHealApp(Adw.Application):
    def __init__(self, simulate: Optional[str] = None) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._simulate = simulate
        self.connect("activate", self._on_activate)
        try:
            Gtk.Window.set_default_icon_name(ICON_NAME)
        except Exception:  # noqa: BLE001
            pass

    def _on_activate(self, app: Adw.Application) -> None:
        win = self.props.active_window
        if not win:
            win = VitaHealWindow(app, simulate=self._simulate)
            try:
                win.set_icon_name(ICON_NAME)
            except Exception:  # noqa: BLE001
                pass
        win.present()


def run_gui(simulate: Optional[str] = None) -> int:
    app = VitaHealApp(simulate=simulate)
    # Do not forward our CLI flags (--simulate-issue, etc.) to Gio/GTK.
    return app.run([sys.argv[0]])
