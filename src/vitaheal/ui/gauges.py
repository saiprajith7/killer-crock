"""Custom Cairo HUD gauges — pulse rings, arc meters, waveforms."""

from __future__ import annotations

import math
from typing import Optional

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402


TEAL = (0.0, 0.90, 0.75)
LIME = (0.72, 1.0, 0.24)
AMBER = (1.0, 0.69, 0.13)
CRIMSON = (1.0, 0.23, 0.36)
VOID = (0.02, 0.03, 0.05)
MIST = (0.62, 0.71, 0.77)


def _severity_color(pct: float, warn: float, crit: float) -> tuple[float, float, float]:
    if pct >= crit:
        return CRIMSON
    if pct >= warn:
        return AMBER
    return TEAL


class PulseScore(Gtk.DrawingArea):
    """Giant animated vitality score with concentric pulse rings."""

    def __init__(self) -> None:
        super().__init__()
        self.set_content_width(220)
        self.set_content_height(220)
        self._score = 100
        self._phase = 0.0
        self._overall = "ok"
        self.set_draw_func(self._draw)
        GLib.timeout_add(33, self._tick)

    def set_score(self, score: int, overall: str = "ok") -> None:
        self._score = max(0, min(100, score))
        self._overall = overall
        self.queue_draw()

    def _tick(self) -> bool:
        self._phase = (self._phase + 0.04) % (math.pi * 2)
        self.queue_draw()
        return True

    def _draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(*VOID)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        cx, cy = w / 2, h / 2
        base_r = min(w, h) * 0.38
        color = TEAL if self._overall == "ok" else AMBER if self._overall == "warn" else CRIMSON

        # Grid crosshair
        cr.set_source_rgba(*TEAL, 0.12)
        cr.set_line_width(1)
        cr.move_to(cx, 8)
        cr.line_to(cx, h - 8)
        cr.move_to(8, cy)
        cr.line_to(w - 8, cy)
        cr.stroke()

        # Pulse rings
        for i in range(3):
            t = (self._phase + i * 0.85) % (math.pi * 2)
            expand = 0.55 + 0.45 * ((math.sin(t) + 1) / 2)
            alpha = 0.35 * (1.0 - (expand - 0.55) / 0.45)
            cr.set_source_rgba(*color, alpha)
            cr.set_line_width(2)
            cr.arc(cx, cy, base_r * expand * 1.35, 0, math.pi * 2)
            cr.stroke()

        # Outer dial ticks
        cr.set_source_rgba(*color, 0.55)
        for i in range(48):
            ang = (i / 48) * math.pi * 2
            inner = base_r * 1.05
            outer = base_r * (1.18 if i % 4 == 0 else 1.12)
            cr.set_line_width(2 if i % 4 == 0 else 1)
            cr.move_to(cx + math.cos(ang) * inner, cy + math.sin(ang) * inner)
            cr.line_to(cx + math.cos(ang) * outer, cy + math.sin(ang) * outer)
            cr.stroke()

        # Score arc
        start = -math.pi * 0.75
        span = math.pi * 1.5 * (self._score / 100.0)
        cr.set_source_rgba(*color, 0.2)
        cr.set_line_width(10)
        cr.arc(cx, cy, base_r, start, start + math.pi * 1.5)
        cr.stroke()
        cr.set_source_rgb(*color)
        cr.set_line_width(10)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.arc(cx, cy, base_r, start, start + span)
        cr.stroke()

        # Score text
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(42)
        text = str(self._score)
        xb, _, tw, th, _, _ = cr.text_extents(text)
        cr.set_source_rgb(*LIME if self._score >= 70 else AMBER if self._score >= 40 else CRIMSON)
        cr.move_to(cx - tw / 2 - xb, cy + th / 2)
        cr.show_text(text)

        cr.set_font_size(11)
        label = "VITALITY"
        xb, _, tw, th, _, _ = cr.text_extents(label)
        cr.set_source_rgba(*TEAL, 0.9)
        cr.move_to(cx - tw / 2 - xb, cy + 28)
        cr.show_text(label)


class ArcGauge(Gtk.DrawingArea):
    """Compact arc gauge with sweeping scanner."""

    def __init__(self, title: str = "METRIC") -> None:
        super().__init__()
        self.set_content_width(160)
        self.set_content_height(130)
        self._title = title
        self._value = 0.0
        self._unit = "%"
        self._warn = 80.0
        self._crit = 95.0
        self._phase = 0.0
        self.set_draw_func(self._draw)
        GLib.timeout_add(40, self._tick)

    def update(
        self,
        value: float,
        unit: str = "%",
        warn: float = 80.0,
        crit: float = 95.0,
        title: Optional[str] = None,
    ) -> None:
        self._value = value
        self._unit = unit
        self._warn = warn
        self._crit = crit
        if title:
            self._title = title
        self.queue_draw()

    def _tick(self) -> bool:
        self._phase = (self._phase + 0.06) % (math.pi * 2)
        self.queue_draw()
        return True

    def _draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(0.04, 0.06, 0.08)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        # subtle scanline
        cr.set_source_rgba(*TEAL, 0.04)
        y = (math.sin(self._phase) * 0.5 + 0.5) * h
        cr.rectangle(0, y, w, 3)
        cr.fill()

        cx, cy = w / 2, h * 0.62
        radius = min(w, h) * 0.42
        color = _severity_color(self._value, self._warn, self._crit)
        # Normalize for non-% units roughly into 0-100 arc
        pct = self._value
        if self._unit not in {"%", "°C"}:
            pct = min(100.0, self._value)
        if self._unit == "°C":
            pct = min(100.0, (self._value / 100.0) * 100.0)

        start = math.pi
        end = 2 * math.pi
        cr.set_source_rgba(*TEAL, 0.15)
        cr.set_line_width(8)
        cr.arc(cx, cy, radius, start, end)
        cr.stroke()

        span = math.pi * min(1.0, max(0.0, pct / 100.0))
        cr.set_source_rgb(*color)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.arc(cx, cy, radius, start, start + span)
        cr.stroke()

        # Sweep needle
        sweep = start + ((math.sin(self._phase) + 1) / 2) * math.pi
        cr.set_source_rgba(*LIME, 0.35)
        cr.set_line_width(1)
        cr.move_to(cx, cy)
        cr.line_to(cx + math.cos(sweep) * radius, cy + math.sin(sweep) * radius)
        cr.stroke()

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)
        cr.set_source_rgb(*TEAL)
        xb, _, tw, _, _, _ = cr.text_extents(self._title.upper())
        cr.move_to(cx - tw / 2 - xb, 16)
        cr.show_text(self._title.upper())

        text = f"{self._value:.0f}{self._unit}"
        cr.set_font_size(20)
        cr.set_source_rgb(*color)
        xb, _, tw, th, _, _ = cr.text_extents(text)
        cr.move_to(cx - tw / 2 - xb, cy + 4)
        cr.show_text(text)


class WaveformStrip(Gtk.DrawingArea):
    """Scrolling vitality waveform."""

    def __init__(self) -> None:
        super().__init__()
        self.set_content_width(600)
        self.set_content_height(56)
        self.set_hexpand(True)
        self._samples: list[float] = [50.0] * 120
        self._phase = 0.0
        self.set_draw_func(self._draw)
        GLib.timeout_add(50, self._tick)

    def push(self, score: float) -> None:
        self._samples.append(score)
        if len(self._samples) > 120:
            self._samples.pop(0)

    def _tick(self) -> bool:
        self._phase += 0.15
        self.queue_draw()
        return True

    def _draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(0.03, 0.05, 0.07)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        # grid
        cr.set_source_rgba(*TEAL, 0.08)
        cr.set_line_width(1)
        for i in range(1, 4):
            y = h * i / 4
            cr.move_to(0, y)
            cr.line_to(w, y)
            cr.stroke()

        if len(self._samples) < 2:
            return

        cr.set_source_rgb(*TEAL)
        cr.set_line_width(2)
        n = len(self._samples)
        for i, val in enumerate(self._samples):
            x = i / (n - 1) * w
            y = h - (val / 100.0) * (h - 8) - 4
            # jitter for living feel
            y += math.sin(self._phase + i * 0.2) * 1.2
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()

        # glow head
        x = w - 2
        y = h - (self._samples[-1] / 100.0) * (h - 8) - 4
        cr.set_source_rgba(*LIME, 0.8)
        cr.arc(x, y, 3.5, 0, math.pi * 2)
        cr.fill()
