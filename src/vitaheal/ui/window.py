"""Minimal VitaHeal window — device graphs + trouble/heal logs + close."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from vitaheal.heal.actions import perform_heal
from vitaheal.monitor.engine import HealthEngine
from vitaheal.monitor.models import HealthSnapshot, Issue, MetricKind, Severity
from vitaheal.ui.eventlog import EventLog
from vitaheal.ui.gauges import BreathWave, DeviceGraph, HeroVitality
from vitaheal.ui.heal_dialog import HealResultToast, ask_heal

CSS_PATH = Path(__file__).with_name("style.css")


class VitaHealWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, simulate: Optional[str] = None) -> None:
        super().__init__(application=app, title="VitaHeal")
        self.set_default_size(1180, 780)
        self.add_css_class("vitaheal-window")

        self.engine = HealthEngine(simulate=simulate)
        self.events = EventLog()
        self._pending_issue_ids: set[str] = set()
        self._autoheal_enabled = True
        self._last_snap: Optional[HealthSnapshot] = None

        self._load_css()
        self._build()

        GLib.timeout_add_seconds(2, self._refresh)
        GLib.idle_add(self._refresh)

    def _load_css(self) -> None:
        css = Gtk.CssProvider()
        css.load_from_path(str(CSS_PATH))
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build(self) -> None:
        # Native titlebar close (window manager X) + our explicit X
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        header.add_css_class("header-bar")
        title = Gtk.Label(label="VitaHeal")
        title.add_css_class("brand-sub")
        header.set_title_widget(title)
        self.set_titlebar(header)

        self.toast_overlay = Adw.ToastOverlay()
        self.toasts = HealResultToast(self.toast_overlay)
        self.set_content(self.toast_overlay)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.toast_overlay.set_child(root)

        # —— Top bar: brand + close ——
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top.add_css_class("topbar")

        brand_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        brand_col.set_hexpand(True)
        brand = Gtk.Label(label="VITAHEAL")
        brand.add_css_class("brand")
        brand.set_halign(Gtk.Align.START)
        sub = Gtk.Label(label="SYSTEM HEALTH · AUTOHEAL")
        sub.add_css_class("brand-sub")
        sub.set_halign(Gtk.Align.START)
        brand_col.append(brand)
        brand_col.append(sub)
        top.append(brand_col)

        self.auto_btn = Gtk.ToggleButton(label="AUTOHEAL ON")
        self.auto_btn.add_css_class("cta-ghost")
        self.auto_btn.set_active(True)
        self.auto_btn.connect("toggled", self._on_auto_toggled)
        top.append(self.auto_btn)

        close_btn = Gtk.Button(label="×")
        close_btn.add_css_class("close-x")
        close_btn.set_tooltip_text("Close")
        close_btn.connect("clicked", lambda *_: self.close())
        top.append(close_btn)
        root.append(top)

        # —— Hero composition ——
        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        hero.add_css_class("hero")

        self.vitality = HeroVitality()
        hero.append(self.vitality)

        hero_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero_text.set_valign(Gtk.Align.CENTER)
        hero_text.set_hexpand(True)

        self.status_label = Gtk.Label(label="ALL SYSTEMS NOMINAL")
        self.status_label.add_css_class("hero-status")
        self.status_label.set_halign(Gtk.Align.START)
        hero_text.append(self.status_label)

        self.blurb = Gtk.Label(
            label="Every device. Live graphs. Trouble on the left, healing on the right."
        )
        self.blurb.add_css_class("hero-line")
        self.blurb.set_halign(Gtk.Align.START)
        self.blurb.set_wrap(True)
        self.blurb.set_xalign(0)
        hero_text.append(self.blurb)
        hero.append(hero_text)
        root.append(hero)

        self.wave = BreathWave()
        self.wave.set_margin_start(20)
        self.wave.set_margin_end(20)
        self.wave.set_margin_bottom(8)
        root.append(self.wave)

        # —— Device health graphs ——
        devices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        devices.add_css_class("device-grid")

        lab = Gtk.Label(label="DEVICE HEALTH")
        lab.add_css_class("section-label")
        lab.set_halign(Gtk.Align.START)
        devices.append(lab)

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row1.set_homogeneous(True)
        self.g_ram = DeviceGraph("RAM")
        self.g_disk = DeviceGraph("DISK")
        self.g_cpu = DeviceGraph("CPU")
        for g in (self.g_ram, self.g_disk, self.g_cpu):
            cell = Gtk.Box()
            cell.add_css_class("device-cell")
            cell.append(g)
            row1.append(cell)
        devices.append(row1)

        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row2.set_homogeneous(True)
        self.g_gpu = DeviceGraph("GPU")
        self.g_temp = DeviceGraph("TEMP")
        self.g_swap = DeviceGraph("SWAP")
        for g in (self.g_gpu, self.g_temp, self.g_swap):
            cell = Gtk.Box()
            cell.add_css_class("device-cell")
            cell.append(g)
            row2.append(cell)
        devices.append(row2)
        root.append(devices)

        # —— Dual logs ——
        logs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        logs.add_css_class("logs-row")
        logs.set_vexpand(True)

        # Trouble log
        trouble_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        trouble_pane.add_css_class("log-pane")
        trouble_pane.add_css_class("trouble")
        trouble_pane.set_hexpand(True)
        t_title = Gtk.Label(label="TROUBLE LOG")
        t_title.add_css_class("log-title")
        t_title.add_css_class("trouble")
        t_title.set_halign(Gtk.Align.START)
        trouble_pane.append(t_title)

        self.trouble_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        t_scroll = Gtk.ScrolledWindow()
        t_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        t_scroll.set_vexpand(True)
        t_scroll.set_child(self.trouble_box)
        trouble_pane.append(t_scroll)
        logs.append(trouble_pane)

        # Heal log
        heal_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        heal_pane.add_css_class("log-pane")
        heal_pane.add_css_class("heal")
        heal_pane.set_hexpand(True)
        h_title = Gtk.Label(label="HEAL LOG")
        h_title.add_css_class("log-title")
        h_title.add_css_class("heal")
        h_title.set_halign(Gtk.Align.START)
        heal_pane.append(h_title)

        self.heal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        h_scroll = Gtk.ScrolledWindow()
        h_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        h_scroll.set_vexpand(True)
        h_scroll.set_child(self.heal_box)
        heal_pane.append(h_scroll)
        logs.append(heal_pane)

        root.append(logs)

        self.footer = Gtk.Label(label="")
        self.footer.add_css_class("footer-meta")
        self.footer.set_halign(Gtk.Align.START)
        root.append(self.footer)

        self._paint_logs()

    def _on_auto_toggled(self, btn: Gtk.ToggleButton) -> None:
        self._autoheal_enabled = btn.get_active()
        btn.set_label("AUTOHEAL ON" if self._autoheal_enabled else "AUTOHEAL OFF")

    def _clear_box(self, box: Gtk.Box) -> None:
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt

    def _paint_logs(self) -> None:
        self._clear_box(self.trouble_box)
        self._clear_box(self.heal_box)

        # Active issues first (actionable), then historical trouble log
        snap_issues = self._last_snap.issues if self._last_snap else []
        if snap_issues:
            for issue in snap_issues:
                self.trouble_box.append(self._issue_row(issue))

        hist = self.events.trouble
        if not snap_issues and not hist:
            empty = Gtk.Label(label="Nothing wrong right now.")
            empty.add_css_class("log-empty")
            empty.set_halign(Gtk.Align.START)
            self.trouble_box.append(empty)
        else:
            for entry in hist[:40]:
                self.trouble_box.append(self._log_row(entry.clock, entry.title, entry.detail))

        heals = self.events.heal
        if not heals:
            empty = Gtk.Label(label="No heal actions yet.")
            empty.add_css_class("log-empty")
            empty.set_halign(Gtk.Align.START)
            self.heal_box.append(empty)
        else:
            for entry in heals[:40]:
                self.heal_box.append(self._log_row(entry.clock, entry.title, entry.detail))

    def _log_row(self, clock: str, title: str, detail: str) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        row.add_css_class("log-row")
        t = Gtk.Label(label=f"{clock}  {title}")
        t.add_css_class("log-head")
        t.set_halign(Gtk.Align.START)
        t.set_wrap(True)
        t.set_xalign(0)
        d = Gtk.Label(label=detail[:140])
        d.add_css_class("log-detail")
        d.set_halign(Gtk.Align.START)
        d.set_wrap(True)
        d.set_xalign(0)
        row.append(t)
        row.append(d)
        return row

    def _issue_row(self, issue: Issue) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("issue-inline")

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        t = Gtk.Label(label=issue.title)
        t.add_css_class("log-head")
        t.set_halign(Gtk.Align.START)
        d = Gtk.Label(label=issue.description.split("\n")[0][:100])
        d.add_css_class("log-detail")
        d.set_halign(Gtk.Align.START)
        d.set_wrap(True)
        d.set_xalign(0)
        text.append(t)
        text.append(d)
        row.append(text)

        btn = Gtk.Button(label="HEAL")
        btn.add_css_class("cta-danger")
        btn.connect("clicked", lambda _b, iss=issue: self._prompt_heal(iss))
        row.append(btn)
        return row

    def _refresh(self) -> bool:
        snap = self.engine.snapshot()
        self._last_snap = snap
        self.vitality.set_score(snap.score, snap.overall.value)
        self.wave.push(float(snap.score))

        by_kind = {m.kind: m for m in snap.metrics}

        if MetricKind.MEMORY in by_kind:
            m = by_kind[MetricKind.MEMORY]
            self.g_ram.update(m.value, m.unit, m.detail, m.threshold_warn, m.threshold_crit, "RAM")
        disk = next((m for m in snap.metrics if m.kind == MetricKind.DISK), None)
        if disk:
            self.g_disk.update(
                disk.value, disk.unit, disk.detail, disk.threshold_warn, disk.threshold_crit, "DISK"
            )
        if MetricKind.CPU in by_kind:
            m = by_kind[MetricKind.CPU]
            self.g_cpu.update(m.value, m.unit, m.detail, m.threshold_warn, m.threshold_crit, "CPU")
        if MetricKind.GPU in by_kind:
            m = by_kind[MetricKind.GPU]
            self.g_gpu.update(m.value, m.unit, m.detail, m.threshold_warn, m.threshold_crit, "GPU")
        if MetricKind.TEMP in by_kind:
            m = by_kind[MetricKind.TEMP]
            self.g_temp.update(m.value, m.unit, m.detail, m.threshold_warn, m.threshold_crit, "TEMP")
        if MetricKind.SWAP in by_kind:
            m = by_kind[MetricKind.SWAP]
            self.g_swap.update(m.value, m.unit, m.detail, m.threshold_warn, m.threshold_crit, "SWAP")

        self.status_label.remove_css_class("warn")
        self.status_label.remove_css_class("crit")
        if snap.overall == Severity.OK:
            self.status_label.set_text("ALL SYSTEMS NOMINAL")
        elif snap.overall == Severity.WARN:
            self.status_label.set_text("ANOMALY DETECTED")
            self.status_label.add_css_class("warn")
        else:
            self.status_label.set_text("CRITICAL — AWAITING YOUR YES / NO")
            self.status_label.add_css_class("crit")

        # Trouble log from active issues
        active_keys = []
        for issue in snap.issues:
            active_keys.append(issue.id)
            self.events.note_trouble(
                issue.id,
                issue.title,
                issue.description.split("\n")[0][:160],
                severity=issue.severity.value,
            )
        self.events.sync_active_troubles(active_keys)

        self._paint_logs()
        self.footer.set_text(
            f"{snap.score}/100 · {len(snap.metrics)} sensors · "
            f"{len(snap.issues)} active · autoheal "
            f"{'on' if self._autoheal_enabled else 'off'}"
        )

        if self._autoheal_enabled:
            for issue in snap.issues:
                if issue.severity != Severity.CRITICAL:
                    continue
                if issue.id in self._pending_issue_ids:
                    continue
                self._pending_issue_ids.add(issue.id)
                self._prompt_heal(issue)

        return True

    def _prompt_heal(self, issue: Issue) -> None:
        def on_decision(yes: bool) -> None:
            if not yes:
                self.events.note_declined(issue.title)
                self.toasts.show(f"Declined: {issue.title}", ok=False)
                self._paint_logs()
                GLib.timeout_add_seconds(
                    60, lambda: self._pending_issue_ids.discard(issue.id) or False
                )
                return
            self.toasts.show(f"Healing: {issue.heal_label}", ok=True)
            GLib.idle_add(self._run_heal, issue)

        ask_heal(self, issue, on_decision)

    def _run_heal(self, issue: Issue) -> bool:
        result = perform_heal(issue.heal_action)
        self.events.note_heal(
            issue.heal_label if result.ok else f"Failed — {issue.heal_label}",
            result.message,
            ok=result.ok,
        )
        self.toasts.show(result.message, ok=result.ok)
        self._pending_issue_ids.discard(issue.id)
        self.events.clear_trouble_key(issue.id)
        self._refresh()
        return False
