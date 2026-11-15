import dataclasses

from forgeseer.alerts import (
    FEVER, FEVER_REARM_SECONDS, STAR, TRIBUTE, AlertMemory, AlertSignals, alert_signals,
    detect_alerts, sound_enabled,
)
from forgeseer.relic_rank import parse_relic_rank
from forgeseer.save_reader import Offer

from tests.test_action_plan import _sword, _state

DAY = ("run", 7)


def run(signals_seq, start=0.0, step=0.3):
    memory, fired = AlertMemory(), []
    for i, signals in enumerate(signals_seq):
        memory, alerts = detect_alerts(memory, signals, start + i * step)
        fired.append(alerts)
    return memory, fired


def test_fever_fires_once_per_frenzy_even_across_a_missed_snapshot():
    on = AlertSignals(DAY, fever=frozenset({1}))
    off = AlertSignals(DAY)

    _, fired = run([off, on, on, off, on, on])

    assert fired == [(), (FEVER,), (), (), (), ()]


def test_fever_fires_again_after_the_rearm_delay():
    memory, first = detect_alerts(AlertMemory(), AlertSignals(DAY, fever=frozenset({1})), 0.0)
    memory, _ = detect_alerts(memory, AlertSignals(DAY), 1.0)
    memory, again = detect_alerts(memory, AlertSignals(DAY, fever=frozenset({1})),
                                  1.0 + FEVER_REARM_SECONDS + 0.5)

    assert first == (FEVER,) and again == (FEVER,)


def test_another_sword_entering_frenzy_fires():
    _, fired = run([AlertSignals(DAY, fever=frozenset({1})),
                    AlertSignals(DAY, fever=frozenset({1, 2}))])

    assert fired == [(FEVER,), (FEVER,)]


def test_tribute_shortfall_warns_once_per_day():
    short = AlertSignals(DAY, tribute_short=True)
    tomorrow = AlertSignals(("run", 8), tribute_short=True)

    _, fired = run([short, short, AlertSignals(DAY), short, tomorrow, tomorrow])

    assert fired == [(TRIBUTE,), (), (), (), (TRIBUTE,), ()]


def test_star_relic_highlights_once_per_item_and_day():
    one = AlertSignals(DAY, starred=frozenset({"nail"}))
    two = AlertSignals(DAY, starred=frozenset({"nail", "seal"}))

    _, fired = run([one, one, two, AlertSignals(("run", 8), starred=frozenset({"nail"}))])

    assert fired == [(STAR,), (), (STAR,), (STAR,)]


def test_alerts_can_fire_together():
    signals = AlertSignals(DAY, fever=frozenset({3}), tribute_short=True, starred=frozenset({"x"}))

    _, alerts = detect_alerts(AlertMemory(), signals, 0.0)

    assert alerts == (FEVER, TRIBUTE, STAR)


def test_signals_from_state():
    swords = (_sword(1, 900, 5, fever=2.0), _sword(2, 500, 3))
    state = dataclasses.replace(_state(swords, shopping=True,
                                       offers=(Offer("nail", 4, False), Offer("seal", 4, True))),
                                run_id="abc", round=4)
    rank = parse_relic_rank({"baseline": {"12": [100, 0, 0, 900, 0]},
                             "items": {"nail": {"12": [50, 0, 0, 950, 0]},
                                       "seal": {"12": [40, 0, 0, 960, 0]}}})

    signals = alert_signals(state, 5000.0, rank)

    assert signals.day == ("abc", 4)
    assert signals.fever == {1}
    assert signals.tribute_short  # 1.400 G kiếm, cần 5.000 G
    assert signals.starred == {"nail"}  # seal giảm gãy hơn nhưng đã bán
    assert not alert_signals(state, 1000.0, None).tribute_short


def test_sound_setting_defaults_on():
    assert sound_enabled({})
    assert sound_enabled({"settings": {"opacity": 80}})
    assert sound_enabled({"settings": {"sound_alerts": "no"}})  # sai kiểu -> mặc định
    assert sound_enabled([])
    assert not sound_enabled({"settings": {"sound_alerts": False}})
