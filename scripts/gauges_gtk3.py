#!/usr/bin/env python3
"""GTK3 Cairo gauges — port of confirmed BOSS-Sentinel graphs (no GTK4/GSK)."""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, List, Optional, Tuple

import cairo
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

CANVAS = (0.945, 0.961, 0.976)
SURFACE = (1.0, 1.0, 1.0)
BLUE = (0.145, 0.388, 0.922)
OK = (0.02, 0.588, 0.412)
AMBER = (0.851, 0.467, 0.024)
FAULT = (0.863, 0.149, 0.149)
MIST = (0.20, 0.255, 0.333)
MUTED = (0.392, 0.455, 0.545)
TEAL = (0.059, 0.463, 0.431)


def _color_for(pct: float, warn: float, crit: float) -> Tuple[float, float, float]:
    if pct >= crit:
        return FAULT
    if pct >= warn:
        return AMBER
    return BLUE


class _CairoArea(Gtk.DrawingArea):
    def __init__(self, width: int = 280, height: int = 150) -> None:
        super().__init__()
        self.set_size_request(width, height)
        self.set_hexpand(True)
        self.connect("draw", self._on_draw)

    def _on_draw(self, _widget, cr: cairo.Context) -> bool:
        w = max(1, self.get_allocated_width())
        h = max(1, self.get_allocated_height())
        try:
            self._paint(cr, w, h)
        except Exception:
            pass
        return False

    def _paint(self, cr: cairo.Context, w: int, h: int) -> None:
        raise NotImplementedError


class DeviceGraph(_CairoArea):
    """Live scrolling area chart — matches prior DeviceGraph look."""

    def __init__(self, title: str = "DEVICE", height: int = 150) -> None:
        super().__init__(280, height)
        self._title = title
        self._value = 0.0
        self._unit = "%"
        self._detail = ""
        self._warn = 85.0
        self._crit = 95.0
        self._history: Deque[float] = deque([0.0] * 60, maxlen=60)
        self._phase = 0.0
        GLib.timeout_add(500, self._tick)

    def update(
        self,
        value: float,
        unit: str = "%",
        detail: str = "",
        warn: float = 85.0,
        crit: float = 95.0,
        title: Optional[str] = None,
    ) -> None:
        self._value = float(value)
        self._unit = unit
        self._detail = detail or ""
        self._warn = warn
        self._crit = crit
        if title:
            self._title = title
        plotted = self._value
        if unit == "°C":
            plotted = min(100.0, self._value)
        elif unit != "%":
            plotted = min(100.0, self._value)
        self._history.append(max(0.0, min(100.0, plotted)))
        self.queue_draw()

    def _tick(self) -> bool:
        if not self.get_mapped():
            return True
        self._phase = (self._phase + 0.05) % (math.pi * 2)
        self.queue_draw()
        return True

    def _paint(self, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(*SURFACE)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        color = _color_for(
            self._value if self._unit in {"%", "°C"} else self._history[-1],
            self._warn,
            self._crit,
        )
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.set_source_rgb(*MUTED)
        cr.move_to(14, 22)
        cr.show_text(self._title.upper())

        text = f"{self._value:.0f}{self._unit}"
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(28)
        cr.set_source_rgb(*color)
        cr.move_to(14, 54)
        cr.show_text(text)

        if self._detail:
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10)
            cr.set_source_rgba(*MIST, 0.7)
            cr.move_to(14, 72)
            cr.show_text(self._detail[:48])

        top, bottom, left, right = 84, h - 14, 14, w - 14
        gh, gw = bottom - top, right - left
        if gh < 8 or gw < 8:
            return

        cr.set_source_rgba(*BLUE, 0.12)
        cr.set_line_width(1)
        cr.move_to(left, bottom)
        cr.line_to(right, bottom)
        cr.stroke()

        samples = list(self._history)
        if len(samples) < 2:
            return

        cr.move_to(left, bottom)
        for i, val in enumerate(samples):
            x = left + (i / (len(samples) - 1)) * gw
            y = bottom - (val / 100.0) * gh + math.sin(self._phase + i * 0.15) * 0.5
            cr.line_to(x, y)
        cr.line_to(right, bottom)
        cr.close_path()
        cr.set_source_rgba(*color, 0.12)
        cr.fill()

        cr.set_line_width(2)
        cr.set_source_rgb(*color)
        for i, val in enumerate(samples):
            x = left + (i / (len(samples) - 1)) * gw
            y = bottom - (val / 100.0) * gh + math.sin(self._phase + i * 0.15) * 0.5
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()

        y = bottom - (samples[-1] / 100.0) * gh
        cr.set_source_rgba(*color, 0.95)
        cr.arc(right, y, 3.0, 0, math.pi * 2)
        cr.fill()


class HeroVitality(_CairoArea):
    def __init__(self) -> None:
        super().__init__(140, 140)
        self.set_hexpand(False)
        self._score = 100
        self._overall = "ok"
        self._phase = 0.0
        GLib.timeout_add(80, self._tick)

    def set_score(self, score: int, overall: str = "ok") -> None:
        self._score = max(0, min(100, int(score)))
        self._overall = overall
        self.queue_draw()

    def _tick(self) -> bool:
        if not self.get_mapped():
            return True
        self._phase = (self._phase + 0.035) % (math.pi * 2)
        self.queue_draw()
        return True

    def _paint(self, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(*CANVAS)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        cx, cy = w / 2, h / 2
        color = OK if self._overall == "ok" else AMBER if self._overall == "warn" else FAULT
        breath = 0.94 + 0.06 * math.sin(self._phase)
        cr.set_source_rgba(*color, 0.18)
        cr.set_line_width(2)
        cr.arc(cx, cy, min(w, h) * 0.42 * breath, 0, math.pi * 2)
        cr.stroke()
        cr.set_source_rgb(*color)
        cr.set_line_width(2.5)
        cr.arc(cx, cy, min(w, h) * 0.36, 0, math.pi * 2)
        cr.stroke()
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(40)
        text = str(self._score)
        xb, _, tw, th, _, _ = cr.text_extents(text)
        cr.move_to(cx - tw / 2 - xb, cy + th / 2 - 4)
        cr.show_text(text)
        cr.set_font_size(10)
        cr.set_source_rgb(*MUTED)
        label = "HEALTH"
        xb, _, tw, _, _, _ = cr.text_extents(label)
        cr.move_to(cx - tw / 2 - xb, cy + 28)
        cr.show_text(label)


class BreathWave(_CairoArea):
    def __init__(self) -> None:
        super().__init__(400, 44)
        self._samples: Deque[float] = deque([100.0] * 100, maxlen=100)
        self._phase = 0.0
        GLib.timeout_add(120, self._tick)

    def push(self, score: float) -> None:
        self._samples.append(max(0.0, min(100.0, float(score))))
        self.queue_draw()

    def _tick(self) -> bool:
        if not self.get_mapped():
            return True
        self._phase += 0.12
        self.queue_draw()
        return True

    def _paint(self, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(*CANVAS)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        samples = list(self._samples)
        if len(samples) < 2:
            return
        cr.set_line_width(2)
        cr.set_source_rgb(*BLUE)
        n = len(samples)
        for i, val in enumerate(samples):
            x = i / (n - 1) * w
            y = h - (val / 100.0) * (h - 10) - 5 + math.sin(self._phase + i * 0.12) * 0.6
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()


class DiskPie(_CairoArea):
    """Disk space pie chart — used / free / reserved."""

    def __init__(self) -> None:
        super().__init__(320, 220)
        self._used_pct = 0.0
        self._used_label = "Used 0%"
        self._free_label = "Free 100%"
        self._title = "DISK /"
        self._detail = ""

    def update(self, used_pct: float, used_human: str = "", free_human: str = "", title: str = "DISK /") -> None:
        self._used_pct = max(0.0, min(100.0, float(used_pct)))
        free = 100.0 - self._used_pct
        self._used_label = f"Used {self._used_pct:.0f}%  {used_human}".strip()
        self._free_label = f"Free {free:.0f}%  {free_human}".strip()
        self._title = title
        self.queue_draw()

    def _paint(self, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(*SURFACE)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        cr.set_source_rgb(*MUTED)
        cr.move_to(16, 22)
        cr.show_text(self._title.upper())

        cx, cy = w * 0.38, h * 0.55
        radius = min(w, h) * 0.32
        used = self._used_pct / 100.0
        # start at top
        start = -math.pi / 2
        used_angle = used * math.pi * 2

        color = _color_for(self._used_pct, 85, 95)
        cr.set_source_rgb(*color)
        cr.move_to(cx, cy)
        cr.arc(cx, cy, radius, start, start + used_angle)
        cr.close_path()
        cr.fill()

        cr.set_source_rgb(*TEAL)
        cr.move_to(cx, cy)
        cr.arc(cx, cy, radius, start + used_angle, start + math.pi * 2)
        cr.close_path()
        cr.fill()

        # hole → donut
        cr.set_source_rgb(*SURFACE)
        cr.arc(cx, cy, radius * 0.48, 0, math.pi * 2)
        cr.fill()

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(22)
        cr.set_source_rgb(*color)
        text = f"{self._used_pct:.0f}%"
        xb, _, tw, th, _, _ = cr.text_extents(text)
        cr.move_to(cx - tw / 2 - xb, cy + th / 2 - 2)
        cr.show_text(text)

        # legend
        lx = w * 0.68
        ly = h * 0.40
        for label, col in ((self._used_label, color), (self._free_label, TEAL)):
            cr.set_source_rgb(*col)
            cr.rectangle(lx, ly - 8, 12, 12)
            cr.fill()
            cr.set_source_rgb(*MIST)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(11)
            cr.move_to(lx + 18, ly + 2)
            cr.show_text(label[:28])
            ly += 28


class MultiCpuGraph(_CairoArea):
    """GNOME System Monitor–style history: one colored line per logical CPU."""

    def __init__(self, history: int = 60) -> None:
        super().__init__(640, 240)
        self._history_len = history
        self._series: List[Deque[float]] = []
        self._current: List[float] = []

    def update(self, per_core: List[float]) -> None:
        n = len(per_core)
        while len(self._series) < n:
            self._series.append(deque([0.0] * self._history_len, maxlen=self._history_len))
        while len(self._series) > n:
            self._series.pop()
        self._current = [max(0.0, min(100.0, float(p))) for p in per_core]
        for i, pct in enumerate(self._current):
            self._series[i].append(pct)
        self.queue_draw()

    def _paint(self, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(*SURFACE)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        pad_l, pad_r, pad_t, pad_b = 14, 14, 36, 36
        gw = max(1.0, w - pad_l - pad_r)
        gh = max(1.0, h - pad_t - pad_b)

        cr.set_line_width(1)
        cr.set_source_rgba(0.15, 0.23, 0.37, 0.12)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = pad_t + gh * (1.0 - frac)
            cr.move_to(pad_l, y)
            cr.line_to(pad_l + gw, y)
            cr.stroke()

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.set_source_rgb(*MUTED)
        cr.move_to(pad_l, 22)
        n = len(self._current)
        cr.show_text(f"CPU HISTORY · {n} LOGICAL CPU{'S' if n != 1 else ''} · LAST 60 SAMPLES")

        if not self._series:
            cr.move_to(pad_l, pad_t + 24)
            cr.show_text("Waiting for per-CPU samples…")
            return

        for idx, series in enumerate(self._series):
            color = _CPU_LINE_COLORS[idx % len(_CPU_LINE_COLORS)]
            pts = list(series)
            if len(pts) < 2:
                continue
            cr.set_line_width(2.0)
            cr.set_source_rgb(*color)
            for i, val in enumerate(pts):
                x = pad_l + (i / (len(pts) - 1)) * gw
                y = pad_t + (1.0 - val / 100.0) * gh
                if i == 0:
                    cr.move_to(x, y)
                else:
                    cr.line_to(x, y)
            cr.stroke()

        # Legend like GNOME System Monitor (CPU1, CPU2, …)
        cr.set_font_size(11)
        lx = pad_l
        ly = h - 12
        for idx, pct in enumerate(self._current):
            color = _CPU_LINE_COLORS[idx % len(_CPU_LINE_COLORS)]
            label = f"CPU{idx + 1}: {pct:.1f}%"
            cr.set_source_rgb(*color)
            cr.rectangle(lx, ly - 9, 10, 10)
            cr.fill()
            cr.set_source_rgb(*MIST)
            cr.move_to(lx + 14, ly)
            cr.show_text(label)
            ext = cr.text_extents(label)
            lx += ext.width + 28
            if lx > w - 130 and idx < len(self._current) - 1:
                lx = pad_l
                ly -= 16


class CpuCoreMeter(Gtk.Box):
    """One logical CPU meter: label, bar, percent."""

    def __init__(self, index: int) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.get_style_context().add_class("cpu-core-meter")
        self.set_hexpand(True)
        self.set_border_width(6)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._lab = Gtk.Label(label=f"CPU{index + 1}", xalign=0)
        self._lab.get_style_context().add_class("core-label")
        self._lab.set_hexpand(True)
        self._val = Gtk.Label(label="0%", xalign=1)
        self._val.get_style_context().add_class("core-val")
        head.pack_start(self._lab, True, True, 0)
        head.pack_start(self._val, False, False, 0)

        self._bar = Gtk.ProgressBar()
        self._bar.set_fraction(0.0)
        self._bar.set_show_text(False)
        self._bar.get_style_context().add_class("core-bar")
        self.pack_start(head, False, False, 0)
        self.pack_start(self._bar, False, False, 0)

    def set_usage(self, pct: float) -> None:
        pct = max(0.0, min(100.0, float(pct)))
        self._bar.set_fraction(pct / 100.0)
        self._val.set_text(f"{pct:.0f}%")
        ctx = self.get_style_context()
        for cls in ("core-ok", "core-warn", "core-crit"):
            ctx.remove_class(cls)
        if pct >= 95:
            ctx.add_class("core-crit")
        elif pct >= 80:
            ctx.add_class("core-warn")
        else:
            ctx.add_class("core-ok")


class PerCpuMonitor(Gtk.Box):
    """Grid of individual logical-CPU meters (CPU1…CPUn)."""

    def __init__(self, title: str = "INDIVIDUAL CPUS") -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.get_style_context().add_class("per-cpu-monitor")
        self._title = Gtk.Label(label=title, xalign=0)
        self._title.get_style_context().add_class("section-label")
        self.pack_start(self._title, False, False, 0)

        self._empty = Gtk.Label(label="Per-CPU stats unavailable on this host.", xalign=0)
        self.pack_start(self._empty, False, False, 0)

        self._flow = Gtk.FlowBox()
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_homogeneous(True)
        self._flow.set_max_children_per_line(4)
        self._flow.set_min_children_per_line(1)
        self._flow.set_row_spacing(8)
        self._flow.set_column_spacing(10)
        self._flow.set_hexpand(True)
        self.pack_start(self._flow, False, False, 0)
        self._meters: List[CpuCoreMeter] = []

    def update(self, per_core: List[float]) -> None:
        if not per_core:
            self._empty.show()
            self._flow.hide()
            return
        self._empty.hide()
        self._flow.show()
        n = len(per_core)
        cols = 6 if n > 16 else (4 if n >= 4 else max(1, n))
        self._flow.set_max_children_per_line(cols)

        while len(self._meters) < n:
            meter = CpuCoreMeter(len(self._meters))
            self._meters.append(meter)
            self._flow.add(meter)
            meter.show_all()
        while len(self._meters) > n:
            meter = self._meters.pop()
            self._flow.remove(meter)

        for i, pct in enumerate(per_core):
            self._meters[i].set_usage(pct)


# Colors similar to GNOME System Monitor Resources (cycling).
_CPU_LINE_COLORS: List[Tuple[float, float, float]] = [
    (0.80, 0.00, 0.00),
    (0.90, 0.45, 0.00),
    (0.15, 0.39, 0.92),
    (0.02, 0.59, 0.41),
    (0.55, 0.25, 0.75),
    (0.85, 0.20, 0.55),
    (0.10, 0.55, 0.70),
    (0.40, 0.40, 0.45),
]
