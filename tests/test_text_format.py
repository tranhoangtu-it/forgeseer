from forgeseer.advisor import SwordOdds
from forgeseer.formatter import format_state
from forgeseer.reroll_advice import RerollCost, reroll_line
from forgeseer.save_reader import RunState, Sword
from forgeseer.text_format import (
    LINE_WIDTH, fmt_dec, fmt_int, fmt_pct, fmt_ratio, wrap_line, wrap_lines,
)


def test_fmt_int_uses_dot_for_thousands():
    assert fmt_int(44200) == "44.200"
    assert fmt_int(1280000) == "1.280.000"
    assert fmt_int(950) == "950"
    assert fmt_int(1799.6) == "1.800"
    assert fmt_int(-1500) == "-1.500"


def test_fmt_dec_uses_comma_for_decimals():
    assert fmt_dec(1.2149) == "1,21"
    assert fmt_dec(12345.5, 1) == "12.345,5"


def test_fmt_ratio_uses_times_sign_and_fewer_decimals_from_ten():
    assert fmt_ratio(1.2149) == "×1,21"
    assert fmt_ratio(65.65) == "×65,7"
    assert fmt_ratio(6.8, 1) == "×6,8"
    assert fmt_ratio(4834.6) == "×4.835"


def test_fmt_pct_keeps_whole_percent_by_default():
    assert fmt_pct(0.19) == "19%"
    assert fmt_pct(0.0) == "0%"
    assert fmt_pct(0.128, 1) == "12,8%"


def test_wrap_line_short_line_untouched():
    assert wrap_line("  Gãy 19%") == ["  Gãy 19%"]


def test_wrap_line_breaks_at_separator_with_deeper_indent():
    text = "    " + " · ".join(f"mục số {i} khá dài" for i in range(8))

    rows = wrap_line(text, width=40)

    assert all(len(r) <= 40 for r in rows)
    assert rows[0].startswith("    mục số 0")
    assert all(r.startswith("      mục") for r in rows[1:])
    assert " · ".join(r.strip() for r in rows) == text.strip()  # không mất chữ nào


def test_wrap_line_falls_back_to_spaces_without_separator():
    rows = wrap_line("  " + "chữ " * 30, width=30)

    assert len(rows) > 1 and all(len(r) <= 30 for r in rows)
    assert all(r.startswith("    ") for r in rows[1:])


def test_wrap_lines_keeps_color_tag():
    lines = wrap_lines([("a · " * 30, "warn")], width=20)

    assert len(lines) > 1 and {tag for _, tag in lines} == {"warn"}


def test_reroll_price_uses_vietnamese_thousands():
    text, _ = reroll_line(RerollCost(False, 1250), wallet=50000, has_good_offer=False)

    assert "1.250 G" in text


def _state(swords):
    return RunState(active=True, round=7, deadline_round=24, wallet=123456, pending_tribute=0,
                    successful_tributes=6, missed_tributes=0, ward_charges=1, sword_credits=1,
                    rerolls=0, rewind_charges=0, shopping=False, finished=False, won=False,
                    relics=(), offers=(), swords=swords, gold_earned=20000, highest_grade=10,
                    play_seconds=125.0, great_events=1, hold_events=3, damage_events=1,
                    fever_events=0, broken_swords=2, consumables=0)


def test_left_panel_lines_fit_width_and_sections_are_separated():
    sword = Sword(serial=1, grade=12, value=123456, peak=200000, strikes=40, success_streak=3,
                  normal_hits=30, normal_successes=20, heated=True, broken=False, active=True,
                  rack=2, damage_count=4, fever_remaining=0.0, charge=7, place=4)
    odds = SwordOdds.from_permille([190, 130, 160, 480, 40])

    lines = format_state(_state((sword,)), odds={1: (odds, odds)}, quota=50000,
                         schedule=(65500.0, 96400.0, 140000.0, 204000.0))

    assert all(len(text) <= LINE_WIDTH for text, _ in lines)
    assert ("", "normal") in lines
    text = "\n".join(t for t, _ in lines)
    assert "Gãy 19% · Hư tổn 13% · Không đổi 16% · Thành công 48% · Xuất sắc 4%" in text
    assert "+12 giá ô 3 · giá trị 123.456 (từng đạt 200.000) · đang nung" in text
    assert "Tích lực Xuất Thần: 7/10" in text
    assert "Cống đã nộp đủ: 6 lần · Lỡ: 0" in text
    assert "Vảy Rồng: 1 · Dây Cót: 0 · Lượt mua di vật: 1 · Lượt đổi hàng: 0" in text
    assert "Xuất Thần: ~7 nhát/lần" in text
    assert "cấp cao nhất +10" in text
    for jargon in ("EV", "G max", "XT ", "Relic", "Shop", "->", " | ", "Ward", "Reroll"):
        assert jargon not in text
