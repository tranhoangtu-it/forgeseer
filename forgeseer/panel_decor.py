"""Trang trí cho khung overlay vẽ trên Canvas: biểu tượng tiêu đề, thanh tỉ lệ, viên huy hiệu.

Hàm thuần, không phụ thuộc Tk. Một dòng vẫn là ``(chữ, tag[, LOW])``; phần trang trí nằm trong
tag dưới dạng ``"good|pill"`` hay ``"title|icon=sword"``, nên mọi chỗ khác (bọc dòng, co khung,
chế độ gọn) vẫn xử lý như dòng thường. Thanh (``bar``) là một dòng riêng, chữ rỗng, cao đúng
một dòng trong mô hình bố cục.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .text_format import LOW, SEP

BAR = "bar"
ODDS, PROGRESS = "odds", "progress"
OUTCOMES = ("break", "damage", "hold", "success", "great")  # thứ tự của SwordOdds
PILL, ICON = "pill", "icon"
PILL_SAFE = "safe"
ARROW_MARK = "→ "

Row = tuple[str, ...]


def decorate(tag: str, **extras: object) -> str:
    """``decorate("title", icon="sword")`` -> ``"title|icon=sword"``; True -> chỉ tên khóa."""
    parts = [tag] + [key if value is True else f"{key}={value}"
                     for key, value in extras.items() if value not in (None, False)]
    return "|".join(parts)


def base_tag(tag: str) -> str:
    """Tag màu gốc (bỏ phần trang trí)."""
    return tag.split("|", 1)[0]


def tag_extras(tag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in tag.split("|")[1:]:
        key, _, value = part.partition("=")
        out[key] = value
    return out


def is_bar(line: Row) -> bool:
    return base_tag(line[1]) == BAR


def _nums(values: Sequence[float]) -> str:
    return ",".join(f"{max(v, 0.0):.4g}" for v in values)


def odds_bar(fractions: Sequence[float], indent: int) -> Row:
    """Thanh 5 màu (Gãy, Hư tổn, Không đổi, Thành công, Xuất sắc), ưu tiên thấp."""
    return "", decorate(BAR, kind=ODDS, indent=indent, v=_nums(fractions)), LOW


def progress_bar(done: float, extra: float, target: float, indent: int, ok: bool) -> Row:
    """Thanh tiến độ: ``done`` (đặc) + ``extra`` (nhạt) so với vạch ``target``."""
    return "", decorate(BAR, kind=PROGRESS, indent=indent, ok="1" if ok else "0",
                        v=_nums((done, extra, target))), LOW


@dataclass(frozen=True)
class BarSpec:
    kind: str
    indent: int
    values: tuple[float, ...]
    ok: bool = True


def parse_bar(tag: str) -> BarSpec | None:
    if base_tag(tag) != BAR:
        return None
    extras = tag_extras(tag)
    try:
        values = tuple(float(v) for v in extras.get("v", "").split(",") if v)
        indent = int(extras.get("indent", "0"))
    except ValueError:
        return None
    return BarSpec(extras.get("kind", ""), indent, values, extras.get("ok", "1") != "0")


def odds_segments(fractions: Sequence[float], x0: int, width: int) -> list[tuple[int, int, str]]:
    """Chia ``width`` px theo tỉ lệ; làm tròn theo tổng cộng dồn nên các đoạn khít nhau và
    luôn phủ đúng ``width`` (bỏ đoạn 0 px)."""
    values = [max(v, 0.0) for v in fractions[:len(OUTCOMES)]]
    total = sum(values)
    if total <= 0 or width <= 0:
        return []
    out, acc, left = [], 0.0, x0
    for name, value in zip(OUTCOMES, values):
        acc += value
        right = x0 + round(width * acc / total)
        if right > left:
            out.append((left, right, name))
        left = right
    return out


@dataclass(frozen=True)
class ProgressGeometry:
    done: tuple[int, int]
    extra: tuple[int, int]
    marker: int  # x của vạch mục tiêu


def progress_geometry(done: float, extra: float, target: float, x0: int,
                      width: int) -> ProgressGeometry:
    """Thang đo = max(mục tiêu, done + extra): thanh không bao giờ tràn, vạch mục tiêu luôn thấy."""
    done, extra, target = max(done, 0.0), max(extra, 0.0), max(target, 0.0)
    scale = max(target, done + extra)
    if scale <= 0 or width <= 0:
        return ProgressGeometry((x0, x0), (x0, x0), x0 + max(width, 0))
    x_done = x0 + round(width * done / scale)
    x_extra = x0 + round(width * (done + extra) / scale)
    return ProgressGeometry((x0, x_done), (x_done, x_extra), x0 + round(width * target / scale))


def pill_span(text: str) -> tuple[int, int] | None:
    """Vị trí (đầu, cuối) của chữ kết luận trong dòng "    → ĐẬP · Kỳ vọng ...": sau mũi tên,
    tới dấu " · " đầu tiên (hoặc hết dòng). None nếu dòng không mở đầu bằng mũi tên."""
    start = len(text) - len(text.lstrip(" "))
    if not text.startswith(ARROW_MARK, start):
        return None  # dòng phụ của một dòng kết luận bị bọc: không có viên
    start += len(ARROW_MARK)
    end = text.find(SEP, start)
    end = len(text) if end < 0 else end
    return (start, end) if end > start else None


def with_icon(lines: list[Row], icon: str) -> list[Row]:
    """Gắn biểu tượng vào dòng đầu (tiêu đề phần); giữ nguyên chữ và mức ưu tiên."""
    if not lines:
        return lines
    first = lines[0]
    return [(first[0], decorate(first[1], icon=icon), *first[2:]), *lines[1:]]
