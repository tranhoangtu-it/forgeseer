from forgeseer.panel_decor import (
    BAR, ODDS, PROGRESS, base_tag, decorate, is_bar, odds_bar, odds_segments, parse_bar,
    pill_span, progress_bar, progress_geometry, tag_extras, with_icon,
)
from forgeseer.text_format import LOW, is_low


def test_decorated_tag_keeps_base_color_and_extras():
    tag = decorate("good", pill=True, icon="sword", skip=None)

    assert tag == "good|pill|icon=sword"
    assert base_tag(tag) == "good"
    assert tag_extras(tag) == {"pill": "", "icon": "sword"}
    assert base_tag("warn") == "warn" and tag_extras("warn") == {}


def test_odds_bar_round_trips_and_is_low_priority():
    row = odds_bar((0.19, 0.03, 0.16, 0.48, 0.14), indent=4)

    spec = parse_bar(row[1])
    assert is_bar(row) and is_low(row) and row[0] == ""
    assert spec.kind == ODDS and spec.indent == 4
    assert spec.values == (0.19, 0.03, 0.16, 0.48, 0.14)


def test_progress_bar_keeps_the_ok_flag_both_ways():
    short = parse_bar(progress_bar(6000, 12620, 20100, 2, ok=False)[1])
    done = parse_bar(progress_bar(20100, 0, 20100, 2, ok=True)[1])

    assert short.kind == PROGRESS and short.values == (6000, 12620, 20100) and not short.ok
    assert done.ok


def test_parse_bar_ignores_other_tags_and_garbage():
    assert parse_bar("good|pill") is None
    assert parse_bar(f"{BAR}|kind=odds|v=x,y") is None


def test_odds_segments_tile_the_width_exactly():
    segments = odds_segments((0.19, 0.03, 0.16, 0.48, 0.14), 10, 300)

    assert [name for *_, name in segments] == ["break", "damage", "hold", "success", "great"]
    assert segments[0][0] == 10 and segments[-1][1] == 310
    assert all(a[1] == b[0] for a, b in zip(segments, segments[1:]))
    assert segments[3][1] - segments[3][0] == round(300 * 0.86) - round(300 * 0.38)


def test_odds_segments_skip_zero_outcomes_and_empty_input():
    segments = odds_segments((0, 0, 0.25, 0.6, 0.15), 0, 100)

    assert [name for *_, name in segments] == ["hold", "success", "great"]
    assert odds_segments((0, 0, 0, 0, 0), 0, 100) == []
    assert odds_segments((0.5, 0.5), 0, 0) == []


def test_progress_geometry_scales_to_the_larger_of_target_and_total():
    short = progress_geometry(6000, 12620, 20100, 0, 201)
    over = progress_geometry(30000, 0, 20000, 0, 300)

    assert short.done == (0, 60) and short.extra == (60, 186) and short.marker == 201
    assert over.done == (0, 300) and over.marker == 200  # mục tiêu vẫn thấy khi đã vượt


def test_progress_geometry_handles_nothing_to_show():
    geo = progress_geometry(0, 0, 0, 5, 100)

    assert geo.done == (5, 5) and geo.extra == (5, 5)


def test_pill_span_covers_the_verdict_after_the_arrow():
    text = "    → ĐẬP (an toàn) · kỳ vọng 1 nhát ×1,46"

    start, end = pill_span(text)

    assert text[start:end] == "ĐẬP (an toàn)"
    stop = "    → DỪNG"
    assert stop[slice(*pill_span(stop))] == "DỪNG"
    assert pill_span("      kỳ vọng tiếp theo") is None  # dòng phụ sau khi bọc dòng


def test_with_icon_tags_only_the_first_row_and_keeps_priority():
    lines = [("Thống kê:", "title", LOW), ("  a", "dim", LOW)]

    out = with_icon(lines, "stats")

    assert out[0] == ("Thống kê:", "title|icon=stats", LOW)
    assert out[1] == lines[1]
    assert with_icon([], "stats") == []
