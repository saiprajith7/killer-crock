"""BOSS Health panel / tray icon — stays in the Cinnamon menu bar.

Click → open the System Readiness dashboard.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk  # noqa: E402

ICON_CANDIDATES = (
    Path("/usr/share/icons/hicolor/64x64/apps/boss-health.png"),
    Path("/usr/share/icons/hicolor/scalable/apps/boss-health.svg"),
    Path("/usr/share/cinnamon/applets/boss-health@boss/icon.png"),
    Path(__file__).resolve().parents[2] / "data" / "icons" / "boss-health.png",
    Path(__file__).resolve().parents[2]
    / "data"
    / "cinnamon"
    / "applets"
    / "boss-health@boss"
    / "icon.png",
)

DASHBOARD_CANDIDATES = (
    "/usr/bin/boss-health",
    "/usr/local/bin/boss-health",
)


def _find_icon() -> str | None:
    for p in ICON_CANDIDATES:
        if p.is_file():
            return str(p)
    return None


def _dashboard_cmd() -> list[str]:
    for path in DASHBOARD_CANDIDATES:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return [path]
    found = GLib.find_program_in_path("boss-health")
    if found:
        return [found]
    env_python = sys.executable or "python3"
    return [env_python, "-m", "boss_health"]


def _launch_dashboard(*_args) -> None:
    """Open the BOSS Health readiness dashboard (non-blocking)."""
    cmd = _dashboard_cmd()
    env = os.environ.copy()
    # Ensure GUI can find the display when spawned from autostart
    env.setdefault("DISPLAY", os.environ.get("DISPLAY", ":0"))
    try:
        subprocess.Popen(cmd, env=env, start_new_session=True)
    except OSError as exc:
        dlg = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="BOSS Health",
        )
        dlg.format_secondary_text(f"Could not open dashboard:\n{exc}\n\nTried: {cmd}")
        dlg.run()
        dlg.destroy()


class BossHealthTray:
    def __init__(self) -> None:
        self.icon = Gtk.StatusIcon()
        icon_path = _find_icon()
        if icon_path:
            self.icon.set_from_file(icon_path)
        else:
            self.icon.set_from_icon_name("utilities-system-monitor")
        self.icon.set_title("BOSS Health")
        self.icon.set_tooltip_text("BOSS Health — System Readiness\nClick to open dashboard")
        self.icon.set_visible(True)
        # Some Cinnamon builds only deliver button-press-event, not activate
        self.icon.connect("activate", self._on_activate)
        self.icon.connect("button-press-event", self._on_button)
        self.icon.connect("popup-menu", self._on_popup)

        self.menu = Gtk.Menu()
        open_item = Gtk.MenuItem(label="Open BOSS Health dashboard")
        open_item.connect("activate", lambda *_: _launch_dashboard())
        self.menu.append(open_item)
        quit_item = Gtk.MenuItem(label="Quit tray icon")
        quit_item.connect("activate", self._on_quit)
        self.menu.append(quit_item)
        self.menu.show_all()

    def _on_activate(self, *_args) -> None:
        _launch_dashboard()

    def _on_button(self, _icon, event) -> bool:
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            _launch_dashboard()
            return True
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            self.menu.popup(
                None,
                None,
                Gtk.StatusIcon.position_menu,
                self.icon,
                event.button,
                event.time,
            )
            return True
        return False

    def _on_popup(self, _icon, button, activate_time) -> None:
        self.menu.popup(None, None, Gtk.StatusIcon.position_menu, self.icon, button, activate_time)

    def _on_quit(self, *_args) -> None:
        Gtk.main_quit()


def run_tray() -> int:
    try:
        from gi.repository import Gio  # noqa: E402

        app = Gio.Application.new("org.boss.BossHealthTray", Gio.ApplicationFlags.FLAGS_NONE)
        if not app.register(None):
            app = None
        elif app.get_is_remote():
            # Another tray is already running — ask it is enough; still OK
            return 0
    except Exception:
        app = None

    BossHealthTray()
    if app is not None:
        app.hold()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_tray())
