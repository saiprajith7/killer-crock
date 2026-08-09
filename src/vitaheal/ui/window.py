"""Premium tabbed BOSS-Sentinel UI — Overview, CPU, Memory, Disk, GPU, Thermal, Logs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango  # noqa: E402

from vitaheal import APP_NAME, BRAND
from vitaheal.heal.actions import perform_heal
from vitaheal.monitor.engine import HealthEngine
from vitaheal.monitor.models import HealthSnapshot, Issue, MetricKind, Severity
from vitaheal.monitor.updates import UpdateStatus, list_upgradable, read_sources, summarize_packages
from vitaheal.ui.eventlog import EventLog
from vitaheal.ui.gauges import BreathWave, DeviceGraph, HeroVitality
from vitaheal.ui.heal_dialog import HealResultToast, ask_confirm, ask_heal

CSS_PATH = Path(__file__).with_name("style.css")


def _metric(snap: HealthSnapshot, kind: MetricKind):
    for m in snap.metrics:
        if m.kind == kind:
            return m
    return None


def _disk(snap: HealthSnapshot):
    for m in snap.metrics:
        if m.kind == MetricKind.DISK:
            return m
    return None


def _stat_tile(title: str) -> tuple[Gtk.Box, Gtk.Label, Gtk.Label]:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.add_css_class("stat-tile")
    t = Gtk.Label(label=title)
    t.add_css_class("stat-title")
    t.set_halign(Gtk.Align.START)
    v = Gtk.Label(label="—")
    v.add_css_class("stat-value")
    v.set_halign(Gtk.Align.START)
    d = Gtk.Label(label="")
    d.add_css_class("stat-detail")
    d.set_halign(Gtk.Align.START)
    d.set_wrap(True)
    d.set_xalign(0)
    box.append(t)
    box.append(v)
    box.append(d)
    return box, v, d


def _scrollable(child: Gtk.Widget) -> Gtk.ScrolledWindow:
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_hexpand(True)
    scroll.set_child(child)
    return scroll


def _section(title: str) -> Gtk.Label:
    lab = Gtk.Label(label=title)
    lab.add_css_class("section-label")
    lab.set_halign(Gtk.Align.START)
    return lab


class BOSS-SentinelWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, simulate: Optional[str] = None) -> None:
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(1240, 820)
        self.add_css_class("boss-sentinel-window")
        self.add_css_class("vitaheal-window")

        self.engine = HealthEngine(simulate=simulate)
        self.events = EventLog()
        self._pending_issue_ids: set[str] = set()
        self._autoheal_enabled = True
        self._last_snap: Optional[HealthSnapshot] = None
        self._update_status = UpdateStatus(sources=read_sources())
        self._update_busy = False

        self._load_css()
        self._build()
        # 3s refresh keeps UI light on modest hardware
        GLib.timeout_add_seconds(3, self._refresh)
        GLib.idle_add(self._refresh)

    def _load_css(self) -> None:
        css = Gtk.CssProvider()
        css.load_from_path(str(CSS_PATH))
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _set_root(self, widget: Gtk.Widget) -> None:
        if hasattr(self, "set_content"):
            self.set_content(widget)
        else:
            self.set_child(widget)

    def _build(self) -> None:
        self.toast_overlay = Adw.ToastOverlay()
        self.toasts = HealResultToast(self.toast_overlay)
        self._set_root(self.toast_overlay)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.toast_overlay.set_child(root)

        root.append(self._build_topbar())

        # Compact status strip
        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        status.add_css_class("status-strip")
        self.vitality = HeroVitality()
        status.append(self.vitality)
        st_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        st_col.set_valign(Gtk.Align.CENTER)
        st_col.set_hexpand(True)
        self.status_label = Gtk.Label(label="ALL SYSTEMS NOMINAL")
        self.status_label.add_css_class("hero-status")
        self.status_label.set_halign(Gtk.Align.START)
        self.blurb = Gtk.Label(
            label="Precision system vitals. Tabs for every subsystem. Scroll anywhere."
        )
        self.blurb.add_css_class("hero-line")
        self.blurb.set_halign(Gtk.Align.START)
        self.blurb.set_wrap(True)
        self.blurb.set_xalign(0)
        st_col.append(self.status_label)
        st_col.append(self.blurb)
        status.append(st_col)
        root.append(status)

        self.wave = BreathWave()
        self.wave.set_margin_start(20)
        self.wave.set_margin_end(20)
        root.append(self.wave)

        # Tabs
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher.add_css_class("tab-switcher")
        switcher.set_halign(Gtk.Align.FILL)
        switcher.set_hexpand(True)
        sw_wrap = Gtk.Box()
        sw_wrap.add_css_class("tab-bar")
        sw_wrap.append(switcher)
        root.append(sw_wrap)

        self.stack.add_titled(self._build_overview_tab(), "overview", "Overview")
        self.stack.add_titled(self._build_cpu_tab(), "cpu", "CPU")
        self.stack.add_titled(self._build_memory_tab(), "memory", "Memory")
        self.stack.add_titled(self._build_disk_tab(), "disk", "Disk")
        self.stack.add_titled(self._build_gpu_tab(), "gpu", "GPU")
        self.stack.add_titled(self._build_thermal_tab(), "thermal", "Thermal")
        self.stack.add_titled(self._build_updates_tab(), "updates", "Updates")
        self.stack.add_titled(self._build_logs_tab(), "logs", "Logs")
        root.append(self.stack)

        self.footer = Gtk.Label(label="")
        self.footer.add_css_class("footer-meta")
        self.footer.set_halign(Gtk.Align.START)
        root.append(self.footer)

        self._paint_logs()

    def _build_topbar(self) -> Gtk.Widget:
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top.add_css_class("topbar")
        brand_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        brand_col.set_hexpand(True)
        brand = Gtk.Label(label=BRAND)
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
        return top

    def _page(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.add_css_class("tab-page")
        box.set_margin_top(8)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        return box

    def _build_overview_tab(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("DEVICE HEALTH"))
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row1.set_homogeneous(True)
        self.ov_ram = DeviceGraph("RAM")
        self.ov_disk = DeviceGraph("DISK")
        self.ov_cpu = DeviceGraph("CPU")
        for g in (self.ov_ram, self.ov_disk, self.ov_cpu):
            cell = Gtk.Box()
            cell.add_css_class("device-cell")
            cell.append(g)
            row1.append(cell)
        page.append(row1)
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row2.set_homogeneous(True)
        self.ov_gpu = DeviceGraph("GPU")
        self.ov_temp = DeviceGraph("TEMP")
        self.ov_swap = DeviceGraph("SWAP")
        for g in (self.ov_gpu, self.ov_temp, self.ov_swap):
            cell = Gtk.Box()
            cell.add_css_class("device-cell")
            cell.append(g)
            row2.append(cell)
        page.append(row2)

        page.append(_section("ACTIVE ISSUES"))
        self.overview_issues = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        page.append(self.overview_issues)
        return _scrollable(page)

    def _build_cpu_tab(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("PROCESSOR"))
        tiles = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        tiles.set_homogeneous(True)
        self.cpu_util_tile, self.cpu_util_v, self.cpu_util_d = _stat_tile("UTILIZATION")
        self.cpu_cores_tile, self.cpu_cores_v, self.cpu_cores_d = _stat_tile("CORES")
        self.cpu_threads_tile, self.cpu_threads_v, self.cpu_threads_d = _stat_tile("THREADS")
        self.cpu_load_tile, self.cpu_load_v, self.cpu_load_d = _stat_tile("LOAD AVERAGE")
        for t in (
            self.cpu_util_tile,
            self.cpu_cores_tile,
            self.cpu_threads_tile,
            self.cpu_load_tile,
        ):
            tiles.append(t)
        page.append(tiles)

        self.cpu_model = Gtk.Label(label="")
        self.cpu_model.add_css_class("model-line")
        self.cpu_model.set_halign(Gtk.Align.START)
        self.cpu_model.set_wrap(True)
        self.cpu_model.set_xalign(0)
        page.append(self.cpu_model)

        page.append(_section("LIVE GRAPH"))
        self.cpu_graph = DeviceGraph("CPU")
        cell = Gtk.Box()
        cell.add_css_class("device-cell")
        cell.append(self.cpu_graph)
        page.append(cell)

        page.append(_section("PER-CORE USAGE"))
        self.core_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        page.append(self.core_box)
        return _scrollable(page)

    def _build_memory_tab(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("MEMORY"))
        tiles = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        tiles.set_homogeneous(True)
        self.mem_tile, self.mem_v, self.mem_d = _stat_tile("RAM")
        self.swap_tile, self.swap_v, self.swap_d = _stat_tile("SWAP")
        tiles.append(self.mem_tile)
        tiles.append(self.swap_tile)
        page.append(tiles)
        page.append(_section("LIVE GRAPHS"))
        graphs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        graphs.set_homogeneous(True)
        self.mem_graph = DeviceGraph("RAM")
        self.swap_graph = DeviceGraph("SWAP")
        for g in (self.mem_graph, self.swap_graph):
            cell = Gtk.Box()
            cell.add_css_class("device-cell")
            cell.append(g)
            graphs.append(cell)
        page.append(graphs)
        return _scrollable(page)

    def _build_disk_tab(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("STORAGE"))
        self.disk_tiles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.append(self.disk_tiles)
        page.append(_section("PRIMARY VOLUME GRAPH"))
        self.disk_graph = DeviceGraph("DISK")
        cell = Gtk.Box()
        cell.add_css_class("device-cell")
        cell.append(self.disk_graph)
        page.append(cell)
        return _scrollable(page)

    def _build_gpu_tab(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("GRAPHICS"))
        tiles = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        tiles.set_homogeneous(True)
        self.gpu_util_tile, self.gpu_util_v, self.gpu_util_d = _stat_tile("GPU UTIL")
        self.gpu_vram_tile, self.gpu_vram_v, self.gpu_vram_d = _stat_tile("VRAM")
        self.gpu_temp_tile, self.gpu_temp_v, self.gpu_temp_d = _stat_tile("GPU TEMP")
        self.gpu_power_tile, self.gpu_power_v, self.gpu_power_d = _stat_tile("POWER")
        for t in (
            self.gpu_util_tile,
            self.gpu_vram_tile,
            self.gpu_temp_tile,
            self.gpu_power_tile,
        ):
            tiles.append(t)
        page.append(tiles)
        self.gpu_name = Gtk.Label(label="No GPU detected")
        self.gpu_name.add_css_class("model-line")
        self.gpu_name.set_halign(Gtk.Align.START)
        self.gpu_name.set_wrap(True)
        self.gpu_name.set_xalign(0)
        page.append(self.gpu_name)
        page.append(_section("LIVE GRAPH"))
        self.gpu_graph = DeviceGraph("GPU")
        cell = Gtk.Box()
        cell.add_css_class("device-cell")
        cell.append(self.gpu_graph)
        page.append(cell)
        page.append(_section("ADAPTERS"))
        self.gpu_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        page.append(self.gpu_list)
        return _scrollable(page)

    def _build_thermal_tab(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("THERMAL"))
        self.therm_hot_tile, self.therm_hot_v, self.therm_hot_d = _stat_tile("HOTTEST")
        page.append(self.therm_hot_tile)
        page.append(_section("LIVE GRAPH"))
        self.therm_graph = DeviceGraph("TEMP")
        cell = Gtk.Box()
        cell.add_css_class("device-cell")
        cell.append(self.therm_graph)
        page.append(cell)
        page.append(_section("ALL SENSORS"))
        self.therm_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        page.append(self.therm_list)
        return _scrollable(page)

    def _build_updates_tab(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("SYSTEM UPDATES"))

        tiles = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        tiles.set_homogeneous(True)
        self.upd_count_tile, self.upd_count_v, self.upd_count_d = _stat_tile("AVAILABLE")
        self.upd_src_tile, self.upd_src_v, self.upd_src_d = _stat_tile("SOURCES")
        tiles.append(self.upd_count_tile)
        tiles.append(self.upd_src_tile)
        page.append(tiles)

        self.upd_summary = Gtk.Label(label="Press Check Updates to query your apt sources.")
        self.upd_summary.add_css_class("model-line")
        self.upd_summary.set_halign(Gtk.Align.START)
        self.upd_summary.set_wrap(True)
        self.upd_summary.set_xalign(0)
        page.append(self.upd_summary)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.upd_check_btn = Gtk.Button(label="CHECK UPDATES")
        self.upd_check_btn.add_css_class("cta-primary")
        self.upd_check_btn.connect("clicked", lambda *_: self._start_update_check(refresh=True))
        btns.append(self.upd_check_btn)

        self.upd_install_btn = Gtk.Button(label="INSTALL UPDATES")
        self.upd_install_btn.add_css_class("cta-ghost")
        self.upd_install_btn.set_sensitive(False)
        self.upd_install_btn.connect("clicked", lambda *_: self._prompt_install_updates())
        btns.append(self.upd_install_btn)
        page.append(btns)

        page.append(_section("CONFIGURED SOURCES (/etc/apt/sources.list*)"))
        self.upd_sources_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        page.append(self.upd_sources_box)

        page.append(_section("UPGRADABLE PACKAGES"))
        self.upd_pkg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        page.append(self.upd_pkg_box)

        # Populate sources immediately (cheap filesystem read)
        self._paint_update_sources()
        self.upd_src_v.set_text(str(len(self._update_status.sources)))
        self.upd_src_d.set_text("from sources.list + sources.list.d")
        self.upd_count_v.set_text("—")
        self.upd_count_d.set_text("not checked yet")
        return _scrollable(page)

    def _build_logs_tab(self) -> Gtk.Widget:
        """Logs has inner tabs: Trouble | Heal | Updates."""
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.add_css_class("tab-page")

        log_stack = Gtk.Stack()
        log_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        log_stack.set_vexpand(True)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(log_stack)
        switcher.add_css_class("log-switcher")
        switcher.set_halign(Gtk.Align.CENTER)
        bar = Gtk.Box()
        bar.add_css_class("log-tab-bar")
        bar.set_halign(Gtk.Align.CENTER)
        bar.append(switcher)
        outer.append(bar)

        t_page = self._page()
        t_page.append(_section("WHAT'S CAUSING TROUBLE"))
        self.trouble_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        t_page.append(self.trouble_box)
        log_stack.add_titled(_scrollable(t_page), "trouble", "Trouble Log")

        h_page = self._page()
        h_page.append(_section("WHAT BOSS-SENTINEL HEALED"))
        self.heal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        h_page.append(self.heal_box)
        log_stack.add_titled(_scrollable(h_page), "heal", "Heal Log")

        u_page = self._page()
        u_page.append(_section("SYSTEM UPDATE LOG"))
        self.update_log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        u_page.append(self.update_log_box)
        log_stack.add_titled(_scrollable(u_page), "updates", "Update Log")

        outer.append(log_stack)
        return outer

    def _on_auto_toggled(self, btn: Gtk.ToggleButton) -> None:
        self._autoheal_enabled = btn.get_active()
        btn.set_label("AUTOHEAL ON" if self._autoheal_enabled else "AUTOHEAL OFF")

    def _clear_box(self, box: Gtk.Box) -> None:
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt

    def _kv_row(self, left: str, right: str) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("kv-row")
        a = Gtk.Label(label=left)
        a.add_css_class("kv-left")
        a.set_halign(Gtk.Align.START)
        a.set_hexpand(True)
        a.set_ellipsize(Pango.EllipsizeMode.END)
        b = Gtk.Label(label=right)
        b.add_css_class("kv-right")
        b.set_halign(Gtk.Align.END)
        row.append(a)
        row.append(b)
        return row

    def _core_bar(self, index: int, pct: float) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("core-row")
        lab = Gtk.Label(label=f"CPU{index}")
        lab.add_css_class("core-label")
        lab.set_width_chars(5)
        lab.set_halign(Gtk.Align.START)
        bar = Gtk.LevelBar()
        bar.set_min_value(0)
        bar.set_max_value(100)
        bar.set_value(pct)
        bar.set_hexpand(True)
        bar.add_css_class("core-bar")
        val = Gtk.Label(label=f"{pct:.0f}%")
        val.add_css_class("core-val")
        val.set_width_chars(4)
        row.append(lab)
        row.append(bar)
        row.append(val)
        return row

    def _paint_logs(self) -> None:
        self._clear_box(self.trouble_box)
        self._clear_box(self.heal_box)
        self._clear_box(self.update_log_box)

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
            for entry in hist[:80]:
                self.trouble_box.append(self._log_row(entry.clock, entry.title, entry.detail))

        heals = self.events.heal
        if not heals:
            empty = Gtk.Label(label="No heal actions yet.")
            empty.add_css_class("log-empty")
            empty.set_halign(Gtk.Align.START)
            self.heal_box.append(empty)
        else:
            for entry in heals[:80]:
                self.heal_box.append(self._log_row(entry.clock, entry.title, entry.detail))

        updates = self.events.update
        if not updates:
            empty = Gtk.Label(label="No system update activity yet.")
            empty.add_css_class("log-empty")
            empty.set_halign(Gtk.Align.START)
            self.update_log_box.append(empty)
        else:
            for entry in updates[:80]:
                self.update_log_box.append(self._log_row(entry.clock, entry.title, entry.detail))

    def _paint_update_sources(self) -> None:
        self._clear_box(self.upd_sources_box)
        sources = self._update_status.sources or read_sources()
        self._update_status.sources = sources
        if not sources:
            empty = Gtk.Label(label="No apt sources found under /etc/apt/.")
            empty.add_css_class("log-empty")
            empty.set_halign(Gtk.Align.START)
            self.upd_sources_box.append(empty)
            return
        for src in sources[:40]:
            flag = "ON" if src.enabled else "OFF"
            self.upd_sources_box.append(
                self._kv_row(f"{src.file} [{flag}]", src.line[:90])
            )

    def _paint_update_packages(self) -> None:
        self._clear_box(self.upd_pkg_box)
        pkgs = self._update_status.packages
        if self._update_status.last_error:
            err = Gtk.Label(label=self._update_status.last_error)
            err.add_css_class("log-empty")
            err.set_halign(Gtk.Align.START)
            err.set_wrap(True)
            err.set_xalign(0)
            self.upd_pkg_box.append(err)
        if not pkgs:
            empty = Gtk.Label(label="No upgradable packages (indexes may need refresh).")
            empty.add_css_class("log-empty")
            empty.set_halign(Gtk.Align.START)
            self.upd_pkg_box.append(empty)
            return
        for pkg in pkgs[:80]:
            self.upd_pkg_box.append(
                self._kv_row(pkg.name, f"{pkg.current} → {pkg.candidate}")
            )

    def _start_update_check(self, refresh: bool = True) -> None:
        if self._update_busy:
            return
        import threading

        self._update_busy = True
        self.upd_check_btn.set_sensitive(False)
        self.upd_install_btn.set_sensitive(False)
        self.upd_summary.set_text("Checking apt sources…")
        self.events.note_update(
            "Checking for updates",
            "Reading sources.list and querying apt indexes",
            ok=True,
        )
        self._paint_logs()

        def work() -> None:
            if refresh:
                result = perform_heal("apt_update")
                self.events.note_update(
                    "apt-get update",
                    result.message + (f" — {result.details}" if result.details else ""),
                    ok=result.ok,
                )
            status = list_upgradable(refresh_index=False)
            GLib.idle_add(self._finish_update_check, status, True)

        threading.Thread(target=work, daemon=True).start()

    def _finish_update_check(
        self, status: UpdateStatus, prompt_if_available: bool = True
    ) -> bool:
        self._update_status = status
        self._update_busy = False
        self.upd_check_btn.set_sensitive(True)
        self.upd_src_v.set_text(str(len(status.sources)))
        self.upd_src_d.set_text("from sources.list + sources.list.d")
        self.upd_count_v.set_text(str(status.count))
        self.upd_count_d.set_text("upgradable packages")
        self.upd_summary.set_text(summarize_packages(status.packages))
        self.upd_install_btn.set_sensitive(status.count > 0)
        self._paint_update_sources()
        self._paint_update_packages()
        self.events.note_update(
            f"Update check complete — {status.count} available",
            summarize_packages(status.packages, limit=20),
            ok=not bool(status.last_error),
        )
        self._paint_logs()
        if status.count > 0:
            self.toasts.show(f"{status.count} update(s) available", ok=True)
            if prompt_if_available:
                self._prompt_install_updates()
        elif status.last_error:
            self.toasts.show(status.last_error, ok=False)
        else:
            self.toasts.show("System is up to date", ok=True)
        return False

    def _prompt_install_updates(self) -> None:
        status = self._update_status
        if status.count <= 0:
            self.toasts.show("No updates to install", ok=True)
            return
        summary = summarize_packages(status.packages, limit=15)

        def on_decision(yes: bool) -> None:
            if not yes:
                self.events.note_update(
                    "Updates declined",
                    f"User chose No — {status.count} package(s) left pending",
                    ok=False,
                )
                self._paint_logs()
                self.toasts.show("Updates declined", ok=False)
                return
            self.events.note_update("Installing updates", summary, ok=True)
            self._paint_logs()
            self.toasts.show("Installing updates…", ok=True)
            self.upd_install_btn.set_sensitive(False)
            self.upd_check_btn.set_sensitive(False)
            GLib.idle_add(self._run_apt_upgrade)

        ask_confirm(
            self,
            "BOSS-SENTINEL — System updates available",
            f"{summary}\n\n"
            "These come from your configured apt repositories "
            "(/etc/apt/sources.list and sources.list.d).\n\n"
            "Do you want BOSS-Sentinel to install them now?",
            on_decision,
            yes_label="Yes — Install updates",
            no_label="No",
        )

    def _run_apt_upgrade(self) -> bool:
        import threading

        def work() -> None:
            result = perform_heal("apt_upgrade")
            self.events.note_update(
                "apt-get upgrade" if result.ok else "Upgrade failed",
                result.message + (f" — {result.details}" if result.details else ""),
                ok=result.ok,
            )
            status = list_upgradable(refresh_index=False)
            GLib.idle_add(self._after_upgrade, result.ok, result.message, status)

        threading.Thread(target=work, daemon=True).start()
        return False

    def _after_upgrade(self, ok: bool, message: str, status: UpdateStatus) -> bool:
        self.toasts.show(message, ok=ok)
        self._paint_logs()
        self._finish_update_check(status, prompt_if_available=False)
        return False

    def _log_row(self, clock: str, title: str, detail: str) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        row.add_css_class("log-row")
        t = Gtk.Label(label=f"{clock}  {title}")
        t.add_css_class("log-head")
        t.set_halign(Gtk.Align.START)
        t.set_wrap(True)
        t.set_xalign(0)
        d = Gtk.Label(label=detail[:160])
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
        d = Gtk.Label(label=issue.description.split("\n")[0][:120])
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

        mem = _metric(snap, MetricKind.MEMORY)
        swap = _metric(snap, MetricKind.SWAP)
        cpu = _metric(snap, MetricKind.CPU)
        load = _metric(snap, MetricKind.LOAD)
        disk = _disk(snap)
        gpu = _metric(snap, MetricKind.GPU)
        gpu_mem = _metric(snap, MetricKind.GPU_MEM)
        gpu_temp = _metric(snap, MetricKind.GPU_TEMP)
        temp = _metric(snap, MetricKind.TEMP)

        # Overview graphs
        if mem:
            self.ov_ram.update(mem.value, mem.unit, mem.detail, mem.threshold_warn, mem.threshold_crit, "RAM")
            self.mem_graph.update(mem.value, mem.unit, mem.detail, mem.threshold_warn, mem.threshold_crit, "RAM")
            self.mem_v.set_text(f"{mem.value:.0f}%")
            self.mem_d.set_text(mem.detail)
        if disk:
            self.ov_disk.update(disk.value, disk.unit, disk.detail, disk.threshold_warn, disk.threshold_crit, "DISK")
            self.disk_graph.update(disk.value, disk.unit, disk.detail, disk.threshold_warn, disk.threshold_crit, "DISK")
        if cpu:
            self.ov_cpu.update(cpu.value, cpu.unit, cpu.detail, cpu.threshold_warn, cpu.threshold_crit, "CPU")
            self.cpu_graph.update(cpu.value, cpu.unit, cpu.detail, cpu.threshold_warn, cpu.threshold_crit, "CPU")
            self.cpu_util_v.set_text(f"{cpu.value:.0f}%")
            self.cpu_util_d.set_text(cpu.severity.value.upper())
        if gpu:
            self.ov_gpu.update(gpu.value, gpu.unit, gpu.detail, gpu.threshold_warn, gpu.threshold_crit, "GPU")
            self.gpu_graph.update(gpu.value, gpu.unit, gpu.detail, gpu.threshold_warn, gpu.threshold_crit, "GPU")
            self.gpu_util_v.set_text(f"{gpu.value:.0f}%")
            self.gpu_util_d.set_text(gpu.detail.split("·")[0].strip()[:40])
        if temp:
            self.ov_temp.update(temp.value, temp.unit, temp.detail, temp.threshold_warn, temp.threshold_crit, "TEMP")
            self.therm_graph.update(temp.value, temp.unit, temp.detail, temp.threshold_warn, temp.threshold_crit, "TEMP")
            self.therm_hot_v.set_text(f"{temp.value:.0f}°C")
            self.therm_hot_d.set_text(temp.detail.split("·")[0].strip())
        if swap:
            self.ov_swap.update(swap.value, swap.unit, swap.detail, swap.threshold_warn, swap.threshold_crit, "SWAP")
            self.swap_graph.update(swap.value, swap.unit, swap.detail, swap.threshold_warn, swap.threshold_crit, "SWAP")
            self.swap_v.set_text(f"{swap.value:.0f}%")
            self.swap_d.set_text(swap.detail)

        # CPU topology
        topo = self.engine.cpu.topology
        self.cpu_cores_v.set_text(str(topo.physical_cores))
        self.cpu_cores_d.set_text("physical cores")
        self.cpu_threads_v.set_text(str(topo.logical_threads))
        self.cpu_threads_d.set_text("logical threads")
        if load:
            self.cpu_load_v.set_text(f"{topo.load1:.2f}")
            self.cpu_load_d.set_text(f"5m {topo.load5:.2f} · 15m {topo.load15:.2f}")
        self.cpu_model.set_text(topo.model)

        self._clear_box(self.core_box)
        if topo.per_core:
            for i, pct in enumerate(topo.per_core):
                self.core_box.append(self._core_bar(i, pct))
        else:
            empty = Gtk.Label(label="Per-core stats unavailable on this host.")
            empty.add_css_class("log-empty")
            empty.set_halign(Gtk.Align.START)
            self.core_box.append(empty)

        # Disk list
        self._clear_box(self.disk_tiles)
        disks = [m for m in snap.metrics if m.kind in {MetricKind.DISK, MetricKind.INODE}]
        if not disks:
            self.disk_tiles.append(Gtk.Label(label="No volumes found", xalign=0))
        else:
            for m in disks:
                self.disk_tiles.append(
                    self._kv_row(m.label, f"{m.value:.0f}{m.unit}  ·  {m.detail}")
                )

        # GPU details
        gpus = self.engine.gpu.gpus
        self._clear_box(self.gpu_list)
        if not gpus:
            self.gpu_name.set_text("No discrete/integrated GPU metrics exposed")
            self.gpu_vram_v.set_text("—")
            self.gpu_temp_v.set_text("—")
            self.gpu_power_v.set_text("—")
            self.gpu_vram_d.set_text("")
            self.gpu_temp_d.set_text("")
            self.gpu_power_d.set_text("")
            miss = Gtk.Label(label="Install nvidia drivers or expose amdgpu sysfs for full GPU telemetry.")
            miss.add_css_class("log-empty")
            miss.set_halign(Gtk.Align.START)
            self.gpu_list.append(miss)
        else:
            g0 = gpus[0]
            self.gpu_name.set_text(f"{g0.vendor.upper()} · {g0.name}")
            if g0.mem_total_mb > 0:
                pct = g0.mem_used_mb / g0.mem_total_mb * 100
                self.gpu_vram_v.set_text(f"{pct:.0f}%")
                self.gpu_vram_d.set_text(f"{g0.mem_used_mb:.0f} / {g0.mem_total_mb:.0f} MB")
            elif gpu_mem:
                self.gpu_vram_v.set_text(f"{gpu_mem.value:.0f}%")
                self.gpu_vram_d.set_text(gpu_mem.detail)
            else:
                self.gpu_vram_v.set_text("n/a")
                self.gpu_vram_d.set_text("VRAM not reported")
            if g0.temp_c is not None:
                self.gpu_temp_v.set_text(f"{g0.temp_c:.0f}°C")
                self.gpu_temp_d.set_text("adapter sensor")
            elif gpu_temp:
                self.gpu_temp_v.set_text(f"{gpu_temp.value:.0f}°C")
                self.gpu_temp_d.set_text(gpu_temp.detail)
            else:
                self.gpu_temp_v.set_text("n/a")
                self.gpu_temp_d.set_text("")
            if g0.power_w is not None:
                self.gpu_power_v.set_text(f"{g0.power_w:.0f}W")
                self.gpu_power_d.set_text("draw")
            else:
                self.gpu_power_v.set_text("n/a")
                self.gpu_power_d.set_text("")
            for i, g in enumerate(gpus):
                line = f"{g.name} · util {g.util:.0f}%"
                if g.temp_c is not None:
                    line += f" · {g.temp_c:.0f}°C"
                if g.mem_total_mb > 0:
                    line += f" · VRAM {g.mem_used_mb:.0f}/{g.mem_total_mb:.0f} MB"
                if g.power_w is not None:
                    line += f" · {g.power_w:.0f}W"
                self.gpu_list.append(self._kv_row(f"GPU {i}", line))

        # Thermal sensors
        self._clear_box(self.therm_list)
        sensors = self.engine.temp.state.sensors
        if not sensors:
            empty = Gtk.Label(label="No thermal sensors exposed via sysfs.")
            empty.add_css_class("log-empty")
            empty.set_halign(Gtk.Align.START)
            self.therm_list.append(empty)
        else:
            for s in sorted(sensors, key=lambda x: x.celsius, reverse=True):
                self.therm_list.append(self._kv_row(s.name, f"{s.celsius:.1f}°C"))

        # Status
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

        # Overview issues
        self._clear_box(self.overview_issues)
        if not snap.issues:
            ok = Gtk.Label(label="No active faults.")
            ok.add_css_class("log-empty")
            ok.set_halign(Gtk.Align.START)
            self.overview_issues.append(ok)
        else:
            for issue in snap.issues:
                self.overview_issues.append(self._issue_row(issue))

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
            f"{topo.physical_cores}C/{topo.logical_threads}T · "
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
