"""BOSS-Optimize main window — tabs for services, processes, packages, I/O, optimize."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango  # noqa: E402

from bossoptimize import APP_NAME, BRAND
from bossoptimize.monitor.engine import OptimizeEngine
from bossoptimize.monitor.models import PerformanceSnapshot
from bossoptimize.optimize.actions import apply_plan

CSS_PATH = Path(__file__).with_name("style.css")


def _bytes_human(n: float) -> str:
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    v = float(n)
    for u in units:
        if v < 1024 or u == units[-1]:
            return f"{v:.1f} {u}"
        v /= 1024.0
    return f"{n:.0f} B/s"


def _chip(title: str) -> tuple[Gtk.Box, Gtk.Label]:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.add_css_class("metric-chip")
    box.set_hexpand(True)
    t = Gtk.Label(label=title, xalign=0)
    t.add_css_class("metric-title")
    v = Gtk.Label(label="—", xalign=0)
    v.add_css_class("metric-value")
    box.append(t)
    box.append(v)
    return box, v


def _section(title: str) -> Gtk.Label:
    lab = Gtk.Label(label=title, xalign=0)
    lab.add_css_class("section-label")
    return lab


def _scroll(child: Gtk.Widget) -> Gtk.ScrolledWindow:
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_hexpand(True)
    try:
        scroll.set_kinetic_scrolling(True)
    except AttributeError:
        pass
    scroll.add_css_class("smooth-scroll")
    scroll.set_child(child)
    return scroll


class OptimizeWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(1280, 860)
        self.add_css_class("boss-optimize-window")

        self.engine = OptimizeEngine()
        self._last: PerformanceSnapshot | None = None
        self._plan: dict | None = None
        self._busy = False

        self._load_css()
        self._build()
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
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._set_root(root)
        root.append(self._build_topbar())

        status = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        status.add_css_class("status-strip")
        self.status_label = Gtk.Label(label="SCANNING SYSTEM PERFORMANCE", xalign=0)
        self.status_label.add_css_class("hero-status")
        self.blurb = Gtk.Label(
            label="Services · processes · packages · disk I/O · GPU · optimize allotment",
            xalign=0,
        )
        self.blurb.add_css_class("hero-line")
        self.blurb.set_wrap(True)
        status.append(self.status_label)
        status.append(self.blurb)
        root.append(status)

        metrics = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        metrics.add_css_class("metric-row")
        self.chip_cpu_box, self.chip_cpu = _chip("CPU")
        self.chip_ram_box, self.chip_ram = _chip("RAM")
        self.chip_io_box, self.chip_io = _chip("DISK I/O")
        self.chip_gpu_box, self.chip_gpu = _chip("GPU")
        for w in (self.chip_cpu_box, self.chip_ram_box, self.chip_io_box, self.chip_gpu_box):
            metrics.append(w)
        root.append(metrics)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_vexpand(True)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher.add_css_class("tab-switcher")
        switcher.set_hexpand(True)
        bar = Gtk.Box()
        bar.add_css_class("tab-bar")
        bar.append(switcher)
        root.append(bar)

        self.stack.add_titled(self._build_overview(), "overview", "Overview")
        self.stack.add_titled(self._build_services(), "services", "Services")
        self.stack.add_titled(self._build_processes(), "processes", "Processes")
        self.stack.add_titled(self._build_packages(), "packages", "Packages")
        self.stack.add_titled(self._build_io(), "io", "Storage I/O")
        self.stack.add_titled(self._build_optimize(), "optimize", "Optimize")
        root.append(self.stack)

        self.footer = Gtk.Label(label="", xalign=0)
        self.footer.add_css_class("footer-meta")
        root.append(self.footer)

    def _build_topbar(self) -> Gtk.Widget:
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top.add_css_class("topbar")
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        col.set_hexpand(True)
        brand = Gtk.Label(label=BRAND, xalign=0)
        brand.add_css_class("brand")
        sub = Gtk.Label(label="PERFORMANCE · ALLOT HARDWARE", xalign=0)
        sub.add_css_class("brand-sub")
        col.append(brand)
        col.append(sub)
        top.append(col)
        close_btn = Gtk.Button(label="×")
        close_btn.add_css_class("close-x")
        close_btn.set_tooltip_text("Close")
        close_btn.connect("clicked", lambda *_: self.close())
        top.append(close_btn)
        return top

    def _page(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.add_css_class("tab-page")
        box.set_margin_start(16)
        box.set_margin_end(16)
        return box

    def _build_overview(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("LIVE SNAPSHOT"))
        self.ov_summary = Gtk.Label(label="Collecting…", xalign=0)
        self.ov_summary.set_wrap(True)
        page.append(self.ov_summary)
        page.append(_section("RUNNING APPLICATIONS (TOP)"))
        self.ov_list = Gtk.ListBox()
        self.ov_list.add_css_class("list-frame")
        self.ov_list.set_selection_mode(Gtk.SelectionMode.NONE)
        page.append(_scroll(self.ov_list))
        return page

    def _build_services(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("SYSTEMD SERVICES"))
        self.svc_hint = Gtk.Label(label="", xalign=0)
        self.svc_hint.add_css_class("hero-line")
        page.append(self.svc_hint)
        self.svc_list = Gtk.ListBox()
        self.svc_list.add_css_class("list-frame")
        self.svc_list.set_selection_mode(Gtk.SelectionMode.NONE)
        page.append(_scroll(self.svc_list))
        return page

    def _build_processes(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("ALL PROCESSES — CPU · RAM · I/O · GPU"))
        self.proc_hint = Gtk.Label(label="", xalign=0)
        self.proc_hint.add_css_class("hero-line")
        page.append(self.proc_hint)
        self.proc_list = Gtk.ListBox()
        self.proc_list.add_css_class("list-frame")
        self.proc_list.set_selection_mode(Gtk.SelectionMode.NONE)
        page.append(_scroll(self.proc_list))
        return page

    def _build_packages(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("PACKAGES + RUNNING / BACKGROUND"))
        self.pkg_hint = Gtk.Label(label="", xalign=0)
        self.pkg_hint.add_css_class("hero-line")
        page.append(self.pkg_hint)
        self.pkg_list = Gtk.ListBox()
        self.pkg_list.add_css_class("list-frame")
        self.pkg_list.set_selection_mode(Gtk.SelectionMode.NONE)
        page.append(_scroll(self.pkg_list))
        return page

    def _build_io(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("STORAGE (HDD / SSD / NVMe) + THROUGHPUT"))
        self.io_hint = Gtk.Label(label="", xalign=0)
        self.io_hint.add_css_class("hero-line")
        page.append(self.io_hint)
        self.io_list = Gtk.ListBox()
        self.io_list.add_css_class("list-frame")
        self.io_list.set_selection_mode(Gtk.SelectionMode.NONE)
        page.append(_scroll(self.io_list))
        page.append(_section("TOP I/O PROCESSES"))
        self.io_proc_list = Gtk.ListBox()
        self.io_proc_list.add_css_class("list-frame")
        self.io_proc_list.set_selection_mode(Gtk.SelectionMode.NONE)
        page.append(_scroll(self.io_proc_list))
        return page

    def _build_optimize(self) -> Gtk.Widget:
        page = self._page()
        page.append(_section("OPTIMIZE PERFORMANCE"))
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("optimize-card")
        self.opt_title = Gtk.Label(label="Ready to allot hardware to active work?", xalign=0)
        self.opt_title.add_css_class("optimize-title")
        self.opt_body = Gtk.Label(
            label="Review the plan below. Choosing YES applies CPU/I/O/memory allotment "
            "(password prompt may appear).",
            xalign=0,
        )
        self.opt_body.add_css_class("optimize-body")
        self.opt_body.set_wrap(True)
        card.append(self.opt_title)
        card.append(self.opt_body)

        self.opt_plan_list = Gtk.ListBox()
        self.opt_plan_list.add_css_class("list-frame")
        self.opt_plan_list.set_selection_mode(Gtk.SelectionMode.NONE)
        card.append(self.opt_plan_list)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.btn_yes = Gtk.Button(label="YES — Optimize now")
        self.btn_yes.add_css_class("opt-yes")
        self.btn_yes.connect("clicked", self._on_optimize_yes)
        self.btn_no = Gtk.Button(label="NO — Keep current allotment")
        self.btn_no.add_css_class("opt-no")
        self.btn_no.connect("clicked", self._on_optimize_no)
        self.btn_refresh_plan = Gtk.Button(label="Refresh plan")
        self.btn_refresh_plan.connect("clicked", lambda *_: self._paint_optimize(force=True))
        btns.append(self.btn_yes)
        btns.append(self.btn_no)
        btns.append(self.btn_refresh_plan)
        card.append(btns)

        self.opt_result = Gtk.Label(label="", xalign=0)
        self.opt_result.add_css_class("optimize-body")
        self.opt_result.set_wrap(True)
        card.append(self.opt_result)
        page.append(card)
        return _scroll(page)

    def _clear_list(self, listbox: Gtk.ListBox) -> None:
        child = listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            listbox.remove(child)
            child = nxt

    def _row(self, title: str, subtitle: str, badge: str = "", badge_class: str = "badge") -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(10)
        box.set_margin_end(10)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        col.set_hexpand(True)
        t = Gtk.Label(label=title, xalign=0)
        t.add_css_class("row-title")
        t.set_ellipsize(Pango.EllipsizeMode.END)
        s = Gtk.Label(label=subtitle, xalign=0)
        s.add_css_class("row-sub")
        s.set_ellipsize(Pango.EllipsizeMode.END)
        col.append(t)
        col.append(s)
        box.append(col)
        if badge:
            b = Gtk.Label(label=badge)
            b.add_css_class(badge_class)
            box.append(b)
        row.set_child(box)
        return row

    def _refresh(self) -> bool:
        try:
            snap = self.engine.snapshot()
        except Exception as exc:  # noqa: BLE001
            self.status_label.set_text(f"SCAN ERROR: {exc}")
            return True
        self._last = snap
        self._paint(snap)
        return True

    def _paint(self, snap: PerformanceSnapshot) -> None:
        self.chip_cpu.set_text(f"{snap.cpu_percent:.0f}%")
        self.chip_ram.set_text(f"{snap.mem_percent:.0f}%")
        self.chip_io.set_text(
            f"R {_bytes_human(snap.io_read_bps)} · W {_bytes_human(snap.io_write_bps)}"
        )
        if snap.gpu and snap.gpu.available:
            self.chip_gpu.set_text(f"{snap.gpu.util_percent:.0f}%")
        else:
            self.chip_gpu.set_text("n/a")

        running_svc = sum(1 for s in snap.services if s.running)
        self.status_label.set_text("PERFORMANCE MONITOR ACTIVE")
        self.blurb.set_text(
            f"{running_svc} services running · {len(snap.processes)} processes · "
            f"{snap.background_count} background · {snap.packages_total} packages installed"
        )

        # Overview
        self.ov_summary.set_text(
            f"Load {snap.load1} on {snap.threads} threads · "
            f"RAM {snap.mem_used_gb}/{snap.mem_total_gb} GB · "
            f"Swap {snap.swap_percent:.0f}% · "
            f"GPU {snap.gpu.name if snap.gpu else 'n/a'}"
        )
        self._clear_list(self.ov_list)
        for p in snap.processes[:12]:
            badge = "BACKGROUND" if p.background else "ACTIVE"
            bcls = "badge badge-bg" if p.background else "badge"
            self.ov_list.append(
                self._row(
                    f"{p.name}  pid {p.pid}",
                    f"CPU {p.cpu_percent}% · RAM {p.mem_rss_mb} MB ({p.mem_percent}%) · "
                    f"I/O {_bytes_human(p.io_total_bps)} · GPU {p.gpu_percent}%",
                    badge,
                    bcls,
                )
            )

        # Services
        self.svc_hint.set_text(f"{running_svc} running / {len(snap.services)} listed")
        self._clear_list(self.svc_list)
        for s in snap.services[:180]:
            badge = "RUNNING" if s.running else s.active.upper()
            bcls = "badge" if s.running else "badge badge-off"
            self.svc_list.append(
                self._row(s.name, f"{s.sub} — {s.description}", badge, bcls)
            )

        # Processes
        self.proc_hint.set_text(
            f"Showing top {len(snap.processes)} · foreground {snap.foreground_count} · "
            f"background {snap.background_count}"
        )
        self._clear_list(self.proc_list)
        for p in snap.processes[:200]:
            badge = "BG" if p.background else "FG"
            bcls = "badge badge-bg" if p.background else "badge"
            self.proc_list.append(
                self._row(
                    f"{p.name}  [{p.user}]  pid {p.pid}",
                    f"CPU {p.cpu_percent}% · RAM {p.mem_rss_mb} MB · "
                    f"R/W {_bytes_human(p.io_total_bps)} · GPU {p.gpu_percent}% · {p.state}",
                    badge,
                    bcls,
                )
            )

        # Packages
        running_pkgs = [p for p in snap.packages_running]
        self.pkg_hint.set_text(
            f"{len(running_pkgs)} packages mapped to running processes · "
            f"{snap.packages_total} installed total"
        )
        self._clear_list(self.pkg_list)
        # Prefer running first already sorted by engine helper
        show = running_pkgs[:120]
        # Also show a few not-running from a second query list if present in snapshot — only running stored
        for p in show:
            if p.running and p.background:
                badge, bcls = "BG RUNNING", "badge badge-bg"
            elif p.running:
                badge, bcls = "RUNNING", "badge"
            else:
                badge, bcls = "INSTALLED", "badge badge-off"
            pids = ",".join(str(x) for x in p.pids[:6]) or "—"
            self.pkg_list.append(
                self._row(
                    f"{p.name}  {p.version}",
                    f"{p.status} · pids {pids}",
                    badge,
                    bcls,
                )
            )

        # I/O disks
        self.io_hint.set_text(
            f"Aggregate read {_bytes_human(snap.io_read_bps)} · "
            f"write {_bytes_human(snap.io_write_bps)}"
        )
        self._clear_list(self.io_list)
        for d in snap.disks:
            self.io_list.append(
                self._row(
                    f"{d.mount}  ({d.kind})",
                    f"{d.device} · {d.fstype} · {d.used_gb}/{d.total_gb} GB ({d.used_percent}%) · "
                    f"R {_bytes_human(d.read_bps)} · W {_bytes_human(d.write_bps)}",
                    d.kind,
                    "badge",
                )
            )
        self._clear_list(self.io_proc_list)
        io_procs = sorted(snap.processes, key=lambda p: p.io_total_bps, reverse=True)[:40]
        for p in io_procs:
            if p.io_total_bps <= 0 and p.read_bytes == 0:
                continue
            self.io_proc_list.append(
                self._row(
                    f"{p.name}  pid {p.pid}",
                    f"Throughput {_bytes_human(p.io_total_bps)} · "
                    f"read {p.read_bytes} B · write {p.write_bytes} B",
                    "BG" if p.background else "FG",
                    "badge badge-bg" if p.background else "badge",
                )
            )

        self._paint_optimize(force=False)
        self.footer.set_text(
            f"BOSS-Optimize · refreshed · CPU {snap.cpu_percent}% · RAM {snap.mem_percent}%"
        )

    def _paint_optimize(self, force: bool = False) -> None:
        if self._busy:
            return
        if self._last is None:
            return
        if force or self._plan is None:
            self._plan = self.engine.build_optimize_plan(self._last)
        plan = self._plan
        self.opt_title.set_text("Optimize performance — allot hardware?")
        self.opt_body.set_text(plan.get("summary", ""))
        self._clear_list(self.opt_plan_list)
        for a in plan.get("actions", []):
            self.opt_plan_list.append(
                self._row(
                    a.get("title", a.get("id", "action")),
                    a.get("detail", ""),
                    a.get("impact", "").upper(),
                    "badge",
                )
            )

    def _on_optimize_no(self, *_args) -> None:
        self.opt_result.set_text("No changes applied. Monitoring continues with current allotment.")

    def _on_optimize_yes(self, *_args) -> None:
        if self._busy or self._last is None:
            return
        self._busy = True
        self.btn_yes.set_sensitive(False)
        self.opt_result.set_text("Applying optimization plan… approve the admin prompt if asked.")

        snap = self._last
        plan = self._plan or self.engine.build_optimize_plan(snap)
        action_ids = [a["id"] for a in plan.get("actions", [])]
        renice_pids = [
            p.pid
            for p in snap.processes
            if p.background and (p.cpu_percent >= 15.0 or p.mem_percent >= 5.0)
        ][:12]
        ionice_pids = [
            p.pid
            for p in sorted(snap.processes, key=lambda x: x.io_total_bps, reverse=True)
            if p.background and p.io_total_bps > 2_000_000
        ][:12]

        def work() -> None:
            results = apply_plan(action_ids, renice_pids=renice_pids, ionice_pids=ionice_pids)
            lines = []
            for r in results:
                mark = "OK" if r.ok else "FAIL"
                lines.append(f"[{mark}] {r.action}: {r.message}")
            text = "\n".join(lines) if lines else "No actions ran."

            def done() -> None:
                self.opt_result.set_text(text)
                self._busy = False
                self.btn_yes.set_sensitive(True)
                self._plan = None
                self._refresh()

            GLib.idle_add(done)

        import threading

        threading.Thread(target=work, daemon=True).start()
