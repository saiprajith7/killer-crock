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
        GLib.timeout_add(40, self._tick)

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
        GLib.timeout_add(33, self._tick)

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
        GLib.timeout_add(50, self._tick)

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
