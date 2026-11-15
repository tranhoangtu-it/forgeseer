import json

from forgetax_overlay.run_log import RunRecord, append_run, load_runs, record_from_state, summary_line
from forgetax_overlay.save_reader import Relic, RunState


def _state(**overrides) -> RunState:
    base = dict(
        active=True, round=9, deadline_round=24, wallet=0, pending_tribute=0,
        successful_tributes=8, missed_tributes=3, ward_charges=0, sword_credits=0, rerolls=0,
        rewind_charges=0, shopping=False, finished=True, won=False, broken_swords=4,
        great_events=0, hold_events=0, damage_events=0, fever_events=0, gold_earned=52000,
        highest_grade=13, play_seconds=900.0, relics=(Relic("nail", 2), Relic("pin", 1)),
        offers=(), swords=(), consumables=0, run_id="abc",
    )
    return RunState(**{**base, **overrides})


def test_record_from_finished_state():
    rec = record_from_state(_state())

    assert rec == RunRecord(run_id="abc", round=9, won=False, gold_earned=52000,
                            highest_grade=13, missed_tributes=3, relics=("nail", "pin"))


def test_append_dedupes_by_run_id(tmp_path):
    log = tmp_path / "sub" / "runs.jsonl"
    rec = record_from_state(_state())

    assert append_run(log, rec, []) is True
    runs = load_runs(log)
    assert append_run(log, rec, runs) is False
    assert load_runs(log) == [rec]
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["run_id"] == "abc"


def test_load_runs_skips_broken_lines(tmp_path):
    log = tmp_path / "runs.jsonl"
    log.write_text('not json\n{"run_id": "x", "round": 3}\n', encoding="utf-8")

    assert load_runs(log) == [RunRecord("x", 3, False, 0, 0, 0, ())]
    assert load_runs(tmp_path / "missing.jsonl") == []


def test_summary_shows_best_and_last():
    runs = [RunRecord("a", 12, False, 90000, 15, 3, ()), RunRecord("b", 9, False, 52000, 13, 3, ())]

    text = summary_line(runs)

    assert text == ("Đã chơi 2 lượt · tốt nhất: ngày 12, cấp cao nhất +15"
                    " · gần nhất: ngày 9, cấp cao nhất +13")
    assert summary_line([]) == ""


def test_summary_marks_wins():
    assert "ngày 24 THẮNG" in summary_line([RunRecord("a", 24, True, 1, 20, 0, ())])
