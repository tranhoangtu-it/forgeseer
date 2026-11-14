from forgetax_overlay.advisor import SwordOdds
from forgetax_overlay.save_reader import Sword
from forgetax_overlay.tribute import TributeStatus, tribute_override

RISKY = SwordOdds.from_permille([300, 50, 100, 500, 50])
SAFE = SwordOdds.from_permille([0, 50, 150, 700, 100])


def _sword(value: int) -> Sword:
    return Sword(serial=1, grade=10, value=value, peak=value, strikes=10, success_streak=0,
                 normal_hits=10, normal_successes=5, heated=False, broken=False, active=True,
                 rack=0, damage_count=0, fever_remaining=0.0)


def _status(quota: float, delivered: float, holdings: float) -> TributeStatus:
    return TributeStatus(quota=quota, delivered=delivered, holdings=holdings)


def test_status_shortfall_and_need():
    status = _status(2100, 500, 1000)

    assert status.need == 1600
    assert status.shortfall == 600


def test_enough_for_tribute_and_risky_strike_says_hold():
    verdict = tribute_override(_sword(3000), RISKY, _status(2100, 0, 3000), 1.5)

    assert verdict.startswith("DỪNG")


def test_enough_for_tribute_and_no_outcome_can_drop_below_quota_gives_no_override():
    # các kiếm khác (2000) + kiếm này kể cả khi bị Hư tổn (2000) vẫn >= 2100
    assert tribute_override(_sword(3000), SAFE, _status(2100, 0, 5000), 1.5) is None


def test_damage_alone_can_cause_tribute_shortfall():
    # không thể gãy nhưng Hư tổn (3000 -> 2000) làm thiếu cống 2100
    verdict = tribute_override(_sword(3000), SAFE, _status(2100, 0, 3000), 1.5)

    assert verdict.startswith("DỪNG") and "5%" in verdict


def test_short_of_tribute_says_strike_with_probability():
    verdict = tribute_override(_sword(1500), RISKY, _status(2100, 0, 1500), 1.5)

    assert verdict.startswith("ĐẬP") and "%" in verdict


def test_tribute_already_paid_gives_no_override():
    assert tribute_override(_sword(3000), RISKY, _status(2100, 2100, 3000), 1.5) is None
