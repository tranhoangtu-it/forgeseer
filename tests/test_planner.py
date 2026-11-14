import pytest

from forgetax_overlay.advisor import SwordOdds
from forgetax_overlay.planner import FEVER_THRESHOLD, plan_sword

SAFE = SwordOdds.from_permille([0, 50, 150, 700, 100])
DEADLY = SwordOdds.from_permille([900, 10, 30, 50, 10])
FEVER = SwordOdds.from_permille([0, 50, 100, 750, 100])


def _table(odds, grades=range(0, 30)):
    return {g: odds for g in grades}


def test_safe_odds_everywhere_says_strike_with_gain():
    plan = plan_sword(grade=3, charge=0, normal=_table(SAFE), fever=_table(FEVER), multiplier=1.5)

    assert plan.verdict == "ĐẬP"
    assert plan.ratio > 1.5


def test_deadly_odds_without_fever_says_stop():
    plan = plan_sword(grade=10, charge=0, normal=_table(DEADLY), fever=_table(FEVER), multiplier=1.5)

    assert plan.verdict == "DỪNG"
    assert plan.ratio == pytest.approx(1.0)


def test_fever_ready_makes_deadly_grade_worth_striking():
    # đủ tích lực: nhát kế tiếp vào Xuất Thần (không gãy) -> nên đập dù tỉ lệ thường rất tệ
    plan = plan_sword(grade=10, charge=FEVER_THRESHOLD, normal=_table(DEADLY),
                      fever=_table(FEVER), multiplier=1.5)

    assert plan.verdict == "ĐẬP"
    assert plan.strikes_to_fever == 0


def test_strikes_to_fever_counts_down():
    plan = plan_sword(grade=0, charge=7, normal=_table(SAFE), fever=_table(FEVER), multiplier=1.5)

    assert plan.strikes_to_fever == FEVER_THRESHOLD - 7


def test_missing_grade_returns_none():
    assert plan_sword(grade=50, charge=0, normal=_table(SAFE), fever=_table(FEVER),
                      multiplier=1.5) is None
