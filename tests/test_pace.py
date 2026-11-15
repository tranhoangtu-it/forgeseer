from forgetax_overlay.advisor import GradeOddsTable, SwordOdds
from forgetax_overlay.pace import (evaluate_pace, pace_detail, holdings_expected, pace_line,
                                   risk_hint, schedule_lines)
from forgetax_overlay.planner import Plan
from forgetax_overlay.save_reader import Sword

SAFE = SwordOdds.from_permille([0, 50, 150, 700, 100])
RISKY = SwordOdds.from_permille([300, 50, 100, 500, 50])
FEVER = SwordOdds.from_permille([0, 50, 100, 750, 100])


def _sword(serial, value, grade, fever=0.0, charge=0) -> Sword:
    return Sword(serial=serial, grade=grade, value=value, peak=value, strikes=5, success_streak=0,
                 normal_hits=5, normal_successes=3, heated=False, broken=False, active=True,
                 rack=0, damage_count=0, fever_remaining=fever, charge=charge)


def test_schedule_lines_list_days_from_tomorrow_three_per_row():
    rows = schedule_lines(15, (290000.0, 410000.0, 534000.0, 824000.0))

    assert rows == ["Cống sắp tới: ngày 16: 290.000 · ngày 17: 410.000 · ngày 18: 534.000",
                    "  ngày 19: 824.000"]


def test_schedule_lines_empty_without_data():
    assert schedule_lines(15, ()) == []


def test_pace_covers_days_while_resources_last():
    # hôm nay cần 1000; các ngày tới 2000, 3000, 10000; kỳ vọng 5000 + 500/ngày
    pace = evaluate_pace(expected=5000, incoming_per_day=500, need_today=1000,
                         schedule=(2000, 3000, 10000))

    assert pace.covered_days == 2           # ngày 1: 5500 >= 3000; ngày 2: 6000 >= 6000
    assert pace.behind
    assert pace.shortfall == 16000 - 6500   # 3 ngày tới: cần 16000, có 5000 + 3*500


def test_pace_ahead_when_resources_exceed_three_days():
    pace = evaluate_pace(expected=50000, incoming_per_day=0, need_today=0,
                         schedule=(2000, 3000, 4000, 100000))

    assert pace.covered_days == 3
    assert not pace.behind
    assert pace.comfortable


def test_pace_uses_only_available_days():
    pace = evaluate_pace(expected=3000, incoming_per_day=0, need_today=0, schedule=(2000,))

    assert pace.days == 1 and pace.covered_days == 1 and not pace.behind


def test_pace_none_without_schedule():
    assert evaluate_pace(expected=3000, incoming_per_day=0, need_today=100, schedule=()) is None


def test_pace_line_texts():
    behind = evaluate_pace(5000, 500, 1000, (2000, 3000, 10000))
    ahead = evaluate_pace(50000, 0, 0, (2000, 3000, 4000))

    assert pace_line(behind)[0] == "Chậm tiến độ: thiếu 9.500 cống cho 3 ngày tới"
    assert pace_line(ahead)[0] == "Tiến độ: đủ cống cho 3 ngày tới"
    assert pace_detail(behind) == "Ước tính sẽ có 6.500 / cần 16.000"


def test_holdings_expected_uses_plan_ratio_or_value():
    table = GradeOddsTable(normal={g: SAFE for g in range(40)},
                           fever={g: FEVER for g in range(40)}, valid=True)
    swords = [_sword(1, 1000, 3)]

    with_table = holdings_expected(swords, table, 1.5)
    without = holdings_expected(swords, None, 1.5)

    assert with_table > 1500
    assert without == 1000


def _plan(ratio, to_fever=5):
    return Plan(ratio=ratio, verdict="ĐẬP" if ratio > 1 else "DỪNG", strikes_to_fever=to_fever)


def test_behind_pace_pushes_top_sword_with_ward():
    pace = evaluate_pace(5000, 0, 0, (20000,))

    hint = risk_hint(_sword(1, 4000, 9), _plan(1.4), RISKY, pace, ward_charges=1,
                     tribute_locked=False)

    assert hint.startswith("Đang chậm tiến độ → đẩy +9")
    assert "Vảy Rồng" in hint


def test_behind_pace_mentions_fever_when_close():
    pace = evaluate_pace(5000, 0, 0, (20000,))

    hint = risk_hint(_sword(1, 4000, 9), _plan(1.4, to_fever=1), RISKY, pace, 0, False)

    assert "Xuất Thần" in hint


def test_ahead_pace_warns_against_risky_strike():
    pace = evaluate_pace(500000, 0, 0, (2000, 3000, 4000))

    hint = risk_hint(_sword(1, 4000, 9), _plan(1.2), RISKY, pace, 0, False)

    assert hint.startswith("Đang dư tiến độ → chơi an toàn, đừng mạo hiểm +9")


def test_risk_hint_never_overrides_todays_tribute_lock():
    pace = evaluate_pace(5000, 0, 0, (20000,))

    assert risk_hint(_sword(1, 4000, 9), _plan(1.4), RISKY, pace, 1, tribute_locked=True) is None


def test_no_hint_for_safe_strike_when_ahead():
    pace = evaluate_pace(500000, 0, 0, (2000, 3000, 4000))

    assert risk_hint(_sword(1, 4000, 9), _plan(1.2), SAFE, pace, 0, False) is None
