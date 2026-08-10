"""Minimal live device graphs — BOSS-Sentinel blue theme."""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, Optional

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402


# Light canvas + trust blue
CANVAS = (0.945, 0.961, 0.976)  # #f1f5f9
SURFACE = (1.0, 1.0, 1.0)
BLUE = (0.145, 0.388, 0.922)  # #2563eb
BLUE_DEEP = (0.118, 0.251, 0.686)
OK = (0.02, 0.588, 0.412)
AMBER = (0.851, 0.467, 0.024)
FAULT = (0.863, 0.149, 0.149)
MIST = (0.20, 0.255, 0.333)
MUTED = (0.392, 0.455, 0.545)


def _color_for(pct: float, warn: float, crit: float) -> tuple[float, float, float]:
    if pct >= crit:
        return FAULT
    if pct >= warn:
        return AMBER
    return BLUE


class DeviceGraph(Gtk.DrawingArea):
    """One device: name, live value, detail, scrolling area chart."""

    def __init__(self, title: str = "DEVICE") -> None:
        super().__init__()
        self.set_content_width(280)
        self.set_content_height(150)
        self.set_hexpand(True)
        self._title = title
        self._value = 0.0
        self._unit = "%"
        self._detail = ""
        self._warn = 85.0
        self._crit = 95.0
        self._history: Deque[float] = deque([0.0] * 60, maxlen=60)
        self._phase = 0.0
        self.set_draw_func(self._draw)
        # Slow animation tick — 100ms redraws across many graphs inflated CPU.
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
        self._value = value
        self._unit = unit
        self._detail = detail
        self._warn = warn
        self._crit = crit
        if title:
            self._title = title
        plotted = value
        if unit == "°C":
            plotted = min(100.0, value)
        elif unit == "KB/s":
            plotted = min(100.0, value / 500.0)
        self._history.append(max(0.0, min(100.0, plotted)))
        self.queue_draw()

    def _tick(self) -> bool:
        self._phase = (self._phase + 0.05) % (math.pi * 2)
        self.queue_draw()
        return True

    def _draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, w: int, h: int) -> None:
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
        gh = bottom - top
        gw = right - left

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
            y = bottom - (val / 100.0) * gh
            y += math.sin(self._phase + i * 0.15) * 0.5
            cr.line_to(x, y)
        cr.line_to(right, bottom)
        cr.close_path()
        cr.set_source_rgba(*color, 0.12)
        cr.fill()

        cr.set_line_width(2)
        cr.set_source_rgb(*color)
        for i, val in enumerate(samples):
            x = left + (i / (len(samples) - 1)) * gw
            y = bottom - (val / 100.0) * gh
            y += math.sin(self._phase + i * 0.15) * 0.5
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()

        x = right
        y = bottom - (samples[-1] / 100.0) * gh
        cr.set_source_rgba(*color, 0.95)
        cr.arc(x, y, 3.0, 0, math.pi * 2)
        cr.fill()


class HeroVitality(Gtk.DrawingArea):
    """Large health score with a quiet breathing ring."""

    def __init__(self) -> None:
        super().__init__()
        self.set_content_width(150)
        self.set_content_height(150)
        self._score = 100
        self._overall = "ok"
        self._phase = 0.0
        self.set_draw_func(self._draw)
        GLib.timeout_add(50, self._tick)

    def set_score(self, score: int, overall: str = "ok") -> None:
        self._score = max(0, min(100, score))
        self._overall = overall
        self.queue_draw()

    def _tick(self) -> bool:
        self._phase = (self._phase + 0.035) % (math.pi * 2)
        self.queue_draw()
        return True

    def _draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, w: int, h: int) -> None:
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
        label = "HEALTH"
        xb, _, tw, _, _, _ = cr.text_extents(label)
        cr.set_source_rgb(*MUTED)
        cr.move_to(cx - tw / 2 - xb, cy + 28)
        cr.show_text(label)


class BreathWave(Gtk.DrawingArea):
    """Full-width minimal vitality waveform."""

    def __init__(self) -> None:
        super().__init__()
        self.set_content_height(44)
        self.set_hexpand(True)
        self._samples: Deque[float] = deque([100.0] * 100, maxlen=100)
        self._phase = 0.0
        self.set_draw_func(self._draw)
        GLib.timeout_add(80, self._tick)

    def push(self, score: float) -> None:
        self._samples.append(score)

    def _tick(self) -> bool:
        self._phase += 0.12
        self.queue_draw()
        return True

    def _draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(*CANVAS)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        samples = list(self._samples)
        if len(samples) < 2:
            return
        cr.set_line_width(2)
        cr.set_source_rgb(*BLUE)
        for i, val in enumerate(samples):
            x = i / (len(samples) - 1) * w
            y = h - (val / 100.0) * (h - 10) - 5
            y += math.sin(self._phase + i * 0.12) * 0.6
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()


class CpuCoreMeter(Gtk.Box):
    """One logical CPU: label, bar, percent — updated in place."""

    def __init__(self, index: int) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("cpu-core-meter")
        self.set_hexpand(True)
        self._index = index

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._lab = Gtk.Label(label=f"CPU{index + 1}")
        self._lab.add_css_class("core-label")
        self._lab.set_halign(Gtk.Align.START)
        self._lab.set_hexpand(True)
        self._val = Gtk.Label(label="0%")
        self._val.add_css_class("core-val")
        self._val.set_halign(Gtk.Align.END)
        head.append(self._lab)
        head.append(self._val)

        self._bar = Gtk.LevelBar()
        self._bar.set_min_value(0.0)
        self._bar.set_max_value(100.0)
        self._bar.set_value(0.0)
        self._bar.set_mode(Gtk.LevelBarMode.CONTINUOUS)
        self._bar.add_css_class("core-bar")
        self._bar.set_hexpand(True)
        try:
            self._bar.add_offset_value("warning", 80.0)
            self._bar.add_offset_value("error", 95.0)
        except Exception:  # noqa: BLE001
            pass

        self.append(head)
        self.append(self._bar)

    def set_usage(self, pct: float, warn: float = 80.0, crit: float = 95.0) -> None:
        pct = max(0.0, min(100.0, float(pct)))
        self._bar.set_value(pct)
        self._val.set_text(f"{pct:.0f}%")
        for cls in ("core-ok", "core-warn", "core-crit"):
            self.remove_css_class(cls)
            self._bar.remove_css_class(cls)
        if pct >= crit:
            self.add_css_class("core-crit")
            self._bar.add_css_class("core-crit")
        elif pct >= warn:
            self.add_css_class("core-warn")
            self._bar.add_css_class("core-warn")
        else:
            self.add_css_class("core-ok")
            self._bar.add_css_class("core-ok")


class PerCpuMonitor(Gtk.Box):
    """Grid of individual logical-CPU meters (CPU0…CPUn)."""

    def __init__(self, title: str = "INDIVIDUAL CPUS") -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add_css_class("per-cpu-monitor")
        self._title = Gtk.Label(label=title)
        self._title.add_css_class("section-label")
        self._title.set_halign(Gtk.Align.START)
        self.append(self._title)

        self._empty = Gtk.Label(label="Per-CPU stats unavailable on this host.")
        self._empty.add_css_class("log-empty")
        self._empty.set_halign(Gtk.Align.START)
        self.append(self._empty)

        self._flow = Gtk.FlowBox()
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_homogeneous(True)
        self._flow.set_max_children_per_line(4)
        self._flow.set_min_children_per_line(1)
        self._flow.set_row_spacing(8)
        self._flow.set_column_spacing(10)
        self._flow.set_hexpand(True)
        self.append(self._flow)

        self._meters: list[CpuCoreMeter] = []

    def update(
        self,
        per_core: list[float],
        warn: float = 80.0,
        crit: float = 95.0,
    ) -> None:
        if not per_core:
            self._empty.set_visible(True)
            self._flow.set_visible(False)
            return

        self._empty.set_visible(False)
        self._flow.set_visible(True)

        n = len(per_core)
        cols = 4 if n >= 4 else max(1, n)
        if n > 16:
            cols = 6
        self._flow.set_max_children_per_line(cols)

        while len(self._meters) < n:
            meter = CpuCoreMeter(len(self._meters))
            self._meters.append(meter)
            self._flow.append(meter)
        while len(self._meters) > n:
            meter = self._meters.pop()
            self._flow.remove(meter)

        for i, pct in enumerate(per_core):
            self._meters[i].set_usage(pct, warn=warn, crit=crit)


# Colors similar to GNOME System Monitor Resources (cycling).
_CPU_LINE_COLORS: list[tuple[float, float, float]] = [
    (0.80, 0.00, 0.00),  # red — CPU1
    (0.90, 0.45, 0.00),  # orange — CPU2
    (0.15, 0.39, 0.92),  # blue
    (0.02, 0.59, 0.41),  # green
    (0.55, 0.25, 0.75),  # purple
    (0.85, 0.20, 0.55),  # pink
    (0.10, 0.55, 0.70),  # teal
    (0.40, 0.40, 0.45),  # slate
]


class MultiCpuGraph(Gtk.DrawingArea):
    """System Monitor–style history: one colored line per logical CPU."""

    def __init__(self, history: int = 60) -> None:
        super().__init__()
        self.set_content_width(640)
        self.set_content_height(220)
        self.set_hexpand(True)
        self.set_vexpand(False)
        self._history_len = history
        self._series: list[Deque[float]] = []
        self._current: list[float] = []
        self.set_draw_func(self._draw)

    def update(self, per_core: list[float]) -> None:
        n = len(per_core)
        while len(self._series) < n:
            self._series.append(deque([0.0] * self._history_len, maxlen=self._history_len))
        while len(self._series) > n:
            self._series.pop()
        self._current = [max(0.0, min(100.0, float(p))) for p in per_core]
        for i, pct in enumerate(self._current):
            self._series[i].append(pct)
        self.queue_draw()

    def _draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(*SURFACE)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        pad_l, pad_r, pad_t, pad_b = 14, 14, 36, 28
        gw = max(1.0, w - pad_l - pad_r)
        gh = max(1.0, h - pad_t - pad_b)

        # Grid
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
        cr.show_text("CPU HISTORY · LAST 60 SAMPLES")

        if not self._series:
            cr.move_to(pad_l, pad_t + 24)
            cr.show_text("Waiting for per-CPU samples…")
            return

        # Lines
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

        # Legend (CPU1… like GNOME System Monitor)
        cr.set_font_size(12)
        lx = pad_l
        ly = h - 10
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
            lx += ext.width + 36
            if lx > w - 120 and idx < len(self._current) - 1:
                lx = pad_l
                ly -= 16
