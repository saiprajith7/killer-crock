"""BOSS Health GTK4 dashboard — System Readiness."""

from __future__ import annotations

import datetime as dt
import threading
import time
from pathlib import Path
from typing import Optional

import gi

# BOSS systems often already ship Gdk/Gtk 4 (sentinel stack). Bind explicitly first.
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

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
    try:
        provider.load_from_path(str(CSS_PATH))
    except GLib.Error:
        return
    display = Gdk.Display.get_default()
    if display is None:
        return
    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def _fmt_time(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


class DetailsWindow(Gtk.Window):
    def __init__(self, parent: Gtk.Window, report: ReadinessReport) -> None:
        super().__init__(title="BOSS Health — View Details")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(560, 480)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        self.set_child(outer)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)

        text = Gtk.TextView()
        text.set_editable(False)
        text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text.set_cursor_visible(False)
        text.add_css_class("bh-details-mono")
        buf = text.get_buffer()

        lines: list[str] = [
            "BOSS HEALTH — System Readiness",
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
        scroll.set_child(text)
        outer.append(scroll)

        close_btn = Gtk.Button(label="Close")
        close_btn.add_css_class("bh-btn-secondary")
        close_btn.set_halign(Gtk.Align.END)
        close_btn.connect("clicked", lambda *_: self.destroy())
        outer.append(close_btn)


class BossHealthDashboard(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, *, simulate: Optional[str] = None) -> None:
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(460, 640)
        self.set_resizable(True)
        self.add_css_class("boss-health-window")
        self._simulate = simulate
        self._report: Optional[ReadinessReport] = None
        self._busy = False

        _load_css()

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.add_css_class("bh-outer")
        outer.set_margin_top(18)
        outer.set_margin_bottom(16)
        outer.set_margin_start(20)
        outer.set_margin_end(20)
        self.set_child(outer)

        brand = Gtk.Label(label="BOSS HEALTH")
        brand.set_halign(Gtk.Align.START)
        brand.add_css_class("bh-brand")
        outer.append(brand)

        sub = Gtk.Label(label=APP_SUBTITLE)
        sub.set_halign(Gtk.Align.START)
        sub.add_css_class("bh-subtitle")
        outer.append(sub)

        self._ts_label = Gtk.Label(label="Last Checked: —")
        self._ts_label.set_halign(Gtk.Align.START)
        self._ts_label.add_css_class("bh-timestamp")
        outer.append(self._ts_label)

        self._section_widgets: dict[str, Gtk.Box] = {}
        for cat, title in CATEGORY_ORDER:
            sec = self._make_section(title)
            self._section_widgets[cat] = sec
            outer.append(sec)

        overall_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        overall_box.add_css_class("bh-overall-box")
        overall_box.set_margin_top(12)
        cap = Gtk.Label(label="Overall Status")
        cap.set_halign(Gtk.Align.START)
        cap.add_css_class("bh-overall-caption")
        self._overall_label = Gtk.Label(label="…")
        self._overall_label.set_halign(Gtk.Align.START)
        self._overall_label.add_css_class("bh-overall-status")
        overall_box.append(cap)
        overall_box.append(self._overall_label)
        outer.append(overall_box)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.add_css_class("bh-actions")
        actions.set_halign(Gtk.Align.END)
        actions.set_margin_top(14)

        self._btn_details = Gtk.Button(label="View Details")
        self._btn_details.add_css_class("bh-btn-secondary")
        self._btn_details.connect("clicked", self._on_details)

        self._btn_again = Gtk.Button(label="Run Check Again")
        self._btn_again.add_css_class("bh-btn-primary")
        self._btn_again.connect("clicked", self._on_again)

        self._btn_close = Gtk.Button(label="Close")
        self._btn_close.add_css_class("bh-btn-secondary")
        self._btn_close.connect("clicked", lambda *_: self.close())

        actions.append(self._btn_details)
        actions.append(self._btn_again)
        actions.append(self._btn_close)
        outer.append(actions)

        self.refresh()

    def _make_section(self, title: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("bh-section")
        box.set_margin_top(10)
        lab = Gtk.Label(label=title)
        lab.set_halign(Gtk.Align.START)
        lab.add_css_class("bh-section-title")
        box.append(lab)
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(rows)
        box._rows = rows  # type: ignore[attr-defined]
        return box

    def _clear_rows(self, section: Gtk.Box) -> None:
        rows = section._rows  # type: ignore[attr-defined]
        child = rows.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            rows.remove(child)
            child = nxt

    def _add_row(self, section: Gtk.Box, check: CheckResult) -> None:
        rows = section._rows  # type: ignore[attr-defined]
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("bh-row")

        sym = Gtk.Label(label=check.status.symbol)
        sym.add_css_class("bh-symbol")
        sym.add_css_class(check.status.css_class)
        sym.set_halign(Gtk.Align.START)

        label = Gtk.Label(label=check.label)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.add_css_class("bh-row-label")
        label.set_ellipsize(Pango.EllipsizeMode.END)

        value = Gtk.Label(label=check.value or "")
        value.set_halign(Gtk.Align.END)
        value.add_css_class("bh-row-value")

        row.append(sym)
        row.append(label)
        row.append(value)
        rows.append(row)

    def apply_report(self, report: ReadinessReport) -> None:
        self._report = report
        self._ts_label.set_text(f"Last Checked: {_fmt_time(report.timestamp)}")
        for cat, _title in CATEGORY_ORDER:
            sec = self._section_widgets[cat]
            self._clear_rows(sec)
            for check in report.checks_in(cat):
                self._add_row(sec, check)

        self._overall_label.set_text(f"{report.overall.symbol}  {report.overall_label}")
        for cls in ("status-pass", "status-warn", "status-fail", "status-unknown"):
            self._overall_label.remove_css_class(cls)
        self._overall_label.add_css_class(report.overall.css_class)

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
                    timestamp=time.time(),
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
        DetailsWindow(self, self._report).present()


class BossHealthApp(Gtk.Application):
    def __init__(self, *, simulate: Optional[str] = None) -> None:
        super().__init__(
            application_id="org.boss.BossHealth",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._simulate = simulate

    def do_activate(self) -> None:  # noqa: N802 — GObject override
        win = self.props.active_window
        if not win:
            win = BossHealthDashboard(self, simulate=self._simulate)
        win.present()


def run_dashboard(*, simulate: Optional[str] = None) -> int:
    _load_css()
    app = BossHealthApp(simulate=simulate)
    return int(app.run(None) or 0)
