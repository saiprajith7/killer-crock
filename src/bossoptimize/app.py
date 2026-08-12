"""GTK4 / libadwaita bootstrap."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from bossoptimize import APP_ID, ICON_NAME
from bossoptimize.ui.window import OptimizeWindow


class OptimizeApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect("activate", self._on_activate)
        try:
            Gtk.Window.set_default_icon_name(ICON_NAME)
        except Exception:  # noqa: BLE001
            pass

    def _on_activate(self, _app: Adw.Application) -> None:
        win = self.props.active_window
        if not win:
            win = OptimizeWindow(self)
            try:
                win.set_icon_name(ICON_NAME)
            except Exception:  # noqa: BLE001
                pass
        win.present()


def run_gui() -> int:
    return OptimizeApp().run([sys.argv[0]])
