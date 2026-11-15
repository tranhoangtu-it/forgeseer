from forgetax_overlay.legend import legend_lines
from forgetax_overlay.text_format import LINE_WIDTH


def _text():
    return "\n".join(text for text, _ in legend_lines())


def test_legend_title_mentions_f7():
    assert legend_lines()[0] == ("Chú giải (F7 để tắt)", "title")


def test_legend_explains_every_overlay_term():
    text = _text()

    for term in ("kỳ vọng ×", "Kế hoạch nhiều nhát", "Tiến độ", "Xuất Thần & tích lực",
                 "Cống hôm nay / ngày mai", "giá ô N", "dưới sàn", "trên đe", "bàn cống",
                 "đang cầm", "có thể bỏ / nên bỏ nhất", "★", "an toàn", "Hư tổn", "Không đổi",
                 "Xuất sắc", "Lượt mua di vật", "Lượt đổi hàng"):
        assert term in text, term


def test_legend_says_above_one_is_profit():
    assert "Trên ×1 là có lời" in _text()


def test_legend_lines_fit_width():
    assert all(len(text) <= LINE_WIDTH for text, _ in legend_lines())
