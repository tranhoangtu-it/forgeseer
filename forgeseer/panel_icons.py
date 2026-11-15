"""Biểu tượng nhỏ vẽ bằng hình cơ bản của Canvas (không cần file ảnh), cỡ khoảng một dòng chữ."""
from __future__ import annotations

import math
import tkinter as tk
from typing import Callable

Painter = Callable[[tk.Canvas, float, float, float, str], None]


def _w(s: float) -> int:
    return max(1, round(s / 9))


def sword(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    c.create_line(x + s * .2, y + s * .8, x + s * .9, y + s * .1, fill=color, width=_w(s) + 1)
    c.create_line(x + s * .12, y + s * .5, x + s * .5, y + s * .88, fill=color, width=_w(s) + 1)
    c.create_line(x + s * .05, y + s * .95, x + s * .25, y + s * .75, fill=color, width=_w(s) + 2)


def tribute(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    """Vương miện (cống nạp cho rồng/nhà vua)."""
    pts = (.08, .8, .08, .3, .3, .55, .5, .15, .7, .55, .92, .3, .92, .8)
    c.create_polygon(*[x + s * v if i % 2 == 0 else y + s * v for i, v in enumerate(pts)],
                     fill=color, outline=color)
    c.create_rectangle(x + s * .08, y + s * .84, x + s * .92, y + s * .95, fill=color, width=0)


def relic(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    """Viên ngọc."""
    c.create_polygon(x + s * .2, y + s * .12, x + s * .8, y + s * .12, x + s * .98, y + s * .38,
                     x + s * .5, y + s * .95, x + s * .02, y + s * .38, fill="", outline=color,
                     width=_w(s) + 1)
    c.create_line(x + s * .02, y + s * .38, x + s * .98, y + s * .38, fill=color, width=_w(s))
    c.create_line(x + s * .35, y + s * .12, x + s * .5, y + s * .95, x + s * .65, y + s * .12,
                  fill=color, width=_w(s))


def rank(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    """Ngôi sao (★ = di vật giảm gãy tốt nhất)."""
    pts = []
    for i in range(10):
        r = s * (.48 if i % 2 == 0 else .2)
        a = math.pi / 2 + i * math.pi / 5
        pts += [x + s / 2 + r * math.cos(a), y + s * .52 - r * math.sin(a)]
    c.create_polygon(*pts, fill=color, outline=color)


def shop(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    """Túi hàng."""
    c.create_rectangle(x + s * .12, y + s * .35, x + s * .88, y + s * .95, outline=color,
                       width=_w(s) + 1)
    c.create_arc(x + s * .3, y + s * .05, x + s * .7, y + s * .6, start=0, extent=180,
                 style="arc", outline=color, width=_w(s) + 1)


def merchant(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    """Đồng vàng (Thương nhân ma)."""
    c.create_oval(x + s * .08, y + s * .08, x + s * .92, y + s * .92, outline=color,
                  width=_w(s) + 1)
    c.create_oval(x + s * .32, y + s * .32, x + s * .68, y + s * .68, fill=color, width=0)


def alert(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    c.create_polygon(x + s * .5, y + s * .04, x + s * .98, y + s * .94, x + s * .02, y + s * .94,
                     fill=color, outline=color)
    c.create_line(x + s * .5, y + s * .36, x + s * .5, y + s * .66, fill="#2a0a0a",
                  width=_w(s) + 1)
    c.create_rectangle(x + s * .46, y + s * .74, x + s * .54, y + s * .84, fill="#2a0a0a", width=0)


def stats(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    for i, h in enumerate((.45, .75, .3)):
        left = x + s * (.1 + i * .3)
        c.create_rectangle(left, y + s * (.95 - h), left + s * .22, y + s * .95, fill=color,
                           width=0)


def todo(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    c.create_rectangle(x + s * .08, y + s * .1, x + s * .9, y + s * .92, outline=color,
                       width=_w(s) + 1)
    c.create_line(x + s * .25, y + s * .52, x + s * .43, y + s * .72, x + s * .75, y + s * .3,
                  fill=color, width=_w(s) + 1)


def forge(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    """Cái đe."""
    pts = (.02, .25, .78, .25, .98, .38, .62, .45, .62, .62, .78, .9, .22, .9, .38, .62, .38,
           .45, .02, .4)
    c.create_polygon(*[x + s * v if i % 2 == 0 else y + s * v for i, v in enumerate(pts)],
                     fill=color, outline=color)


def info(c: tk.Canvas, x: float, y: float, s: float, color: str) -> None:
    c.create_oval(x + s * .06, y + s * .06, x + s * .94, y + s * .94, outline=color,
                  width=_w(s) + 1)
    c.create_line(x + s * .5, y + s * .44, x + s * .5, y + s * .76, fill=color, width=_w(s) + 1)
    c.create_rectangle(x + s * .45, y + s * .24, x + s * .55, y + s * .34, fill=color, width=0)


ICONS: dict[str, Painter] = {
    "sword": sword, "tribute": tribute, "relic": relic, "rank": rank, "shop": shop,
    "merchant": merchant, "alert": alert, "stats": stats, "todo": todo, "forge": forge,
    "info": info,
}


def draw_icon(canvas: tk.Canvas, name: str, x: float, y: float, size: float, color: str) -> None:
    painter = ICONS.get(name)
    if painter is not None:
        painter(canvas, x, y, size, color)
