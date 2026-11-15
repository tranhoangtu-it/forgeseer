"""Numbers for the "Stats" tab, from runs.jsonl (finished runs) and days.jsonl (day snapshots).

Pure: takes the loaded records, returns plain values the tab draws.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .day_log import DayRecord
from .run_log import RunRecord


@dataclass(frozen=True)
class RunStats:
    runs: int
    wins: int
    best_day: int
    avg_day: float
    end_days: tuple[tuple[int, int], ...]   # (day the run ended, how many runs), lost runs only
    grade_trend: tuple[int, ...]            # highest grade of each run, oldest first
    first_miss_avg: float | None            # average day of the first missed tribute
    first_miss_runs: int


def first_miss_days(days: list[DayRecord]) -> dict[str, int]:
    """Run id -> first day whose snapshot shows a missed tribute."""
    first: dict[str, int] = {}
    for d in days:
        if d.missed > 0 and d.round < first.get(d.run_id, 10**9):
            first[d.run_id] = d.round
    return first


def run_stats(runs: list[RunRecord], days: list[DayRecord] = ()) -> RunStats | None:
    if not runs:
        return None
    ends = Counter(r.round for r in runs if not r.won)
    misses = list(first_miss_days(list(days)).values())
    return RunStats(
        runs=len(runs), wins=sum(r.won for r in runs),
        best_day=max(r.round for r in runs),
        avg_day=sum(r.round for r in runs) / len(runs),
        end_days=tuple(sorted(ends.items())),
        grade_trend=tuple(r.highest_grade for r in runs),
        first_miss_avg=sum(misses) / len(misses) if misses else None,
        first_miss_runs=len(misses),
    )
