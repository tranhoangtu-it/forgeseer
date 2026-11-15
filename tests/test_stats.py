import json

from forgeseer.day_log import DayRecord, load_days
from forgeseer.run_log import RunRecord
from forgeseer.stats import first_miss_days, run_stats
from forgeseer.stats_tab import summary_lines


def _run(day, won=False, grade=10, run_id="r") -> RunRecord:
    return RunRecord(run_id=run_id, round=day, won=won, gold_earned=0, highest_grade=grade,
                     missed_tributes=3, relics=())


def _day(run_id, day, missed) -> DayRecord:
    return DayRecord(run_id, day, 1000.0, 0, 0, 5, missed)


def test_run_stats_summarizes_runs():
    stats = run_stats([_run(9, grade=12), _run(12, grade=14), _run(9, grade=9),
                       _run(24, won=True, grade=22)])

    assert stats.runs == 4 and stats.wins == 1 and stats.best_day == 24
    assert stats.avg_day == 13.5
    assert stats.end_days == ((9, 2), (12, 1))
    assert stats.grade_trend == (12, 14, 9, 22)
    assert stats.first_miss_avg is None


def test_run_stats_none_without_runs():
    assert run_stats([]) is None
    assert summary_lines(None) == [summary_lines(None)[0]]


def test_first_missed_tribute_day_per_run():
    days = [_day("a", 5, 0), _day("a", 8, 1), _day("a", 7, 1), _day("b", 3, 0), _day("c", 11, 2)]

    assert first_miss_days(days) == {"a": 7, "c": 11}
    stats = run_stats([_run(9)], days)
    assert stats.first_miss_avg == 9.0 and stats.first_miss_runs == 2


def test_summary_lines_in_vietnamese():
    lines = summary_lines(run_stats([_run(9), _run(12)], [_day("a", 7, 1)]))

    assert lines[0] == "Đã chơi 2 lượt · thắng 0 · xa nhất ngày 12 · trung bình ngày 10,5"
    assert lines[1] == "Lỡ cống lần đầu trung bình ở ngày 7,0 (1 lượt)"


def test_load_days_skips_broken_lines(tmp_path):
    path = tmp_path / "days.jsonl"
    good = {"run_id": "a", "round": 4, "quota": 3350.0, "delivered": 3400, "holdings": 900,
            "top_grade": 6, "missed": 0}
    path.write_text(json.dumps(good) + "\nnot json\n" + json.dumps({"round": 1}) + "\n[]\n",
                    encoding="utf-8")

    assert load_days(path) == [DayRecord("a", 4, 3350.0, 3400, 900, 6, 0)]
    assert load_days(tmp_path / "missing.jsonl") == []
