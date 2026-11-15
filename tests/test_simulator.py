import itertools

import pytest

from forgeseer.advisor import GradeOddsTable, SwordOdds
from forgeseer.save_reader import PLACE_TRIBUTE, RunState, Sword
from forgeseer.simulator import STRATEGY_KEYS, SimInput, SimSword, build_input, curve_quota, simulate
from forgeseer.simulator.engine import _pay, _roll
from forgeseer.simulator.model import QUOTA_CURVE, assumed_odds
from forgeseer.simulator.strategies import (Context, Spot, advisor, aggressive, build_context,
                                            conservative, safe_only, tribute_locked, tribute_push)

SAFE = SwordOdds(0.0, 0.0, 0.2, 0.7, 0.1)
RISKY = SwordOdds(0.3, 0.1, 0.1, 0.4, 0.1)
MILD = SwordOdds(0.05, 0.05, 0.2, 0.6, 0.1)
FEVER = SwordOdds(0.0, 0.0, 0.2, 0.7, 0.1)


def _inp(day=20, swords=(SimSword(0, 320.0),) * 3, need=None, table=None, missed=0) -> SimInput:
    table = table or assumed_odds()
    return SimInput(day=day, deadline=24, swords=tuple(swords),
                    need_today=curve_quota(day) if need is None else need,
                    quotas=tuple(curve_quota(d) for d in range(day + 1, 25)),
                    normal=table.normal, fever=table.fever, missed=missed)


def _ctx(plan=True, safe=True) -> Context:
    normal = {0: SAFE, 5: MILD, 9: RISKY}
    keys = [(g, c) for g in normal for c in range(11)]
    return Context(normal=normal, multiplier=1.5, plan={k: plan for k in keys},
                   safe={k: safe for k in keys})


def _spot(grade=9, charge=0, value=1000.0, need=0.0, holdings=1000.0, top=False) -> Spot:
    return Spot(grade, charge, value, need, holdings, top)


# ---------- model ----------
def test_curve_quota_uses_measured_days_and_fills_gaps():
    assert curve_quota(7) == 8700
    assert curve_quota(24) == 2_000_000
    assert QUOTA_CURVE[18] < curve_quota(19) < QUOTA_CURVE[20]
    assert curve_quota(19) == pytest.approx((534000 * 824000) ** 0.5)
    assert curve_quota(25) > curve_quota(24)


def _sword(serial, grade, value, place=0, charge=0) -> Sword:
    return Sword(serial, grade, value, value, 0, 0, 0, 0, False, False, True, -1, 0, 0.0,
                 charge=charge, place=place)


def _state(**overrides) -> RunState:
    base = dict(
        active=True, round=10, deadline_round=24, wallet=0, pending_tribute=0,
        successful_tributes=9, missed_tributes=1, ward_charges=0, sword_credits=0, rerolls=0,
        rewind_charges=0, shopping=False, finished=False, won=False, broken_swords=0,
        great_events=0, hold_events=0, damage_events=0, fever_events=0, gold_earned=0,
        highest_grade=8, play_seconds=0.0, relics=(), offers=(),
        swords=(_sword(1, 8, 8200, charge=4), _sword(2, 3, 1080),
                _sword(3, 2, 720, place=PLACE_TRIBUTE)),
        consumables=0, delivered=5000,
    )
    return RunState(**{**base, **overrides})


def test_build_input_uses_live_numbers_then_curve():
    table = GradeOddsTable(normal={0: SAFE}, fever={0: FEVER}, valid=True)
    inp = build_input(_state(), quota=29500, schedule=(40000, 60000), table=table,
                      multiplier=1.5, fever_strikes=6)

    assert inp.day == 10 and inp.deadline == 24 and inp.missed == 1
    assert inp.need_today == 24500
    assert inp.quotas[:3] == (40000, 60000, curve_quota(13))
    assert len(inp.quotas) == 14
    assert inp.swords == (SimSword(8, 8200.0, 4), SimSword(3, 1080.0, 0))
    assert not inp.assumed and inp.fever_strikes == 6


def test_build_input_without_odds_table_flags_assumed_odds():
    inp = build_input(_state(), quota=0)

    assert inp.assumed and inp.normal
    assert inp.need_today == curve_quota(10) - 5000


def test_build_input_none_for_finished_run():
    assert build_input(_state(finished=True)) is None
    assert build_input(_state(missed_tributes=3)) is None  # out of misses, game over


# ---------- decisions ----------
def test_tribute_lock_and_push():
    ctx = _ctx()
    assert tribute_locked(ctx, _spot(need=900, holdings=1200))       # only this sword covers it
    assert not tribute_locked(ctx, _spot(grade=0, need=900, holdings=1200))  # can't break
    assert not tribute_locked(ctx, _spot(need=900, holdings=5000))   # others cover it
    assert tribute_push(ctx, _spot(need=2000, holdings=1000))        # ×2.25 would cover
    assert not tribute_push(ctx, _spot(need=9000, holdings=1000))    # out of reach


def test_advisor_follows_plan_unless_tribute_says_otherwise():
    assert advisor(_ctx(plan=True), _spot())
    assert not advisor(_ctx(plan=False), _spot())
    assert not advisor(_ctx(plan=True), _spot(need=900, holdings=1200))
    assert advisor(_ctx(plan=False), _spot(need=2000, holdings=1000))
    assert not advisor(_ctx(plan=True), _spot(grade=30))  # outside the odds table


def test_conservative_refuses_risky_normal_strikes():
    assert not conservative(_ctx(), _spot(grade=9))
    assert conservative(_ctx(), _spot(grade=9, charge=10))  # Frenzy burst can't break
    assert conservative(_ctx(), _spot(grade=5))


def test_aggressive_pushes_top_sword_even_when_tribute_rests_on_it():
    locked = dict(need=900, holdings=1200)
    assert aggressive(_ctx(plan=False), _spot(grade=5, top=True, **locked))
    assert not aggressive(_ctx(plan=True), _spot(grade=5, top=False, **locked))


def test_safe_only_uses_safe_plan():
    assert safe_only(_ctx(safe=True), _spot(grade=0))
    assert not safe_only(_ctx(safe=False), _spot(grade=0))


def test_safe_decision_table_never_strikes_into_break_chance():
    inp = _inp()
    ctx = build_context(inp)
    for (g, c), go in ctx.safe.items():
        if go and c < 10:
            assert inp.normal[g].destruction == 0, (g, c)


# ---------- engine ----------
def test_roll_maps_random_number_to_outcome():
    cum = (0.1, 0.2, 0.3, 0.8)
    assert [_roll(cum, 5, r) for r in (0.05, 0.15, 0.25, 0.5, 0.9)] == [-1, 4, 5, 6, 7]
    assert _roll(cum, 0, 0.15) == 0


def test_pay_prefers_smallest_covering_sword():
    a, b, c = [0, 500.0, 0], [0, 3000.0, 0], [0, 9000.0, 0]
    assert _pay([a, b, c], 2500) == [a, c]
    assert _pay([a, b], 3200) == []


def test_simulation_is_deterministic_with_a_seed():
    first = simulate(_inp(), runs=60, seed=7, budget_s=None)
    second = simulate(_inp(), runs=60, seed=7, budget_s=None)

    assert [r.survival for r in first.results] == [r.survival for r in second.results]
    assert {r.key for r in first.results} == set(STRATEGY_KEYS)
    assert all(r.runs == 60 for r in first.results)


def test_survival_curves_never_go_up():
    report = simulate(_inp(day=14), runs=80, seed=3, budget_s=None)
    for r in report.results:
        assert len(r.survival) == 24 - 14 + 1
        assert all(a >= b for a, b in itertools.pairwise(r.survival)), r.key
        assert r.win == r.survival[-1]
        assert 14 <= r.expected_day <= 24


def test_hopeless_run_dies_after_the_remaining_misses():
    inp = _inp(day=22, swords=(), need=10**9, missed=2)
    report = simulate(inp, runs=10, seed=1, budget_s=None)

    for r in report.results:
        assert r.survival[0] == 0.0 and r.expected_day == 22


def test_easy_run_is_won_by_every_strategy():
    table = GradeOddsTable(normal={g: SAFE for g in range(60)}, fever={g: FEVER for g in range(60)},
                           valid=True)
    inp = _inp(day=23, swords=(SimSword(40, 320 * 1.5 ** 40),) * 3, table=table)
    report = simulate(inp, runs=20, seed=1, budget_s=None)

    assert all(r.win == 1.0 for r in report.results)
    assert report.best is not None


def test_time_budget_stops_early_with_equal_counts():
    ticks = itertools.count()
    report = simulate(_inp(), runs=10_000, seed=1, budget_s=5, clock=lambda: next(ticks))

    counts = {r.runs for r in report.results}
    assert len(counts) == 1 and counts.pop() < 10_000
