"""GTK4 / libadwaita application bootstrap."""

from __future__ import annotations

import sys
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

from vitaheal import APP_ID
from vitaheal.ui.window import VitaHealWindow


class VitaHealApp(Adw.Application):
    def __init__(self, simulate: Optional[str] = None) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._simulate = simulate
        self.connect("activate", self._on_activate)

    def _on_activate(self, app: Adw.Application) -> None:
        win = self.props.active_window
        if not win:
            win = VitaHealWindow(app, simulate=self._simulate)
        win.present()


def run_gui(simulate: Optional[str] = None) -> int:
    app = VitaHealApp(simulate=simulate)
    # Do not forward our CLI flags (--simulate-issue, etc.) to Gio/GTK.
    return app.run([sys.argv[0]])
