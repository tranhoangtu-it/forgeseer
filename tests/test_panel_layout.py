import math

import pytest

from forgeseer.panel_layout import (
    MIN_FONT, FontMetrics, compact_lines, fit_layout, split_columns,
)
from forgeseer.text_format import LOW, is_low

TASKBAR_PX = 48  # thanh taskbar Windows 11 ở 100%
MARGIN = 20      # overlay.PANEL_MARGIN


def consolas_metrics(scale: float) -> dict[int, FontMetrics]:
    """Ước lượng Consolas: dòng ≈ 1,17 em, một cột ≈ 0,55 em; 1pt = 96/72 px ở 100%."""
    out = {}
    for size in range(8, 17):
        em = size * scale * 96 / 72
        out[size] = FontMetrics(math.ceil(em * 1.17), round(em * 0.55))
    return out


def available(width: int, height: int, scale: float) -> tuple[int, int]:
    return width - 2 * MARGIN, height - round(TASKBAR_PX * scale) - 2 * MARGIN


def realistic_lines() -> list[tuple[str, ...]]:
    """~120 dòng giống khung chi tiết khi cửa hàng đang mở và có 8 nhóm kiếm."""
    lines: list[tuple[str, ...]] = [("ForgeTax", "title"),
                                    ("Ngày 7/24 (còn 17 ngày) · Vàng 12.345", "good"),
                                    ("Cống nạp đã xong: 6 · Lỡ cống: 0", "normal"),
                                    ("Hộ phù 1 · Quay ngược 0 · Phiếu kiếm 3 · Đổi 2", "normal"),
                                    ("", "normal"),
                                    ("Cống hôm nay 8.700 G · đã nộp 0 G → thiếu 2.000 G", "warn"),
                                    ("  Kiếm đang có: 6.700 G", "normal")]
    lines += [(f"  Ngày {d}: {d * 1000} G", "dim") for d in range(8, 13)]
    lines += [("  Tiến độ: chậm", "warn"), ("    chi tiết tiến độ", "dim"), ("", "normal"),
              ("Kiếm (12):", "title")]
    for i in range(8):
        lines += [(f"  +{i} trên giá {i}: 1.000 G", "normal"),
                  ("    Đã đập 3 nhát · Chuỗi 1 · Tỉ lệ 60%", "dim", LOW),
                  ("    Gãy 19% · Hư tổn 3% · Không đổi 16% · Thành công 48% · Xuất sắc 14%",
                   "normal"),
                  ("    → ĐẬP · Kỳ vọng 1 nhát ×1,21", "good"),
                  ("    Kế hoạch: ĐẬP tiếp ×2,5 · Xuất Thần sau 4 nhát", "dim", LOW)]
    lines += [("  Tổng giá trị: 8.000 G", "good"), ("", "normal"), ("Di vật (4):", "title")]
    lines += [(f"  Di vật {i}", "normal") for i in range(4)]
    lines += [("", "normal"), ("Di vật giảm Gãy:", "title", LOW)]
    lines += [(f"  Món {i}" if i % 2 == 0 else "      Gãy +8: 5% → 4% · +12: 15% → 11%", "dim",
               LOW) for i in range(18)]
    lines += [("", "normal"), ("Cửa hàng di vật:", "title")]
    for i in range(4):
        lines += [(f"  Món bán {i} · 1.200 G", "good"),
                  ("      mô tả dòng một của món hàng khá dài để chiếm chỗ", "dim", LOW),
                  ("      mô tả dòng hai", "dim", LOW),
                  ("    Mua: Gãy 19% → 15%", "good"), ("    Theo cấp: +8 · +12", "dim")]
    lines += [("", "normal"), ("Thống kê:", "title", LOW)]
    lines += [(f"  thống kê {i}", "dim", LOW) for i in range(4)]
    lines += [("", "normal"), ("Đọc trực tiếp 12:00:00", "dim"),
              ("F6 cài đặt · F7 chú giải · F8 ẩn · F9 di chuyển · F10 thoát", "dim")]
    return lines


CONFIGS = [  # (rộng, cao, scale)
    (1920, 1080, 1.0), (1920, 1080, 1.25), (2560, 1440, 1.0), (2560, 1440, 1.25),
    (3440, 1440, 1.0), (3840, 2160, 1.0), (3840, 2160, 1.5),
]


@pytest.mark.parametrize("width, height, scale", CONFIGS)
def test_layout_always_fits_work_area(width, height, scale):
    lines = realistic_lines()
    max_w, max_h = available(width, height, scale)

    layout = fit_layout(lines, consolas_metrics(scale), max_w, max_h, 10, pinned_tail=3)

    assert len(lines) >= 90
    assert layout.height <= max_h
    assert layout.width <= max_w
    assert MIN_FONT <= layout.font_size <= 10
    shown = [line for column in layout.columns for line in column]
    assert shown[-1] == lines[-1] and shown[-2] == lines[-2]  # trạng thái + phím tắt luôn còn
    kept_low = any(is_low(line) for line in shown)
    dropped_high = any(line not in shown for line in lines if not is_low(line) and line[0].strip())
    assert not (kept_low and dropped_high)  # dòng quan trọng không bao giờ mất trước dòng phụ


def test_4k_at_100_percent_keeps_user_font_and_every_line():
    lines = realistic_lines()

    layout = fit_layout(lines, consolas_metrics(1.0), *available(3840, 2160, 1.0), 10,
                        pinned_tail=3)

    assert layout.font_size == 10
    assert layout.columns == (tuple(lines),)
    assert not layout.compact and layout.hidden == 0


def test_1080p_shrinks_font_before_dropping_lines():
    lines = realistic_lines()[:70]

    layout = fit_layout(lines, consolas_metrics(1.0), *available(1920, 1080, 1.0), 10)

    assert layout.font_size < 10
    assert layout.columns == (tuple(lines),)


def test_compact_keeps_headers_swords_and_warnings():
    lines = realistic_lines()

    short = compact_lines(lines)

    assert not any(is_low(line) for line in short)
    for line in lines:
        if not is_low(line) and line[0].strip():
            assert line in short
    assert all(short[i][0].strip() or short[i + 1][0].strip() for i in range(len(short) - 1))
    assert short[0][0].strip()


def test_two_columns_never_split_a_sword_block():
    lines = compact_lines(realistic_lines())
    m = consolas_metrics(1.0)[8]

    left, right = split_columns(lines, m, 2000, 10_000)

    assert not right[0][0].startswith("    ")  # cột phải mở đầu bằng một khối, không phải dòng phụ


def test_truncates_with_localized_more_line_when_nothing_else_fits():
    lines = [(f"  dòng {i}", "normal") for i in range(200)] + [("status", "dim"), ("hint", "dim")]

    layout = fit_layout(lines, consolas_metrics(1.0), 300, 400, 10, pinned_tail=2)

    (column,) = layout.columns
    assert layout.font_size == MIN_FONT and layout.hidden > 0
    assert layout.height <= 400
    assert column[-3][0] == f"… còn {layout.hidden} dòng nữa (khung đã thu gọn cho vừa màn hình)"
    assert column[-2:] == (("status", "dim"), ("hint", "dim"))
    assert len(column) - 3 + layout.hidden == 200


def test_raises_without_metrics():
    with pytest.raises(ValueError):
        fit_layout([("a", "normal")], {}, 100, 100, 10)
