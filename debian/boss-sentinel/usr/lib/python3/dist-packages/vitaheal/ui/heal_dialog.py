"""Yes/No autoheal confirmation popup."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from vitaheal.monitor.models import Issue


class HealConfirmDialog(Adw.MessageDialog):
    """Modal popup: explains the issue and asks Yes / No before healing."""

    def __init__(
        self,
        parent: Gtk.Window,
        issue: Issue,
        on_decision: Callable[[bool], None],
    ) -> None:
        # Construct without kwargs that older Adw may reject, then set props.
        super().__init__(transient_for=parent, modal=True)
        self.set_heading(f"BOSS-SENTINEL — {issue.title}")
        self.set_body(
            f"{issue.description}\n\n"
            f"Proposed action: {issue.heal_label}\n\n"
            "Do you want BOSS-Sentinel to proceed with this repair?"
        )
        self._on_decision = on_decision
        self.add_response("no", "No")
        self.add_response("yes", "Yes — Heal Now")
        self.set_response_appearance("yes", Adw.ResponseAppearance.SUGGESTED)
        self.set_response_appearance("no", Adw.ResponseAppearance.DESTRUCTIVE)
        self.set_default_response("no")
        self.set_close_response("no")
        self.connect("response", self._on_response)

    def _on_response(self, _dialog: Adw.MessageDialog, response: str) -> None:
        self._on_decision(response == "yes")


def ask_heal(
    parent: Gtk.Window,
    issue: Issue,
    on_decision: Callable[[bool], None],
) -> None:
    dlg = HealConfirmDialog(parent, issue, on_decision)
    dlg.present()


class HealResultToast:
    """Lightweight result banner inside the main window."""

    def __init__(self, overlay: Adw.ToastOverlay) -> None:
        self._overlay = overlay

    def show(self, message: str, ok: bool = True) -> None:
        toast = Adw.Toast.new(("✓ " if ok else "✗ ") + message)
        toast.set_timeout(5)
        self._overlay.add_toast(toast)
