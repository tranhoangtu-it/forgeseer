"""Inputs of the whole-run Monte Carlo: where the run stands and the numbers it plays with.

Everything comes from the game when we have it (odds by grade from the game's odds function,
the tribute schedule from the game's tribute function, the swords on hand). What we don't have
is filled in with documented guesses:

- tribute after the live schedule: the curve measured in docs/technical-notes.md, days that were
  never measured are geometric means of their neighbours;
- no odds table (save file only, not connected to the game): ``assumed_odds``, a rough curve
  shaped like the real one. The result is then flagged as an estimate;
- 3 fresh +0 swords a day (``pace.FRESH_SWORDS_PER_DAY``), missing the tribute 3 times ends
  the run, a missed tribute keeps the swords and delivers nothing.

Only probabilities. The game's RNG state is never read or predicted.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from ..advisor import GradeOddsTable, SwordOdds
from ..fever_calibration import DEFAULT_FEVER_STRIKES
from ..save_reader import RunState

DEFAULT_DEADLINE = 24
DEFAULT_MULTIPLIER = 1.5
MISSES_TO_LOSE = 3
ASSUMED_MAX_GRADE = 40

# Base tribute by day (balanceRevision 2, see docs/technical-notes.md).
QUOTA_CURVE: dict[int, float] = {
    1: 1800, 2: 2100, 3: 2600, 4: 3350, 5: 4350, 6: 5700, 7: 8700, 8: 13200, 9: 20100,
    10: 29500, 11: 44200, 12: 65500, 13: 96400, 14: 140000, 15: 204000, 16: 290000,
    17: 413000, 18: 534000, 20: 824000, 22: 1280000, 24: 2000000,
}


def curve_quota(day: int) -> float:
    """Tribute of ``day`` from the measured curve; gaps are geometric means, past the end the
    last day-to-day growth continues."""
    if day in QUOTA_CURVE:
        return float(QUOTA_CURVE[day])
    known = sorted(QUOTA_CURVE)
    if day < known[0]:
        return float(QUOTA_CURVE[known[0]])
    lower = max(d for d in known if d < day)
    upper = min((d for d in known if d > day), default=None)
    if upper is None:
        prev = max(d for d in known if d < lower)
        step = (QUOTA_CURVE[lower] / QUOTA_CURVE[prev]) ** (1 / (lower - prev))
        return QUOTA_CURVE[lower] * step ** (day - lower)
    frac = (day - lower) / (upper - lower)
    return math.exp(math.log(QUOTA_CURVE[lower]) * (1 - frac)
                    + math.log(QUOTA_CURVE[upper]) * frac)


def assumed_odds(max_grade: int = ASSUMED_MAX_GRADE) -> GradeOddsTable:
    """Stand-in odds when the game's table isn't available. Shaped like the real one (no break
    at +0..+2, then rising), but it is a guess and the UI says so."""
    normal, fever = {}, {}
    for g in range(max_grade + 1):
        brk = min(0.6, max(0.0, 0.04 * (g - 2)))
        dmg = 0.0 if g < 3 else 0.10
        great = 0.05
        success = max(0.12, 0.70 - 0.035 * g)
        hold = max(0.0, 1.0 - brk - dmg - great - success)
        normal[g] = SwordOdds(brk, dmg, hold, success, great)
        f_success = min(0.80, success + 0.25)
        fever[g] = SwordOdds(0.0, 0.0, max(0.0, 1.0 - f_success - 0.10), f_success, 0.10)
    return GradeOddsTable(normal=normal, fever=fever, valid=True)


@dataclass(frozen=True)
class SimSword:
    grade: int
    value: float
    charge: int = 0


@dataclass(frozen=True)
class SimInput:
    day: int                          # today (its tribute is still due)
    deadline: int                     # last day of the contract
    swords: tuple[SimSword, ...]      # swords on hand
    need_today: float                 # tribute still missing today
    quotas: tuple[float, ...]         # tribute for day+1 .. deadline
    normal: dict[int, SwordOdds] = field(default_factory=dict)
    fever: dict[int, SwordOdds] = field(default_factory=dict)
    multiplier: float = DEFAULT_MULTIPLIER
    fever_strikes: int = DEFAULT_FEVER_STRIKES
    missed: int = 0
    assumed: bool = False             # odds are the stand-in curve, not the game's

    def quota_for(self, day: int) -> float:
        return self.need_today if day == self.day else self.quotas[day - self.day - 1]


def build_input(state: RunState, quota: float = 0.0, schedule: Sequence[float] = (),
                table: GradeOddsTable | None = None, multiplier: float = DEFAULT_MULTIPLIER,
                fever_strikes: int = DEFAULT_FEVER_STRIKES) -> SimInput | None:
    """Simulation input from the current state; None when the run is over (finished flag or
    already out of misses) or not started."""
    if state.finished or state.round <= 0 or state.missed_tributes >= MISSES_TO_LOSE:
        return None
    deadline = state.deadline_round if state.deadline_round >= state.round else DEFAULT_DEADLINE
    deadline = max(deadline, state.round)
    today_quota = quota if quota > 0 else curve_quota(state.round)
    future = tuple(float(schedule[i]) if i < len(schedule) and schedule[i] > 0
                   else curve_quota(d)
                   for i, d in enumerate(range(state.round + 1, deadline + 1)))
    assumed = table is None or not table.valid or not table.normal
    odds = assumed_odds() if assumed else table
    swords = tuple(SimSword(sw.grade, float(sw.value), sw.charge)
                   for sw in state.swords if sw.is_live)
    return SimInput(day=state.round, deadline=deadline, swords=swords,
                    need_today=max(today_quota - state.delivered, 0.0), quotas=future,
                    normal=dict(odds.normal), fever=dict(odds.fever),
                    multiplier=multiplier if multiplier > 1 else DEFAULT_MULTIPLIER,
                    fever_strikes=max(1, fever_strikes), missed=state.missed_tributes,
                    assumed=assumed)
