"""Small charts drawn on a Tk canvas for the settings window (no plotting library).

``line_chart`` for curves (survival by day, grade trend) and ``bar_chart`` for counts. Layout
maths is kept in pure helpers so it can be tested without a display.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Sequence

WIDTH, HEIGHT = 440, 170
MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 40, 12, 14, 22
BG, GRID, AXIS, TEXT = "#ffffff", "#e6e6e6", "#888888", "#444444"
FONT = ("Segoe UI", 8)
SERIES_COLORS = ("#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#ff7f0e")


def scale(value: float, low: float, high: float, out_low: float, out_high: float) -> float:
    """Linear map of ``value`` from [low, high] to [out_low, out_high] (flat range -> middle)."""
    if high == low:
        return (out_low + out_high) / 2
    return out_low + (value - low) * (out_high - out_low) / (high - low)


def tick_step(span: int, max_ticks: int = 8) -> int:
    """Step between x labels so at most ``max_ticks`` are drawn."""
    return max(1, -(-span // max_ticks))


def make_canvas(parent: tk.Misc, width: int = WIDTH, height: int = HEIGHT) -> tk.Canvas:
    return tk.Canvas(parent, width=width, height=height, background=BG, highlightthickness=1,
                     highlightbackground=GRID)


def _frame(canvas: tk.Canvas, title: str) -> tuple[float, float, float, float]:
    w, h = int(canvas["width"]), int(canvas["height"])
    canvas.delete("all")
    if title:
        canvas.create_text(MARGIN_L, 2, text=title, anchor="nw", fill=TEXT, font=FONT)
    return MARGIN_L, MARGIN_T + 6, w - MARGIN_R, h - MARGIN_B


def line_chart(canvas: tk.Canvas, xs: Sequence[int],
               series: Sequence[tuple[str, Sequence[float]]], y_max: float,
               y_label: Callable[[float], str], title: str = "") -> None:
    """One line per (name, values) over ``xs``; y from 0 to ``y_max``; legend top-right."""
    left, top, right, bottom = _frame(canvas, title)
    if not xs or y_max <= 0:
        return
    for frac in (0.0, 0.5, 1.0):
        y = scale(frac, 0, 1, bottom, top)
        canvas.create_line(left, y, right, y, fill=GRID)
        canvas.create_text(left - 4, y, text=y_label(frac * y_max), anchor="e", fill=TEXT,
                           font=FONT)
    step = tick_step(len(xs))
    for i, x in enumerate(xs):
        if i % step == 0 or i == len(xs) - 1:
            px = scale(i, 0, len(xs) - 1, left, right)
            canvas.create_text(px, bottom + 3, text=str(x), anchor="n", fill=TEXT, font=FONT)
    canvas.create_line(left, bottom, right, bottom, fill=AXIS)
    for k, (name, values) in enumerate(series):
        color = SERIES_COLORS[k % len(SERIES_COLORS)]
        points = [coord for i, v in enumerate(values)
                  for coord in (scale(i, 0, len(xs) - 1, left, right),
                                scale(min(v, y_max), 0, y_max, bottom, top))]
        if len(points) >= 4:
            canvas.create_line(*points, fill=color, width=2)
        elif len(points) == 2:
            canvas.create_oval(points[0] - 2, points[1] - 2, points[0] + 2, points[1] + 2,
                               fill=color, outline=color)
        if name:
            canvas.create_text(right, top + 2 + 12 * k, text=name + " ━", anchor="ne",
                               fill=color, font=FONT)


def bar_chart(canvas: tk.Canvas, bars: Sequence[tuple[str, int]], title: str = "") -> None:
    """Vertical bars with their count on top and the label underneath."""
    left, top, right, bottom = _frame(canvas, title)
    if not bars:
        return
    peak = max(count for _, count in bars) or 1
    slot = (right - left) / len(bars)
    width = max(min(slot * 0.7, 36), 2)
    canvas.create_line(left, bottom, right, bottom, fill=AXIS)
    step = tick_step(len(bars), 12)
    for i, (label, count) in enumerate(bars):
        cx = left + slot * (i + 0.5)
        y = scale(count, 0, peak, bottom, top + 10)
        canvas.create_rectangle(cx - width / 2, y, cx + width / 2, bottom,
                                fill=SERIES_COLORS[0], outline="")
        canvas.create_text(cx, y - 1, text=str(count), anchor="s", fill=TEXT, font=FONT)
        if i % step == 0:
            canvas.create_text(cx, bottom + 3, text=label, anchor="n", fill=TEXT, font=FONT)
