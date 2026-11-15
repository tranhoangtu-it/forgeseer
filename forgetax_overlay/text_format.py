"""Định dạng chữ hiển thị trên overlay theo kiểu Việt Nam (dùng chung cho mọi khung).

- Số nguyên: dấu chấm ngăn hàng nghìn (44.200); số thập phân: dấu phẩy (1,21).
- Hệ số nhân dùng "×", mũi tên "→", ngăn cách các ý bằng " · ".
- Dòng dài hơn ``LINE_WIDTH`` được tách thành dòng chính + dòng phụ thụt vào.
"""
from __future__ import annotations

LINE_WIDTH = 72  # ~70 ký tự; đủ cho dòng 5 tỉ lệ kết quả thụt 4 khoảng trắng
SEP = " · "
ARROW = " → "
CONTINUATION_INDENT = 2  # dòng phụ thụt thêm so với dòng chính

Line = tuple[str, str]


def _swap_separators(text: str) -> str:
    """'12,345.6' (kiểu Anh) -> '12.345,6' (kiểu Việt)."""
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def fmt_int(value: float) -> str:
    """44200 -> '44.200' (làm tròn tới đơn vị)."""
    return _swap_separators(f"{value:,.0f}")


def fmt_dec(value: float, digits: int = 2) -> str:
    """1.2149 -> '1,21'."""
    return _swap_separators(f"{value:,.{digits}f}")


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
        elif len(row) + 1 + len(word) > width:
            rows.append(row)
            row = cont + word
        else:
            row = f"{row} {word}"
    return rows + ([row] if row else [])


def wrap_line(text: str, width: int = LINE_WIDTH) -> list[str]:
    """Tách dòng dài: ưu tiên ngắt ở " · ", không được thì ngắt ở khoảng trắng.

    Dòng phụ thụt vào thêm ``CONTINUATION_INDENT`` so với dòng chính.
    """
    if len(text) <= width:
        return [text]
    indent = len(text) - len(text.lstrip(" "))
    cont = " " * (indent + CONTINUATION_INDENT)
    parts = text.split(SEP)
    rows: list[str] = []
    row = parts[0]
    for part in parts[1:]:
        if len(row) + len(SEP) + len(part) <= width:
            row += SEP + part
        else:
            rows.append(row)
            row = cont + part.lstrip(" ")
    rows.append(row)
    out: list[str] = []
    for r in rows:
        out += [r] if len(r) <= width else _word_wrap(r, width, cont)
    return out


def wrap_lines(lines: list[Line], width: int = LINE_WIDTH) -> list[Line]:
    """Áp ``wrap_line`` cho mọi dòng, giữ nguyên tag màu."""
    return [(row, tag) for text, tag in lines for row in wrap_line(text, width)]
