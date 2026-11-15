"""Định dạng chữ hiển thị trên overlay (dùng chung cho mọi khung).

- Số theo ngôn ngữ đang dùng: tiếng Việt 44.200 và 1,21; tiếng Anh 44,200 và 1.21...
  (dấu ngăn lấy từ khóa ``number.group`` / ``number.decimal`` của catalog).
- Hệ số nhân dùng "×", mũi tên "→", ngăn cách các ý bằng " · ".
- Dòng dài hơn ``LINE_WIDTH`` được tách thành dòng chính + dòng phụ thụt vào.
"""
from __future__ import annotations

import unicodedata

from .i18n import t

LINE_WIDTH = 72  # ~70 ký tự; đủ cho dòng 5 tỉ lệ kết quả thụt 4 khoảng trắng
SEP = " · "
ARROW = " → "
CONTINUATION_INDENT = 2  # dòng phụ thụt thêm so với dòng chính

Line = tuple[str, str]


def _localize(text: str) -> str:
    """'12,345.6' (định dạng Python) -> dấu ngăn của ngôn ngữ đang dùng."""
    group, decimal = t("number.group"), t("number.decimal")
    return text.replace(",", "\0").replace(".", decimal).replace("\0", group)


def fmt_int(value: float) -> str:
    """44200 -> '44.200' (tiếng Việt), '44,200' (tiếng Anh); làm tròn tới đơn vị."""
    return _localize(f"{value:,.0f}")


def fmt_dec(value: float, digits: int = 2) -> str:
    """1.2149 -> '1,21' (tiếng Việt), '1.21' (tiếng Anh)."""
    return _localize(f"{value:,.{digits}f}")


def fmt_ratio(value: float, digits: int | None = None) -> str:
    """Hệ số nhân: 1.2149 -> '×1,21', 65.65 -> '×65,7', 4834.6 -> '×4.835'
    (từ 10 giữ 1 số lẻ, từ 100 bỏ số lẻ)."""
    if digits is None:
        digits = 0 if abs(value) >= 100 else 1 if abs(value) >= 10 else 2
    return "×" + fmt_dec(value, digits)


def fmt_pct(fraction: float, digits: int = 0) -> str:
    """0.19 -> '19%', với digits=1: 0.195 -> '19,5%'."""
    return fmt_dec(fraction * 100, digits) + "%"


def _word_wrap(text: str, width: int, cont: str) -> list[str]:
    rows: list[str] = []
    row = ""
    for word in text.split(" "):
        if not word:
            continue
        if not row:
            row = (cont if rows else text[:len(text) - len(text.lstrip(" "))]) + word
        elif display_width(row) + 1 + display_width(word) > width:
            rows.append(row)
            row = cont + word
        else:
            row = f"{row} {word}"
        while display_width(row) > width:  # một "từ" quá dài (chữ Trung/Nhật không có dấu cách)
            head, row = _cut(row, width)
            rows.append(head)
            row = cont + row
    return rows + ([row] if row else [])


def _cut(text: str, width: int) -> tuple[str, str]:
    """Cắt ``text`` thành phần đầu vừa ``width`` cột và phần còn lại."""
    used = 0
    for i, ch in enumerate(text):
        used += display_width(ch)
        if used > width:
            i = max(i, 1)  # luôn tiến ít nhất một ký tự
            return text[:i], text[i:]
    return text, ""


def display_width(text: str) -> int:
    """Số cột khi hiển thị bằng font monospace: chữ Trung/Nhật/Hàn chiếm 2 cột."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def wrap_line(text: str, width: int = LINE_WIDTH) -> list[str]:
    """Tách dòng dài: ưu tiên ngắt ở " · ", không được thì ngắt ở khoảng trắng.

    Dòng phụ thụt vào thêm ``CONTINUATION_INDENT`` so với dòng chính.
    """
    if display_width(text) <= width:
        return [text]
    indent = len(text) - len(text.lstrip(" "))
    cont = " " * (indent + CONTINUATION_INDENT)
    parts = text.split(SEP)
    rows: list[str] = []
    row = parts[0]
    for part in parts[1:]:
        if display_width(row) + len(SEP) + display_width(part) <= width:
            row += SEP + part
        else:
            rows.append(row)
            row = cont + part.lstrip(" ")
    rows.append(row)
    out: list[str] = []
    for r in rows:
        out += [r] if display_width(r) <= width else _word_wrap(r, width, cont)
    return out


def wrap_lines(lines: list[Line], width: int = LINE_WIDTH) -> list[Line]:
    """Áp ``wrap_line`` cho mọi dòng, giữ nguyên tag màu."""
    return [(row, tag) for text, tag in lines for row in wrap_line(text, width)]
