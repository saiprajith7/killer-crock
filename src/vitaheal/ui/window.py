"""Main VitaHeal HUD window."""

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
from vitaheal.ui.gauges import ArcGauge, PulseScore, WaveformStrip
from vitaheal.ui.heal_dialog import HealResultToast, ask_heal


CSS_PATH = Path(__file__).with_name("style.css")


class VitaHealWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, simulate: Optional[str] = None) -> None:
        super().__init__(application=app, title="VitaHeal")
        self.set_default_size(1100, 720)
        self.add_css_class("vitaheal-window")

        self.engine = HealthEngine(simulate=simulate)
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
        self.toast_overlay = Adw.ToastOverlay()
        self.toasts = HealResultToast(self.toast_overlay)
        self.set_content(self.toast_overlay)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.add_css_class("scanline")
        self.toast_overlay.set_child(outer)

        # —— Hero / brand first viewport ——
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero.set_margin_top(28)
        hero.set_margin_bottom(12)
        hero.set_margin_start(28)
        hero.set_margin_end(28)

        brand = Gtk.Label(label="VITAHEAL")
        brand.add_css_class("hero-brand")
        brand.set_halign(Gtk.Align.START)
        hero.append(brand)

        tag = Gtk.Label(label="OS-NATIVE · PULSE MONITOR · INTERACTIVE AUTOHEAL")
        tag.add_css_class("hero-tag")
        tag.set_halign(Gtk.Align.START)
        hero.append(tag)

        hero_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=28)
        hero_row.set_margin_top(12)

        self.pulse = PulseScore()
        hero_row.append(self.pulse)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.set_valign(Gtk.Align.CENTER)
        right.set_hexpand(True)

        self.status_label = Gtk.Label(label="SYSTEM NOMINAL")
        self.status_label.add_css_class("score-label")
        self.status_label.set_halign(Gtk.Align.START)
        right.append(self.status_label)

        self.blurb = Gtk.Label(
            label="Live vitals from your Debian machine. When something breaks, "
            "VitaHeal asks before it heals."
        )
        self.blurb.set_wrap(True)
        self.blurb.set_halign(Gtk.Align.START)
        self.blurb.set_xalign(0)
        right.append(self.blurb)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.scan_btn = Gtk.Button(label="FORCE SCAN")
        self.scan_btn.add_css_class("cta-primary")
        self.scan_btn.connect("clicked", lambda *_: self._refresh())
        btn_row.append(self.scan_btn)

        self.auto_btn = Gtk.ToggleButton(label="AUTOHEAL ARMED")
        self.auto_btn.add_css_class("cta-ghost")
        self.auto_btn.set_active(True)
        self.auto_btn.connect("toggled", self._on_auto_toggled)
        btn_row.append(self.auto_btn)
        right.append(btn_row)

        hero_row.append(right)
        hero.append(hero_row)

        self.wave = WaveformStrip()
        self.wave.set_margin_top(16)
        hero.append(self.wave)

        outer.append(hero)

        # —— Metrics deck ——
        deck = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        deck.set_margin_start(28)
        deck.set_margin_end(28)
        deck.set_margin_bottom(12)

        title = Gtk.Label(label="VITAL TELEMETRY")
        title.add_css_class("hud-title")
        title.set_halign(Gtk.Align.START)
        deck.append(title)

        gauges = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        gauges.set_homogeneous(True)
        self.g_cpu = ArcGauge("CPU")
        self.g_mem = ArcGauge("MEMORY")
        self.g_disk = ArcGauge("DISK")
        self.g_temp = ArcGauge("TEMP")
        self.g_net = ArcGauge("NET")
        for g in (self.g_cpu, self.g_mem, self.g_disk, self.g_temp, self.g_net):
            frame = Gtk.Box()
            frame.add_css_class("hud-panel")
            frame.append(g)
            gauges.append(frame)
        deck.append(gauges)
        outer.append(deck)

        # —— Issues / heal queue ——
        issues_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        issues_wrap.set_margin_start(28)
        issues_wrap.set_margin_end(28)
        issues_wrap.set_margin_bottom(24)
        issues_wrap.set_vexpand(True)

        it = Gtk.Label(label="HEAL QUEUE")
        it.add_css_class("hud-title")
        it.set_halign(Gtk.Align.START)
        issues_wrap.append(it)

        self.issues_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(160)
        scroll.set_child(self.issues_box)
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel.add_css_class("hud-panel")
        panel.append(scroll)
        issues_wrap.append(panel)

        self.ticker = Gtk.Label(label="SCANNER IDLE")
        self.ticker.add_css_class("ticker")
        self.ticker.set_halign(Gtk.Align.START)
        self.ticker.set_margin_top(8)
        issues_wrap.append(self.ticker)

        outer.append(issues_wrap)

    def _on_auto_toggled(self, btn: Gtk.ToggleButton) -> None:
        self._autoheal_enabled = btn.get_active()
        btn.set_label("AUTOHEAL ARMED" if self._autoheal_enabled else "AUTOHEAL SAFE")

    def _refresh(self) -> bool:
        snap = self.engine.snapshot()
        self._last_snap = snap
        self.pulse.set_score(snap.score, snap.overall.value)
        self.wave.push(float(snap.score))

        by_kind = {m.kind: m for m in snap.metrics}
        if MetricKind.CPU in by_kind:
            m = by_kind[MetricKind.CPU]
            self.g_cpu.update(m.value, m.unit, m.threshold_warn, m.threshold_crit, "CPU")
        if MetricKind.MEMORY in by_kind:
            m = by_kind[MetricKind.MEMORY]
            self.g_mem.update(m.value, m.unit, m.threshold_warn, m.threshold_crit, "MEMORY")
        disk = next((m for m in snap.metrics if m.kind == MetricKind.DISK), None)
        if disk:
            self.g_disk.update(disk.value, disk.unit, disk.threshold_warn, disk.threshold_crit, "DISK")
        if MetricKind.TEMP in by_kind:
            m = by_kind[MetricKind.TEMP]
            self.g_temp.update(m.value, m.unit, m.threshold_warn, m.threshold_crit, "TEMP")
        if MetricKind.NETWORK in by_kind:
            m = by_kind[MetricKind.NETWORK]
            self.g_net.update(m.value, m.unit, 50000, 100000, "NET")

        if snap.overall == Severity.OK:
            self.status_label.set_text("SYSTEM NOMINAL")
            self.status_label.remove_css_class("status-warn")
            self.status_label.remove_css_class("status-crit")
            self.status_label.add_css_class("status-ok")
        elif snap.overall == Severity.WARN:
            self.status_label.set_text("ANOMALY DETECTED")
            self.status_label.add_css_class("status-warn")
        else:
            self.status_label.set_text("CRITICAL — AWAITING HEAL DECISION")
            self.status_label.add_css_class("status-crit")

        self._rebuild_issues(snap.issues)
        self.ticker.set_text(
            f"PULSE {snap.score}/100 · {len(snap.metrics)} sensors · "
            f"{len(snap.issues)} issue(s) · autoheal "
            f"{'ARMED' if self._autoheal_enabled else 'SAFE'}"
        )

        if self._autoheal_enabled:
            for issue in snap.issues:
                if issue.severity != Severity.CRITICAL:
                    continue
                if issue.id in self._pending_issue_ids:
                    continue
                self._pending_issue_ids.add(issue.id)
                self._prompt_heal(issue)

        return True  # keep timer

    def _rebuild_issues(self, issues: list[Issue]) -> None:
        child = self.issues_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.issues_box.remove(child)
            child = nxt

        if not issues:
            ok = Gtk.Label(label="No active faults. Machine is breathing easy.")
            ok.set_halign(Gtk.Align.START)
            ok.add_css_class("status-ok")
            self.issues_box.append(ok)
            return

        for issue in issues:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.add_css_class("issue-row")
            if issue.severity == Severity.WARN:
                row.add_css_class("warn")

            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text.set_hexpand(True)
            t = Gtk.Label(label=issue.title)
            t.set_halign(Gtk.Align.START)
            t.add_css_class("metric-name")
            d = Gtk.Label(label=issue.description.split("\n")[0][:120])
            d.set_halign(Gtk.Align.START)
            d.add_css_class("metric-detail")
            d.set_wrap(True)
            text.append(t)
            text.append(d)
            row.append(text)

            btn = Gtk.Button(label="HEAL?")
            btn.add_css_class("cta-danger")
            btn.connect("clicked", lambda _b, iss=issue: self._prompt_heal(iss))
            row.append(btn)
            self.issues_box.append(row)

    def _prompt_heal(self, issue: Issue) -> None:
        def on_decision(yes: bool) -> None:
            if not yes:
                self.toasts.show(f"Heal declined for: {issue.title}", ok=False)
                # Allow re-prompt later
                GLib.timeout_add_seconds(60, lambda: self._pending_issue_ids.discard(issue.id) or False)
                return
            self.toasts.show(f"Executing: {issue.heal_label}…", ok=True)
            # Run heal off the tight UI path
            GLib.idle_add(self._run_heal, issue)

        ask_heal(self, issue, on_decision)

    def _run_heal(self, issue: Issue) -> bool:
        result = perform_heal(issue.heal_action)
        self.toasts.show(result.message, ok=result.ok)
        self._pending_issue_ids.discard(issue.id)
        self._refresh()
        return False
