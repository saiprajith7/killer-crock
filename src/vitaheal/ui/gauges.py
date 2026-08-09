"""Minimal live device graphs — the visual core of VitaHeal."""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, Optional

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402


INK = (0.04, 0.05, 0.045)
SIGNAL = (0.24, 1.0, 0.60)
SIGNAL_DIM = (0.24, 1.0, 0.60)
AMBER = (1.0, 0.62, 0.20)
FAULT = (1.0, 0.30, 0.42)
MIST = (0.70, 0.76, 0.72)
MUTED = (0.35, 0.42, 0.38)


def _color_for(pct: float, warn: float, crit: float) -> tuple[float, float, float]:
    if pct >= crit:
        return FAULT
    if pct >= warn:
        return AMBER
    return SIGNAL


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
        # Normalize history to 0-100 for graphing non-% units
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
        # Soft vertical wash (atmosphere, not flat)
        for i in range(h):
            t = i / max(h, 1)
            cr.set_source_rgb(
                INK[0] + 0.02 * t,
                INK[1] + 0.03 * t,
                INK[2] + 0.02 * t,
            )
            cr.rectangle(0, i, w, 1)
            cr.fill()

        color = _color_for(self._value if self._unit in {"%", "°C"} else self._history[-1], self._warn, self._crit)

        # Title
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.set_source_rgb(*MUTED)
        cr.move_to(14, 22)
        cr.show_text(self._title.upper())

        # Big value
        text = f"{self._value:.0f}{self._unit}"
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(28)
        cr.set_source_rgb(*color)
        cr.move_to(14, 54)
        cr.show_text(text)

        # Detail
        if self._detail:
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10)
            cr.set_source_rgba(*MIST, 0.65)
            cr.move_to(14, 72)
            cr.show_text(self._detail[:48])

        # Graph region
        top, bottom, left, right = 84, h - 14, 14, w - 14
        gh = bottom - top
        gw = right - left

        # Baseline
        cr.set_source_rgba(*SIGNAL, 0.12)
        cr.set_line_width(1)
        cr.move_to(left, bottom)
        cr.line_to(right, bottom)
        cr.stroke()

        samples = list(self._history)
        if len(samples) < 2:
            return

        # Filled area
        cr.move_to(left, bottom)
        for i, val in enumerate(samples):
            x = left + (i / (len(samples) - 1)) * gw
            y = bottom - (val / 100.0) * gh
            y += math.sin(self._phase + i * 0.15) * 0.6
            cr.line_to(x, y)
        cr.line_to(right, bottom)
        cr.close_path()
        cr.set_source_rgba(*color, 0.14)
        cr.fill()

        # Stroke
        cr.set_line_width(2)
        cr.set_source_rgb(*color)
        for i, val in enumerate(samples):
            x = left + (i / (len(samples) - 1)) * gw
            y = bottom - (val / 100.0) * gh
            y += math.sin(self._phase + i * 0.15) * 0.6
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()

        # Living head
        x = right
        y = bottom - (samples[-1] / 100.0) * gh
        cr.set_source_rgba(*color, 0.9)
        cr.arc(x, y, 3.2, 0, math.pi * 2)
        cr.fill()


class HeroVitality(Gtk.DrawingArea):
    """Single large vitality number with a quiet breathing ring."""

    def __init__(self) -> None:
        super().__init__()
        self.set_content_width(160)
        self.set_content_height(160)
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
        cr.set_source_rgb(*INK)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        cx, cy = w / 2, h / 2
        color = SIGNAL if self._overall == "ok" else AMBER if self._overall == "warn" else FAULT
        breath = 0.92 + 0.08 * math.sin(self._phase)

        cr.set_source_rgba(*color, 0.22)
        cr.set_line_width(1.5)
        cr.arc(cx, cy, min(w, h) * 0.42 * breath, 0, math.pi * 2)
        cr.stroke()

        cr.set_source_rgba(*color, 0.55)
        cr.set_line_width(2)
        cr.arc(cx, cy, min(w, h) * 0.36, 0, math.pi * 2)
        cr.stroke()

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(44)
        text = str(self._score)
        xb, _, tw, th, _, _ = cr.text_extents(text)
        cr.set_source_rgb(*color)
        cr.move_to(cx - tw / 2 - xb, cy + th / 2 - 4)
        cr.show_text(text)

        cr.set_font_size(10)
        label = "HEALTH"
        xb, _, tw, _, _, _ = cr.text_extents(label)
        cr.set_source_rgba(*MIST, 0.7)
        cr.move_to(cx - tw / 2 - xb, cy + 28)
        cr.show_text(label)


class BreathWave(Gtk.DrawingArea):
    """Full-width minimal vitality waveform."""

    def __init__(self) -> None:
        super().__init__()
        self.set_content_height(48)
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
        for i in range(h):
            t = i / max(h, 1)
            cr.set_source_rgb(0.035 + t * 0.01, 0.045, 0.04)
            cr.rectangle(0, i, w, 1)
            cr.fill()

        samples = list(self._samples)
        if len(samples) < 2:
            return
        cr.set_line_width(1.8)
        cr.set_source_rgb(*SIGNAL)
        for i, val in enumerate(samples):
            x = i / (len(samples) - 1) * w
            y = h - (val / 100.0) * (h - 10) - 5
            y += math.sin(self._phase + i * 0.12) * 0.8
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()
