import json

from forgetax_overlay.day_log import (DayTracker, append_day, day_record, load_day_keys,
                                      observe_day)
from forgetax_overlay.save_reader import RunState, Sword


def _sword(serial, value, grade) -> Sword:
    return Sword(serial=serial, grade=grade, value=value, peak=value, strikes=1, success_streak=0,
                 normal_hits=1, normal_successes=1, heated=False, broken=False, active=True,
                 rack=0, damage_count=0, fever_remaining=0.0)


def _state(round_, delivered=0, run_id="abc", finished=False, missed=0) -> RunState:
    return RunState(
        active=True, round=round_, deadline_round=24, wallet=0, pending_tribute=0,
        successful_tributes=0, missed_tributes=missed, ward_charges=0, sword_credits=0, rerolls=0,
        rewind_charges=0, shopping=False, finished=finished, won=False, broken_swords=0,
        great_events=0, hold_events=0, damage_events=0, fever_events=0, gold_earned=0,
        highest_grade=0, play_seconds=0.0, relics=(), offers=(),
        swords=(_sword(1, 3000, 6), _sword(2, 320, 0)), consumables=0, delivered=delivered,
        run_id=run_id)


def test_day_record_summarizes_state():
    rec = day_record(_state(5, delivered=1000, missed=1), quota=3350)

    assert (rec.run_id, rec.round, rec.quota, rec.delivered) == ("abc", 5, 3350, 1000)
    assert rec.holdings == 3320 and rec.top_grade == 6 and rec.missed == 1


def test_round_change_emits_last_snapshot_of_previous_day():
    tracker = DayTracker()
    tracker, out1 = observe_day(tracker, _state(5, delivered=0), 3350)
    tracker, out2 = observe_day(tracker, _state(5, delivered=3400), 3350)
    tracker, out3 = observe_day(tracker, _state(6, delivered=0), 4350)

    assert out1 is None and out2 is None
    assert out3.round == 5 and out3.delivered == 3400


def test_finished_run_emits_current_day():
    _, out = observe_day(DayTracker(), _state(19, finished=True, missed=3), 534000)

    assert out.round == 19 and out.missed == 3


def test_append_day_dedupes_by_run_and_round(tmp_path):
    path = tmp_path / "days.jsonl"
    rec = day_record(_state(5), 3350)
    keys = load_day_keys(path)

    assert append_day(path, rec, keys)
    keys = load_day_keys(path)
    assert not append_day(path, rec, keys)
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["round"] == 5
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
