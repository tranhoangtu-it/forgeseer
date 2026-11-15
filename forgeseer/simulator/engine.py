"""Monte Carlo of the rest of the run: play the remaining days many times with each strategy.

A simulated day: fresh +0 swords arrive (not on the current day, those are already in hand),
every sword is struck while the strategy says so (most valuable first, at most
``MAX_STEPS_PER_SWORD`` decisions a day, a Frenzy burst counts as one), then the tribute is paid
with the swords that cover it with the least overpay. Not enough value means a missed tribute;
the third one ends the run. Outcomes per strike: break (gone), damage -1 grade, hold, success +1,
great +2, value × multiplier per grade (the planner's model).

The working lists are mutable on purpose: this is the hot loop and runs ~millions of strikes.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from ..pace import FRESH_SWORD_VALUE, FRESH_SWORDS_PER_DAY
from ..planner import FEVER_THRESHOLD
from .model import MISSES_TO_LOSE, SimInput
from .strategies import DECIDERS, STRATEGY_KEYS, Context, Spot, build_context

DEFAULT_RUNS = 2000
DEFAULT_BUDGET_S = 0.9
MAX_STEPS_PER_SWORD = 30
CHECK_EVERY = 25  # runs between two looks at the clock


@dataclass(frozen=True)
class StrategyResult:
    key: str
    runs: int
    survival: tuple[float, ...]   # P(still in the run after day d), d = first_day .. deadline
    first_day: int
    win: float                    # P(survives the last day)
    expected_day: float           # mean of the day the run ends (deadline when won)


@dataclass(frozen=True)
class SimReport:
    results: tuple[StrategyResult, ...]
    seconds: float
    assumed: bool

    @property
    def best(self) -> StrategyResult | None:
        if not self.results:
            return None
        return max(self.results, key=lambda r: (round(r.win, 3), r.expected_day))


Cumulative = tuple[float, float, float, float]


def _cumulative(odds) -> Cumulative:
    a = odds.destruction
    b = a + odds.damage
    c = b + odds.hold
    return a, b, c, c + odds.success


def _roll(cum: Cumulative, grade: int, r: float) -> int:
    """New grade after one strike; -1 = broken."""
    if r < cum[0]:
        return -1
    if r < cum[1]:
        return max(grade - 1, 0)
    if r < cum[2]:
        return grade
    if r < cum[3]:
        return grade + 1
    return grade + 2


class _Runner:
    def __init__(self, inp: SimInput, ctx: Context) -> None:
        self.inp = inp
        self.ctx = ctx
        self.normal = {g: _cumulative(o) for g, o in inp.normal.items()}
        self.fever = {g: _cumulative(o) for g, o in inp.fever.items()}

    def _strike(self, sword: list, rng: random.Random) -> bool:
        """Strike once (or one Frenzy burst); False if the sword broke."""
        grade, value, charge = sword
        mult = self.inp.multiplier
        if charge >= FEVER_THRESHOLD:
            for _ in range(self.inp.fever_strikes):
                cum = self.fever.get(grade)
                if cum is None:
                    continue
                new = _roll(cum, grade, rng.random())
                if new < 0:
                    return False
                value *= mult ** (new - grade)
                grade = new
            sword[0], sword[1], sword[2] = grade, value, 0
            return True
        new = _roll(self.normal[grade], grade, rng.random())
        if new < 0:
            return False
        sword[0], sword[1], sword[2] = new, value * mult ** (new - grade), charge + 1
        return True

    def _forge(self, swords: list[list], need: float, decide, rng: random.Random) -> list[list]:
        swords.sort(key=lambda s: -s[1])
        holdings = sum(s[1] for s in swords)
        kept = []
        for i, sword in enumerate(swords):
            alive = True
            for _ in range(MAX_STEPS_PER_SWORD):
                spot = Spot(sword[0], sword[2], sword[1], need, holdings, i == 0)
                if not decide(self.ctx, spot):
                    break
                before = sword[1]
                if not self._strike(sword, rng):
                    holdings -= before
                    alive = False
                    break
                holdings += sword[1] - before
            if alive:
                kept.append(sword)
        return kept

    def run_once(self, decide, rng: random.Random) -> int | None:
        """Day the run ends on (third missed tribute), None when it survives the deadline."""
        inp = self.inp
        swords = [[s.grade, s.value, s.charge] for s in inp.swords]
        missed = inp.missed
        for day in range(inp.day, inp.deadline + 1):
            if day > inp.day:
                swords.extend([0, FRESH_SWORD_VALUE, 0] for _ in range(FRESH_SWORDS_PER_DAY))
            need = inp.quota_for(day)
            swords = self._forge(swords, need, decide, rng)
            if need <= 0:
                continue
            if sum(s[1] for s in swords) >= need:
                swords = _pay(swords, need)
            else:
                missed += 1
                if missed >= MISSES_TO_LOSE:
                    return day
        return None


def _pay(swords: list[list], need: float) -> list[list]:
    """Give the smallest sword that covers ``need`` alone, else the biggest ones until covered."""
    covering = [s for s in swords if s[1] >= need]
    if covering:
        pick = min(covering, key=lambda s: s[1])
        return [s for s in swords if s is not pick]
    rest = sorted(swords, key=lambda s: -s[1])
    total = 0.0
    while total < need and rest:
        total += rest.pop(0)[1]
    return rest


def _result(key: str, inp: SimInput, ends: Sequence[int | None]) -> StrategyResult:
    n = len(ends)
    days = range(inp.day, inp.deadline + 1)
    survival = tuple(sum(1 for e in ends if e is None or e > d) / n for d in days) if n else ()
    reached = [inp.deadline if e is None else e for e in ends]
    return StrategyResult(key=key, runs=n, survival=survival, first_day=inp.day,
                          win=survival[-1] if survival else 0.0,
                          expected_day=sum(reached) / n if n else 0.0)


def simulate(inp: SimInput, runs: int = DEFAULT_RUNS, seed: int | None = None,
             budget_s: float | None = DEFAULT_BUDGET_S, keys: Sequence[str] = STRATEGY_KEYS,
             clock: Callable[[], float] = time.perf_counter) -> SimReport:
    """Play ``runs`` runs per strategy (interleaved, so a time-out keeps them equal)."""
    start = clock()
    runner = _Runner(inp, build_context(inp))
    base = random.Random(seed).randrange(1 << 30) if seed is not None else random.randrange(1 << 30)
    rngs = {k: random.Random(base + i) for i, k in enumerate(keys)}
    ends: dict[str, list[int | None]] = {k: [] for k in keys}
    for n in range(runs):
        if budget_s is not None and n and n % CHECK_EVERY == 0 and clock() - start > budget_s:
            break
        for k in keys:
            ends[k].append(runner.run_once(DECIDERS[k], rngs[k]))
    results = tuple(_result(k, inp, ends[k]) for k in keys)
    return SimReport(results=results, seconds=clock() - start, assumed=inp.assumed)
