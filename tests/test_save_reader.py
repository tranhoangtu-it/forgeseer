import json
import os
import time

import pytest

from forgeseer.save_reader import (
    SaveReadError,
    find_run_save,
    parse_run_save,
)


def _wrap(payload: dict) -> str:
    """Bọc payload theo đúng định dạng file save: payload là chuỗi JSON lồng bên trong."""
    return json.dumps({"version": 1, "payload": json.dumps(payload), "checksum": "x"})


def _sample_payload() -> dict:
    return {
        "active": True,
        "campaign": {
            "Record": {"seconds": 870.5, "goldEarned": 23450, "highestGrade": 10},
            "round": 7,
            "contractDeadlineRound": 24,
            "wallet": 9178,
            "pendingTribute": 500,
            "successfulTributes": 6,
            "missedTributes": 1,
            "wardCharges": 1,
            "swordCredits": 2,
            "rerolls": 0,
            "rewindCharges": 0,
            "shopping": True,
            "finished": False,
            "won": False,
            "brokenSwords": 7,
            "greatEvents": 11,
            "holdEvents": 10,
            "damageEvents": 7,
            "feverEvents": 1,
            "consumables": [{"id": "oil"}],
            "relics": [{"id": "nail", "rank": 1}, {"id": "", "rank": 0}],
            "offers": [
                {"id": "hold", "price": 1, "sold": False},
                {"id": "", "price": 0, "sold": False},
            ],
        },
        "swords": [
            {
                "serial": 1, "grade": 10, "value": 20503, "strikes": 16,
                "heated": False, "broken": False, "active": True, "rack": 2,
                "feverRemaining": 2.5,
                "effects": {"successStreak": 3, "normalHits": 10,
                            "normalSuccesses": 5, "peak": 20503, "damageCount": 2},
            },
            {"serial": 2, "grade": 0, "value": 0, "active": False, "effects": {}},
        ],
    }


def test_parse_run_save_reads_campaign_fields():
    state = parse_run_save(_wrap(_sample_payload()))

    assert state.round == 7
    assert state.deadline_round == 24
    assert state.wallet == 9178
    assert state.pending_tribute == 500
    assert state.gold_earned == 23450
    assert state.highest_grade == 10
    assert state.shopping is True


def test_parse_run_save_drops_empty_relic_and_offer_slots():
    state = parse_run_save(_wrap(_sample_payload()))

    assert [(r.id, r.rank) for r in state.relics] == [("nail", 1)]
    assert [(o.id, o.price) for o in state.offers] == [("hold", 1)]


def test_parse_run_save_reads_sword_effects():
    state = parse_run_save(_wrap(_sample_payload()))

    sword = state.swords[0]
    assert sword.value == 20503
    assert sword.success_streak == 3
    assert sword.success_rate == pytest.approx(0.5)
    assert sword.damage_count == 2
    assert sword.fever_remaining == pytest.approx(2.5)
    assert state.consumables == 1
    assert state.swords[1].success_rate is None  # chưa đập nhát nào


def test_parse_run_save_tolerates_missing_fields():
    state = parse_run_save(_wrap({"campaign": {}, "swords": []}))

    assert state.round == 0
    assert state.swords == ()


@pytest.mark.parametrize("text", ["", "{not json", json.dumps({"version": 1})])
def test_parse_run_save_rejects_invalid_content(text):
    with pytest.raises(SaveReadError):
        parse_run_save(text)


def test_find_run_save_picks_newest_and_ignores_previous(tmp_path):
    old = tmp_path / "run_release23_v1_1.json"
    new = tmp_path / "run_release24_v1_1.json"
    backup = tmp_path / "run_release24_v1_1.json.previous"
    for f in (old, new, backup):
        f.write_text("{}")
    now = time.time()
    os.utime(old, (now - 100, now - 100))
    os.utime(new, (now - 10, now - 10))
    os.utime(backup, (now, now))

    assert find_run_save(tmp_path) == new


def test_find_run_save_returns_none_when_missing(tmp_path):
    assert find_run_save(tmp_path / "nope") is None


def test_sword_tag_uses_visible_grade_and_location():
    from forgeseer.save_reader import PLACE_RACK, Sword
    base = dict(serial=3, grade=8, value=11250, peak=11250, strikes=17, success_streak=0,
                normal_hits=10, normal_successes=3, heated=False, broken=False, active=True,
                rack=1, damage_count=1, fever_remaining=0.0)

    assert Sword(**base, place=PLACE_RACK).tag == "+8 giá ô 2"
    assert Sword(**base, place=0).tag == "+8 dưới sàn"
    assert Sword(**base, place=3).tag == "+8 trên đe"
    assert Sword(**base, place=2).tag == "+8 đang cầm"
    assert not Sword(**base, place=5).is_live  # đã đặt lên bàn cống nạp


def test_run_id_read_from_campaign():
    import json as _json
    from forgeseer.save_reader import parse_run_save as _parse
    text = _json.dumps({"version": 1, "checksum": "",
                        "payload": _json.dumps({"campaign": {"anonymousRunId": "r1"}})})

    assert _parse(text).run_id == "r1"


def test_display_sort_key_puts_anvil_sword_first_then_by_value():
    from forgeseer.save_reader import PLACE_ANVIL, PLACE_RACK, Sword, display_sort_key
    base = dict(grade=5, strikes=1, success_streak=0, normal_hits=1, normal_successes=1,
                heated=False, broken=False, active=True, rack=0, damage_count=0,
                fever_remaining=0.0)
    big = Sword(serial=1, value=90000, peak=90000, place=PLACE_RACK, **base)
    small_on_anvil = Sword(serial=2, value=320, peak=320, place=PLACE_ANVIL, **base)
    mid = Sword(serial=3, value=5000, peak=5000, place=PLACE_RACK, **base)

    ordered = sorted([big, small_on_anvil, mid], key=display_sort_key)

    assert [s.serial for s in ordered] == [2, 1, 3]
