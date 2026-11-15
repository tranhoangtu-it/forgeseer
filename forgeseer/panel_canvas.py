"""Vẽ một khung overlay lên tk.Canvas: nền bo góc, biểu tượng tiêu đề, thanh tỉ lệ / tiến độ,
viên kết luận và hiệu ứng nháy viền khi có cảnh báo.

Bố cục (cỡ chữ, cột, dòng nào hiện) đã được ``panel_layout.fit_layout`` tính sẵn; ở đây chỉ vẽ.
Phần trang trí đọc từ tag của từng dòng (``panel_decor``).
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Protocol

from .panel_decor import (ICON, ODDS, PILL, PILL_SAFE, PROGRESS, base_tag, odds_segments,
                          parse_bar, pill_span, progress_geometry, tag_extras)
from .panel_icons import draw_icon
from .panel_layout import COLUMN_GAP, PAD_X, FontMetrics, Layout, frame

TRANSPARENT_KEY = "#010203"  # màu "trong suốt" của cửa sổ (góc ngoài phần bo tròn)
PANEL_BG = "#121218"
BORDER = "#34344a"
TITLE_RULE = "#2a2a38"
TRACK = "#262632"
TITLE, NORMAL, GOOD, WARN, DIM, ALERT = "title", "normal", "good", "warn", "dim", "alert"
COLORS = {TITLE: "#f0c060", NORMAL: "#e8e8e8", GOOD: "#7ee08a", WARN: "#ff6b5b", DIM: "#9a9aa8",
          ALERT: "#ffffff"}
OUTCOME_COLORS = {"break": "#e5484d", "damage": "#f08c3a", "hold": "#8b8d98",
                  "success": "#46c768", "great": "#f5c542"}
PILL_COLORS = {GOOD: ("#173d22", "#46c768"), WARN: ("#4a1916", "#ff6b5b"),
               PILL_SAFE: ("#123b44", "#4cc9d9")}
ALERT_BG = "#b01818"
MARKER = "#f4f4f8"
BAR_COLS = 56       # bề rộng tối đa của thanh (số cột chữ)
RADIUS = 10         # bo góc khung ở 100% (px)
BORDER_WIDTH = 1
ICON_SHARE = 0.78   # biểu tượng cao ~78% một dòng
BAR_SHARE = 0.42    # thanh cao ~42% một dòng


class Fonts(Protocol):
    normal: tkfont.Font
    bold: tkfont.Font
    alert: tkfont.Font


def rounded_rect(c: tk.Canvas, x0: float, y0: float, x1: float, y1: float, r: float,
                 **kw: object) -> int:
    r = max(min(r, (x1 - x0) / 2, (y1 - y0) / 2), 0)
    pts = (x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0)
    return c.create_polygon(*pts, smooth=True, **kw)


class PanelCanvas:
    def __init__(self, parent: tk.Misc) -> None:
        self.canvas = tk.Canvas(parent, bg=TRANSPARENT_KEY, bd=0, highlightthickness=0,
                                cursor="arrow")
        self.canvas.pack()
        self._border: int | None = None
        self._border_width = BORDER_WIDTH
        self._flash_job: str | None = None
        self._flash_color: str | None = None  # màu viền lúc đang sáng (giữ qua các lần vẽ lại)

    # ---------- vẽ ----------
    def draw(self, layout: Layout, fonts: Fonts, m: FontMetrics, scale: float) -> None:
        c = self.canvas
        c.delete("all")
        left, top = frame(m, scale)
        min_width = BAR_COLS * m.char_width // 2  # cột chỉ có thanh vẫn đủ chỗ vẽ
        widths = [max(max((self._text_width(row, fonts) for row in col), default=0), min_width)
                  for col in layout.columns]
        xs = [left]
        if len(layout.columns) > 1:
            xs.append(left + widths[0] + COLUMN_GAP * m.char_width)
        bottoms = []
        for x, col, width in zip(xs, layout.columns, widths):
            y = top
            for row in col:
                y += self._draw_row(row, x, y, width, fonts, m, scale)
            bottoms.append(y)
        w = xs[-1] + widths[-1] + round(PAD_X * scale) + m.char_width
        h = max(bottoms, default=top) + top
        self._border_width = max(round(BORDER_WIDTH * scale), 1)
        lit = self._flash_color is not None
        self._border = rounded_rect(c, 1, 1, w - 1, h - 1, RADIUS * scale, fill=PANEL_BG,
                                    outline=self._flash_color if lit else BORDER,
                                    width=self._border_width * (3 if lit else 1))
        c.tag_lower(self._border)
        c.configure(width=w, height=h)

    @staticmethod
    def _font(base: str, fonts: Fonts) -> tkfont.Font:
        return fonts.alert if base == ALERT else fonts.bold if base == TITLE else fonts.normal

    def _text_width(self, row: tuple[str, ...], fonts: Fonts) -> int:
        base = base_tag(row[1])
        return self._font(base, fonts).measure(row[0]) if row[0] else 0

    def _draw_row(self, row: tuple[str, ...], x: int, y: int, col_width: int, fonts: Fonts,
                  m: FontMetrics, scale: float) -> int:
        text, tag = row[0], row[1]
        spec = parse_bar(tag)
        if spec is not None:
            self._draw_bar(spec, x, y, col_width, m)
            return m.line_height
        base, extras = base_tag(tag), tag_extras(tag)
        font = self._font(base, fonts)
        height = font.metrics("linespace") if base == ALERT else m.line_height
        c = self.canvas
        if base == ALERT and text:
            pad = round(4 * scale)
            rounded_rect(c, x - pad, y, x + font.measure(text) + pad, y + height, 6 * scale,
                         fill=ALERT_BG, outline="")
            extras.setdefault(ICON, "alert")
        if PILL in extras:
            self._draw_pill(text, extras[PILL], base, x, y, font, m, scale)
        if ICON in extras:
            size = m.line_height * ICON_SHARE
            color = COLORS[WARN] if extras[ICON] == "alert" else COLORS.get(base, COLORS[TITLE])
            draw_icon(c, extras[ICON], x - m.line_height * 0.92, y + (height - size) / 2, size,
                      COLORS[TITLE] if base == TITLE else color)
        if text:
            c.create_text(x, y, text=text, anchor="nw", font=font,
                          fill=COLORS.get(base, COLORS[NORMAL]))
        if base == TITLE and text:
            rule_x = x + font.measure(text) + m.char_width
            if rule_x < x + col_width:
                c.create_line(rule_x, y + height / 2, x + col_width, y + height / 2,
                              fill=TITLE_RULE)
        return height

    def _draw_pill(self, text: str, kind: str, base: str, x: int, y: int, font: tkfont.Font,
                   m: FontMetrics, scale: float) -> None:
        span = pill_span(text)
        if span is None:
            return
        fill, outline = PILL_COLORS.get(PILL_SAFE if kind == PILL_SAFE else base,
                                        PILL_COLORS[GOOD])
        pad = max(round(m.char_width * 0.4), 1)  # vừa trong khoảng trắng hai bên chữ
        x0 = x + font.measure(text[:span[0]]) - pad
        x1 = x + font.measure(text[:span[1]]) + pad
        inset = max(round(m.line_height * 0.06), 1)
        rounded_rect(self.canvas, x0, y + inset, x1, y + m.line_height - inset,
                     m.line_height / 2, fill=fill, outline=outline)

    def _draw_bar(self, spec, x: int, y: int, col_width: int, m: FontMetrics) -> None:
        c = self.canvas
        x0 = x + spec.indent * m.char_width
        width = max(min(BAR_COLS * m.char_width, x + col_width - x0), 4 * m.char_width)
        bar_h = max(round(m.line_height * BAR_SHARE), 4)
        top = y + (m.line_height - bar_h) // 2
        bottom = top + bar_h
        c.create_rectangle(x0, top, x0 + width, bottom, fill=TRACK, width=0)
        if spec.kind == ODDS:
            for left, right, outcome in odds_segments(spec.values, x0, width):
                c.create_rectangle(left, top, right, bottom, fill=OUTCOME_COLORS[outcome], width=0)
        elif spec.kind == PROGRESS and len(spec.values) == 3:
            geo = progress_geometry(*spec.values, x0, width)
            color = COLORS[GOOD] if spec.ok else COLORS[WARN]
            if geo.done[1] > geo.done[0]:
                c.create_rectangle(geo.done[0], top, geo.done[1], bottom, fill=color, width=0)
            if geo.extra[1] > geo.extra[0]:
                c.create_rectangle(geo.extra[0], top, geo.extra[1], bottom, fill=color,
                                   stipple="gray50", width=0)
            c.create_line(geo.marker, top - 2, geo.marker, bottom + 2, fill=MARKER, width=2)

    # ---------- cảnh báo ----------
    def flash(self, color: str, cycles: int = 3, period_ms: int = 220) -> None:
        """Nháy viền khung ``cycles`` lần (sáng/tắt), hủy đợt nháy cũ nếu còn."""
        if self._flash_job is not None:
            self.canvas.after_cancel(self._flash_job)
            self._flash_job = None
        self._flash_step(color, cycles * 2, period_ms)

    def _flash_step(self, color: str, steps: int, period_ms: int) -> None:
        on = steps % 2 == 0 and steps > 0
        self._flash_color = color if on else None
        if self._border is not None:
            self.canvas.itemconfigure(self._border, outline=color if on else BORDER,
                                      width=self._border_width * (3 if on else 1))
        if steps <= 0:
            self._flash_job = None
            return
        self._flash_job = self.canvas.after(period_ms, self._flash_step, color, steps - 1,
                                            period_ms)
