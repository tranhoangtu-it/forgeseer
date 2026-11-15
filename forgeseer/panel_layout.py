"""Co một khung overlay cho vừa vùng làm việc của màn hình. Hàm thuần, không phụ thuộc Tk.

Cỡ chữ tính bằng point nên khung to theo mức scale của Windows: khung chi tiết vừa khít ở 4K
100% nhưng tràn màn hình ở 1080p hay 1440p. ``fit_layout`` thử lần lượt:

1. cỡ chữ người chơi chọn, rồi giảm dần tới ``MIN_FONT``;
2. chế độ gọn: bỏ các dòng ưu tiên thấp (``text_format.LOW``), lấy cỡ chữ lớn nhất vừa;
3. chia hai cột nếu hai cột vẫn chỉ chiếm ≤ 50% bề rộng vùng làm việc (không cắt ngang khối
   của một kiếm / một món hàng nếu tránh được);
4. cuối cùng: cắt bớt, thay phần thiếu bằng dòng "… +N" (các dòng cuối ``pinned_tail`` luôn giữ).

Kích thước chữ (``FontMetrics``) được đo một lần từ Tk lúc chạy rồi truyền vào.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .i18n import t
from .text_format import display_width, is_low

MIN_FONT = 8
PAD_X, PAD_Y = 10, 8  # padx/pady của ô chữ (overlay_windows._make_text)
COLUMN_GAP = 3  # số cột trắng giữa hai cột chữ
COLUMNS_MAX_SHARE = 0.5  # hai cột chỉ dùng khi tổng bề rộng ≤ 50% bề rộng vùng làm việc
BLOCK_INDENT = 2  # dòng thụt ≤ 2 khoảng trắng mở đầu một khối (tiêu đề, một kiếm, một món hàng)
DIM = "dim"

Row = tuple[str, ...]  # (chữ, tag màu[, LOW])


@dataclass(frozen=True)
class FontMetrics:
    line_height: int  # px mỗi dòng (linespace)
    char_width: int   # px mỗi cột (bề rộng chữ "0", Tk tính bề rộng ô chữ theo nó)


@dataclass(frozen=True)
class Layout:
    font_size: int
    columns: tuple[tuple[Row, ...], ...]  # 1 hoặc 2 cột
    width: int   # px, ước tính
    height: int  # px, ước tính
    compact: bool = False  # đã bỏ dòng ưu tiên thấp
    hidden: int = 0        # số dòng bị cắt (dòng "… +N")


def _cols(lines: Sequence[Row]) -> int:
    return max((display_width(line[0]) for line in lines), default=0)


def _single_size(lines: Sequence[Row], m: FontMetrics) -> tuple[int, int]:
    return (_cols(lines) + 1) * m.char_width + 2 * PAD_X, len(lines) * m.line_height + 2 * PAD_Y


def _pair_size(left: Sequence[Row], right: Sequence[Row], m: FontMetrics) -> tuple[int, int]:
    cols = _cols(left) + COLUMN_GAP + _cols(right) + 1
    rows = max(len(left), len(right))
    return cols * m.char_width + 2 * PAD_X, rows * m.line_height + 2 * PAD_Y


def _is_blank(line: Row) -> bool:
    return not line[0].strip()


def compact_lines(lines: Sequence[Row]) -> list[Row]:
    """Bỏ dòng ưu tiên thấp, gộp các dòng trống liền nhau và bỏ dòng trống ở đầu."""
    out: list[Row] = []
    for line in lines:
        if is_low(line):
            continue
        if _is_blank(line) and (not out or _is_blank(out[-1])):
            continue
        out.append(line)
    return out


def _trim(lines: Sequence[Row]) -> list[Row]:
    lines = list(lines)
    while lines and _is_blank(lines[0]):
        lines.pop(0)
    while lines and _is_blank(lines[-1]):
        lines.pop()
    return lines


def _starts_block(line: Row) -> bool:
    text = line[0]
    return _is_blank(line) or len(text) - len(text.lstrip(" ")) <= BLOCK_INDENT


def split_columns(lines: Sequence[Row], m: FontMetrics, max_width: int,
                  max_height: int) -> tuple[list[Row], list[Row]] | None:
    """Chia hai cột thấp nhất có thể; ưu tiên ngắt giữa hai phần, rồi ở đầu một khối.
    None nếu không vừa."""
    indices = range(1, len(lines))
    for candidates in ([i for i in indices if _is_blank(lines[i])],
                       [i for i in indices if _starts_block(lines[i])], list(indices)):
        best: tuple[int, list[Row], list[Row]] | None = None
        for i in candidates:
            left, right = _trim(lines[:i]), _trim(lines[i:])
            width, height = _pair_size(left, right, m)
            if width <= max_width and height <= max_height and (best is None or height < best[0]):
                best = (height, left, right)
        if best is not None:
            return best[1], best[2]
    return None


def _truncate(lines: Sequence[Row], m: FontMetrics, max_height: int,
              pinned_tail: int) -> tuple[list[Row], int]:
    tail = list(lines[len(lines) - pinned_tail:]) if pinned_tail else []
    head = list(lines[:len(lines) - len(tail)])
    capacity = (max_height - 2 * PAD_Y) // m.line_height - len(tail) - 1  # 1 dòng "… +N"
    shown = _trim(head[:max(capacity, 0)])
    hidden = sum(1 for line in head[len(shown):] if not _is_blank(line))
    if hidden == 0:
        return list(lines), 0
    return shown + [(t("layout.more", count=hidden), DIM)] + tail, hidden


def fit_layout(lines: Sequence[Row], metrics: Mapping[int, FontMetrics], max_width: int,
               max_height: int, font_size: int, min_font: int = MIN_FONT,
               pinned_tail: int = 0) -> Layout:
    """Bố cục vừa ``max_width`` × ``max_height`` px (xem các bước ở đầu module)."""
    sizes = [s for s in range(max(font_size, min_font), min_font - 1, -1) if s in metrics]
    if not sizes:
        raise ValueError(f"no font metrics for sizes {min_font}..{font_size}")
    full = list(lines)
    short = compact_lines(full)
    passes = [(full, False)] + ([(short, True)] if short != full else [])
    for rows, compact in passes:
        for size in sizes:
            width, height = _single_size(rows, metrics[size])
            if width <= max_width and height <= max_height:
                return Layout(size, (tuple(rows),), width, height, compact)
    compact = short != full
    for size in sizes:
        split = split_columns(short, metrics[size], int(max_width * COLUMNS_MAX_SHARE), max_height)
        if split is not None:
            width, height = _pair_size(*split, metrics[size])
            return Layout(size, (tuple(split[0]), tuple(split[1])), width, height, compact)
    m = metrics[sizes[-1]]
    rows, hidden = _truncate(short, m, max_height, pinned_tail)
    width, height = _single_size(rows, m)
    return Layout(sizes[-1], (tuple(rows),), width, height, compact, hidden)
