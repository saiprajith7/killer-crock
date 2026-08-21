"""BOSS Health GTK dashboard — System Readiness."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from boss_health import APP_NAME, APP_SUBTITLE
from boss_health.models import CheckResult, CheckStatus, ReadinessReport
from boss_health.readiness import run_all_checks

CSS_PATH = Path(__file__).with_name("style.css")

CATEGORY_ORDER = (
    ("connectivity", "CONNECTIVITY"),
    ("system", "SYSTEM HEALTH"),
    ("services", "SERVICES"),
)


def _load_css() -> None:
    if not CSS_PATH.is_file():
        return
    provider = Gtk.CssProvider()
    provider.load_from_path(str(CSS_PATH))
    screen = Gdk.Screen.get_default()
    if screen is None:
        return
    Gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def _fmt_time(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


class DetailsDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, report: ReadinessReport) -> None:
        super().__init__(title="BOSS Health — View Details", transient_for=parent, modal=True)
        self.set_default_size(560, 480)
        self.add_button("Close", Gtk.ResponseType.CLOSE)
        box = self.get_content_area()
        box.set_border_width(12)
        box.set_spacing(8)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)

        text = Gtk.TextView()
        text.set_editable(False)
        text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text.set_cursor_visible(False)
        buf = text.get_buffer()
        lines: list[str] = [
            f"BOSS HEALTH — System Readiness",
            f"Last Checked: {_fmt_time(report.timestamp)}",
            f"Overall: {report.overall.symbol} {report.overall_label}",
            "",
        ]
        for cat, title in CATEGORY_ORDER:
            lines.append(f"══ {title} ══")
            for c in report.checks_in(cat):
                val = f"  [{c.value}]" if c.value else ""
                lines.append(f"{c.status.symbol} {c.label}{val}")
                lines.append(f"   Status : {c.status.value.upper()}")
                lines.append(f"   Summary: {c.summary}")
                if c.detail:
                    for dline in c.detail.splitlines():
                        lines.append(f"   Detail : {dline}")
                lines.append("")
            lines.append("")
        buf.set_text("\n".join(lines))
        text.get_style_context().add_class("bh-details-mono")
        scroll.add(text)
        box.pack_start(scroll, True, True, 0)
        self.show_all()


class BossHealthDashboard(Gtk.Window):
    def __init__(self, *, simulate: Optional[str] = None) -> None:
        super().__init__(title=APP_NAME)
        self.set_default_size(440, 620)
        self.set_resizable(True)
        self.set_border_width(0)
        self.get_style_context().add_class("boss-health-window")
        self._simulate = simulate
        self._report: Optional[ReadinessReport] = None
        self._busy = False

        _load_css()

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.get_style_context().add_class("boss-health-outer")
        self.add(outer)

        # Header
        brand = Gtk.Label(label="BOSS HEALTH")
        brand.set_halign(Gtk.Align.START)
        brand.get_style_context().add_class("bh-brand")
        outer.pack_start(brand, False, False, 0)

        sub = Gtk.Label(label=APP_SUBTITLE)
        sub.set_halign(Gtk.Align.START)
        sub.get_style_context().add_class("bh-subtitle")
        outer.pack_start(sub, False, False, 0)

        self._ts_label = Gtk.Label(label="Last Checked: —")
        self._ts_label.set_halign(Gtk.Align.START)
        self._ts_label.get_style_context().add_class("bh-timestamp")
        outer.pack_start(self._ts_label, False, False, 0)

        # Sections container
        self._sections_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.pack_start(self._sections_box, True, True, 0)

        self._section_widgets: dict[str, Gtk.Box] = {}
        for cat, title in CATEGORY_ORDER:
            sec = self._make_section(title)
            self._section_widgets[cat] = sec
            self._sections_box.pack_start(sec, False, False, 0)

        # Overall
        overall_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        overall_box.get_style_context().add_class("bh-overall-box")
        cap = Gtk.Label(label="Overall Status")
        cap.set_halign(Gtk.Align.START)
        cap.get_style_context().add_class("bh-overall-caption")
        self._overall_label = Gtk.Label(label="…")
        self._overall_label.set_halign(Gtk.Align.START)
        self._overall_label.get_style_context().add_class("bh-overall-status")
        overall_box.pack_start(cap, False, False, 0)
        overall_box.pack_start(self._overall_label, False, False, 0)
        outer.pack_start(overall_box, False, False, 0)

        # Actions
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.get_style_context().add_class("bh-actions")
        actions.set_halign(Gtk.Align.END)

        self._btn_details = Gtk.Button(label="View Details")
        self._btn_details.get_style_context().add_class("bh-btn-secondary")
        self._btn_details.connect("clicked", self._on_details)

        self._btn_again = Gtk.Button(label="Run Check Again")
        self._btn_again.get_style_context().add_class("bh-btn-primary")
        self._btn_again.connect("clicked", self._on_again)

        self._btn_close = Gtk.Button(label="Close")
        self._btn_close.get_style_context().add_class("bh-btn-secondary")
        self._btn_close.connect("clicked", lambda *_: self.destroy())

        actions.pack_start(self._btn_details, False, False, 0)
        actions.pack_start(self._btn_again, False, False, 0)
        actions.pack_start(self._btn_close, False, False, 0)
        outer.pack_start(actions, False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.show_all()
        self.refresh()

    def _make_section(self, title: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.get_style_context().add_class("bh-section")
        lab = Gtk.Label(label=title)
        lab.set_halign(Gtk.Align.START)
        lab.get_style_context().add_class("bh-section-title")
        box.pack_start(lab, False, False, 0)
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        rows.set_name("rows")
        box.pack_start(rows, False, False, 0)
        # stash rows container
        box._rows = rows  # type: ignore[attr-defined]
        return box

    def _clear_rows(self, section: Gtk.Box) -> None:
        rows = section._rows  # type: ignore[attr-defined]
        for child in list(rows.get_children()):
            rows.remove(child)

    def _add_row(self, section: Gtk.Box, check: CheckResult) -> None:
        rows = section._rows  # type: ignore[attr-defined]
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.get_style_context().add_class("bh-row")

        sym = Gtk.Label(label=check.status.symbol)
        sym.get_style_context().add_class("bh-symbol")
        sym.get_style_context().add_class(check.status.css_class)
        sym.set_halign(Gtk.Align.START)

        label = Gtk.Label(label=check.label)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.get_style_context().add_class("bh-row-label")
        label.set_ellipsize(Pango.EllipsizeMode.END)

        value = Gtk.Label(label=check.value or "")
        value.set_halign(Gtk.Align.END)
        value.get_style_context().add_class("bh-row-value")

        row.pack_start(sym, False, False, 0)
        row.pack_start(label, True, True, 0)
        row.pack_start(value, False, False, 0)
        rows.pack_start(row, False, False, 0)

    def apply_report(self, report: ReadinessReport) -> None:
        self._report = report
        self._ts_label.set_text(f"Last Checked: {_fmt_time(report.timestamp)}")
        for cat, _title in CATEGORY_ORDER:
            sec = self._section_widgets[cat]
            self._clear_rows(sec)
            for check in report.checks_in(cat):
                self._add_row(sec, check)
            sec.show_all()

        self._overall_label.set_text(f"{report.overall.symbol}  {report.overall_label}")
        ctx = self._overall_label.get_style_context()
        for cls in ("status-pass", "status-warn", "status-fail", "status-unknown"):
            ctx.remove_class(cls)
        ctx.add_class(report.overall.css_class)

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._btn_again.set_sensitive(False)
        self._overall_label.set_text("Running checks…")

        simulate = self._simulate

        def work() -> None:
            try:
                report = run_all_checks(simulate=simulate)
            except Exception as exc:  # noqa: BLE001
                report = ReadinessReport(
                    timestamp=__import__("time").time(),
                    checks=[
                        CheckResult(
                            id="error",
                            category="system",
                            label="Readiness Engine",
                            status=CheckStatus.FAIL,
                            summary="Check suite failed",
                            detail=str(exc),
                        )
                    ],
                    overall=CheckStatus.FAIL,
                    overall_label="SYSTEM NOT READY",
                )
            GLib.idle_add(self._on_refresh_done, report)

        import threading

        threading.Thread(target=work, daemon=True).start()

    def _on_refresh_done(self, report: ReadinessReport) -> bool:
        self.apply_report(report)
        self._busy = False
        self._btn_again.set_sensitive(True)
        return False

    def _on_again(self, *_args) -> None:
        self.refresh()

    def _on_details(self, *_args) -> None:
        if not self._report:
            return
        dlg = DetailsDialog(self, self._report)
        dlg.run()
        dlg.destroy()


def run_dashboard(*, simulate: Optional[str] = None) -> int:
    _load_css()
    win = BossHealthDashboard(simulate=simulate)
    win.present()
    Gtk.main()
    return 0
