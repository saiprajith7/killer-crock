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
    def __init__(self) -> None:
        super().__init__(600, 160)
        self._cores: List[float] = []
        self._phase = 0.0
        GLib.timeout_add(400, self._tick)

    def update(self, cores: List[float]) -> None:
        self._cores = [max(0.0, min(100.0, float(c))) for c in cores]
        self.queue_draw()

    def _tick(self) -> bool:
        if not self.get_mapped():
            return True
        self._phase = (self._phase + 0.04) % (math.pi * 2)
        self.queue_draw()
        return True

    def _paint(self, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(*SURFACE)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.set_source_rgb(*MUTED)
        cr.move_to(14, 20)
        cr.show_text("PER-CPU UTILIZATION")
        if not self._cores:
            return
        n = len(self._cores)
        left, right, top, bottom = 14, w - 14, 32, h - 14
        gap = 4
        bar_w = max(4.0, (right - left - gap * (n - 1)) / n)
        for i, val in enumerate(self._cores):
            x = left + i * (bar_w + gap)
            bh = (val / 100.0) * (bottom - top)
            color = _color_for(val, 85, 95)
            cr.set_source_rgb(*color)
            cr.rectangle(x, bottom - bh, bar_w, bh)
            cr.fill()
