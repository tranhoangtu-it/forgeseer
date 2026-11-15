from forgeseer.fever_calibration import (
    DEFAULT_FEVER_STRIKES, FeverStats, FeverTracker, load_fever_stats, observe, save_fever_stats,
)
from forgeseer.save_reader import Sword


def _sword(serial=1, strikes=10, fever=0.0, broken=False) -> Sword:
    return Sword(serial=serial, grade=3, value=900, peak=900, strikes=strikes, success_streak=0,
                 normal_hits=strikes, normal_successes=0, heated=False, broken=broken,
                 active=True, rack=-1, damage_count=0, fever_remaining=fever)


def test_stats_default_to_seven_without_samples():
    assert FeverStats().strikes == DEFAULT_FEVER_STRIKES == 7


def test_stats_running_average_rounds():
    stats = FeverStats().add(6).add(9)

    assert stats.samples == 2
    assert stats.strikes == 8  # (6 + 9) / 2 = 7.5 -> 8


def test_observe_counts_strikes_from_before_fever_until_it_ends():
    tracker = FeverTracker()
    # số liệu thật: nhát thứ 10 (thường) kích hoạt, rồi đập nhát 11..16 trong ~4 giây
    tracker, done = observe(tracker, [_sword(strikes=9)])
    tracker, done1 = observe(tracker, [_sword(strikes=10, fever=3.8)])
    tracker, done2 = observe(tracker, [_sword(strikes=15, fever=1.0)])
    tracker, done3 = observe(tracker, [_sword(strikes=16, fever=0.0)])

    assert done == done1 == done2 == []
    assert done3 == [6]


def test_observe_ignores_fever_already_running_when_first_seen():
    tracker, _ = observe(FeverTracker(), [_sword(strikes=12, fever=2.0)])
    tracker, done = observe(tracker, [_sword(strikes=14, fever=0.0)])

    assert done == []


def test_observe_closes_fever_when_sword_disappears():
    tracker, _ = observe(FeverTracker(), [_sword(strikes=10)])
    tracker, _ = observe(tracker, [_sword(strikes=13, fever=2.0)])  # nhát 11 kích hoạt bị lỡ
    tracker, done = observe(tracker, [])

    assert done == [2]


def test_observe_skips_zero_strike_fever():
    tracker, _ = observe(FeverTracker(), [_sword(strikes=10)])
    tracker, _ = observe(tracker, [_sword(strikes=10, fever=2.0)])
    tracker, done = observe(tracker, [_sword(strikes=10, fever=0.0)])

    assert done == []


def test_stats_persist_without_losing_other_config_keys(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"x": 5, "y": 6}', encoding="utf-8")

    save_fever_stats(cfg, FeverStats().add(8))

    assert load_fever_stats(cfg) == FeverStats(total=8, samples=1)
    assert '"x": 5' in cfg.read_text(encoding="utf-8")


def test_load_fever_stats_defaults_when_missing_or_broken(tmp_path):
    broken = tmp_path / "config.json"
    broken.write_text('{"fever": {"total": "x"}}', encoding="utf-8")

    assert load_fever_stats(tmp_path / "missing.json") == FeverStats()
    assert load_fever_stats(broken) == FeverStats()
