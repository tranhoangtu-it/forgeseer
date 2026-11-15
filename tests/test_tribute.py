from forgeseer.advisor import SwordOdds
from forgeseer.save_reader import Sword
from forgeseer.tribute import TributeStatus, choose_tribute, tribute_override

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


def _s(serial: int, value: int) -> Sword:
    return Sword(serial=serial, grade=5, value=value, peak=value, strikes=1, success_streak=0,
                 normal_hits=1, normal_successes=1, heated=False, broken=False, active=True,
                 rack=0, damage_count=0, fever_remaining=0.0)


def test_choose_tribute_minimizes_lost_future_value():
    # greedy theo giá trị nhỏ sẽ nộp 1000+1500 (mất 1000*3 + 1500*1); tối ưu: nộp 2600 (mất 2600)
    swords = [_s(1, 1000), _s(2, 1500), _s(3, 2600)]
    ratios = {1: 3.0, 2: 1.0, 3: 1.0}

    chosen = choose_tribute(swords, need=2500, ratios=ratios)

    assert [s.serial for s in chosen] == [3]


def test_choose_tribute_tie_breaks_on_smallest_overpay():
    swords = [_s(1, 3000), _s(2, 2600), _s(3, 9000)]

    chosen = choose_tribute(swords, need=2500, ratios={})

    assert [s.serial for s in chosen] == [2]


def test_choose_tribute_combines_swords_sorted_by_value():
    swords = [_s(1, 9000), _s(2, 2000), _s(3, 1500)]

    chosen = choose_tribute(swords, need=3000, ratios={1: 1.0, 2: 1.0, 3: 1.0})

    assert [s.serial for s in chosen] == [3, 2]


def test_choose_tribute_empty_when_not_enough():
    assert choose_tribute([_s(1, 100)], need=3000, ratios={}) == []


def test_choose_tribute_falls_back_to_greedy_for_many_swords():
    swords = [_s(i, 100) for i in range(1, 21)]

    chosen = choose_tribute(swords, need=550, ratios={})

    assert sum(s.value for s in chosen) == 600
