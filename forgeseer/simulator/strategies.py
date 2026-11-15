"""Ways of playing compared by the simulation, each one a pure "strike this sword again?" rule.

- ``advisor``: what the overlay says. The multi-strike plan (planner), with the tribute rules on
  top: never risk a sword that today's tribute depends on, push a sword when one strike can make
  up today's shortfall.
- ``conservative``: the same, but never takes a normal strike with a 10 %+ break chance.
- ``aggressive``: the most valuable sword keeps going while one strike is worth it on average,
  even when the tribute rests on it; the other swords follow the overlay.
- ``safe_only``: only strikes that can't break, and Frenzy bursts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..advisor import SwordOdds, advise
from ..pace import RISKY_DESTRUCTION
from ..planner import EPSILON, FEVER_THRESHOLD, HORIZON, _model
from .model import SimInput

ADVISOR, CONSERVATIVE, AGGRESSIVE, SAFE_ONLY = "advisor", "conservative", "aggressive", "safe_only"
STRATEGY_KEYS = (ADVISOR, CONSERVATIVE, AGGRESSIVE, SAFE_ONLY)

DecisionTable = dict[tuple[int, int], bool]


@dataclass(frozen=True)
class Context:
    normal: dict[int, SwordOdds]
    multiplier: float
    plan: DecisionTable   # optimal plan says strike at (grade, charge)
    safe: DecisionTable   # safe-only plan says strike at (grade, charge)


@dataclass(frozen=True)
class Spot:
    """One sword at one moment of the day."""
    grade: int
    charge: int
    value: float
    need: float       # tribute still missing today (0 once paid)
    holdings: float   # value of every sword on hand, this one included
    is_top: bool      # the most valuable sword on hand


Decide = Callable[[Context, Spot], bool]


def decision_table(inp: SimInput, safe_only: bool) -> DecisionTable:
    """Plan decision for every (grade, charge) of the odds table. One DP for all grades: the
    plan's choice doesn't depend on the scale of values, so relative to +0 is enough."""
    if not inp.normal:
        return {}
    best, strike = _model(0, inp.normal, inp.fever, inp.multiplier, inp.fever_strikes, safe_only)
    table: DecisionTable = {}
    for g in inp.normal:
        stop = inp.multiplier ** g
        for c in range(FEVER_THRESHOLD + 1):
            go = strike(g, c, HORIZON) > stop * (1.0 + EPSILON)
            if safe_only and c < FEVER_THRESHOLD and inp.normal[g].destruction > 0:
                go = False
            table[(g, c)] = go
    return table


def build_context(inp: SimInput) -> Context:
    return Context(normal=inp.normal, multiplier=inp.multiplier,
                   plan=decision_table(inp, False), safe=decision_table(inp, True))


def _can_break(ctx: Context, spot: Spot) -> bool:
    odds = ctx.normal.get(spot.grade)
    return spot.charge < FEVER_THRESHOLD and odds is not None and odds.destruction > 0


def tribute_locked(ctx: Context, spot: Spot) -> bool:
    """Today's tribute is covered only with this sword, and a strike could break it."""
    others = spot.holdings - spot.value
    return spot.need > 0 and others < spot.need <= spot.holdings and _can_break(ctx, spot)


def tribute_push(ctx: Context, spot: Spot) -> bool:
    """Today's tribute is short and one good strike on this sword would cover it."""
    if spot.need <= 0 or spot.holdings >= spot.need or spot.grade not in ctx.normal:
        return False
    others = spot.holdings - spot.value
    return others + spot.value * ctx.multiplier ** 2 >= spot.need


def advisor(ctx: Context, spot: Spot) -> bool:
    if spot.grade not in ctx.normal or tribute_locked(ctx, spot):
        return False
    return tribute_push(ctx, spot) or ctx.plan.get((spot.grade, spot.charge), False)


def conservative(ctx: Context, spot: Spot) -> bool:
    odds = ctx.normal.get(spot.grade)
    if odds is None or tribute_locked(ctx, spot):
        return False
    risky = spot.charge < FEVER_THRESHOLD and odds.destruction >= RISKY_DESTRUCTION
    if risky:
        return False
    return tribute_push(ctx, spot) or ctx.plan.get((spot.grade, spot.charge), False)


def aggressive(ctx: Context, spot: Spot) -> bool:
    odds = ctx.normal.get(spot.grade)
    if odds is None:
        return False
    if spot.is_top:
        return (spot.charge >= FEVER_THRESHOLD or advise(odds, ctx.multiplier).strike
                or ctx.plan.get((spot.grade, spot.charge), False))
    return advisor(ctx, spot)


def safe_only(ctx: Context, spot: Spot) -> bool:
    if spot.grade not in ctx.normal or tribute_locked(ctx, spot):
        return False
    return ctx.safe.get((spot.grade, spot.charge), False)


DECIDERS: dict[str, Decide] = {ADVISOR: advisor, CONSERVATIVE: conservative,
                               AGGRESSIVE: aggressive, SAFE_ONLY: safe_only}
