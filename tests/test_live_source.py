import json

from forgetax_overlay.live_source import LiveSource


def _run_message(payload: dict) -> dict:
    return {"type": "send", "payload": {"kind": "run", "json": json.dumps(payload)}}


def test_run_message_updates_latest_state():
    live = LiveSource(clock=lambda: 100.0)

    live.handle_message(_run_message({"campaign": {"round": 9, "wallet": 5}, "swords": []}))

    state, age = live.latest()
    assert state.round == 9 and state.wallet == 5
    assert age == 0.0


def test_latest_age_grows_with_clock():
    now = [100.0]
    live = LiveSource(clock=lambda: now[0])
    live.handle_message(_run_message({"campaign": {}, "swords": []}))

    now[0] = 104.5

    assert live.latest()[1] == 4.5


def test_broken_payload_keeps_previous_state():
    live = LiveSource(clock=lambda: 1.0)
    live.handle_message(_run_message({"campaign": {"round": 3}, "swords": []}))

    live.handle_message({"type": "send", "payload": {"kind": "run", "json": "{oops"}})

    assert live.latest()[0].round == 3


def test_error_messages_are_reported_in_status():
    live = LiveSource()

    live.handle_message({"type": "send", "payload": {"kind": "error", "message": "boom"}})
    assert "boom" in live.status
    live.handle_message({"type": "error", "description": "script crashed"})
    assert "script crashed" in live.status


def test_run_message_with_odds_exposes_sword_odds():
    live = LiveSource(clock=lambda: 1.0)
    message = _run_message({"campaign": {}, "swords": []})
    message["payload"]["odds"] = {"6": {"normal": [359, 42, 62, 496, 41],
                                        "fever": [0, 65, 97, 774, 64]}}
    message["payload"]["multiplier"] = 1.5

    live.handle_message(message)

    odds, multiplier = live.odds()
    normal, fever = odds[6]
    assert normal.destruction == 0.359 and fever.destruction == 0.0
    assert multiplier == 1.5


def test_texts_message_stores_relic_texts_and_writes_cache(tmp_path):
    cache = tmp_path / "relic_texts.json"
    live = LiveSource(texts_cache=cache)
    items = {"nail": {"name": "Đinh Cong", "description": "+4 phiếu Thành công."}}

    live.handle_message({"type": "send", "payload": {"kind": "texts", "lang": "vi", "items": items}})

    assert live.texts()["nail"].name == "Đinh Cong"
    assert json.loads(cache.read_text(encoding="utf-8")) == items


def test_run_message_with_shop_simulation():
    live = LiveSource(clock=lambda: 1.0)
    message = _run_message({"campaign": {}, "swords": []})
    message["payload"]["shopSim"] = {
        "buy": {"nail": {"11": [300, 42, 62, 550, 46]}, "bad": "x"},
        "drop": {"knot": {"11": [359, 42, 62, 496, 41]}},
        "swap": {"pin": {"knot": {"11": [250, 42, 62, 600, 46]}}},
    }

    live.handle_message(message)

    sim = live.shop_simulation()
    assert sim.buy["nail"][11].destruction == 0.3
    assert "bad" not in sim.buy
    assert sim.drop["knot"][11].success == 0.496
    assert sim.swap["pin"]["knot"][11].destruction == 0.25


def test_run_message_with_quota_and_grade_odds():
    live = LiveSource(clock=lambda: 1.0)
    message = _run_message({"campaign": {}, "swords": []})
    message["payload"]["quota"] = 2100.0
    message["payload"]["gradeOdds"] = {"valid": True,
                                       "normal": {"0": [0, 120, 200, 600, 80]},
                                       "fever": {"0": [0, 100, 200, 620, 80]}}

    live.handle_message(message)

    assert live.quota() == 2100.0
    table = live.grade_odds()
    assert table.valid and table.normal[0].success == 0.6 and table.fever[0].success == 0.62


def test_no_state_before_any_message():
    assert LiveSource().latest() == (None, None)
