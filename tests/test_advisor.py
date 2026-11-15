import pytest

from forgeseer.advisor import SwordOdds, advise


def _odds(destruction, damage, hold, success, great) -> SwordOdds:
    return SwordOdds.from_permille([destruction, damage, hold, success, great])


def test_from_permille_converts_to_fractions():
    odds = _odds(359, 42, 62, 496, 41)

    assert odds.destruction == pytest.approx(0.359)
    assert odds.great == pytest.approx(0.041)


def test_risky_high_grade_sword_says_stop():
    advice = advise(_odds(359, 42, 62, 496, 41), multiplier=1.5)

    assert advice.ev_ratio == pytest.approx(0.926, abs=0.002)
    assert advice.verdict == "DỪNG"


def test_no_destruction_and_positive_ev_says_safe_strike():
    advice = advise(_odds(0, 65, 97, 774, 64), multiplier=1.5)

    assert advice.ev_ratio > 1
    assert advice.verdict == "ĐẬP (an toàn)"


def test_positive_ev_with_risk_says_strike():
    advice = advise(_odds(100, 50, 50, 700, 100), multiplier=1.5)

    assert advice.verdict == "ĐẬP"
