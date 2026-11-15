from forgetax_overlay.advisor import ShopSimulation
from forgetax_overlay.formatter import format_state
from forgetax_overlay.relic_rank import parse_relic_rank
from forgetax_overlay.save_reader import Offer, Relic, RunState, Sword


def _sword(**overrides) -> Sword:
    base = dict(serial=1, grade=5, value=1000, peak=1000, strikes=4,
                success_streak=1, normal_hits=4, normal_successes=3,
                heated=False, broken=False, active=True, rack=0,
                damage_count=0, fever_remaining=0.0)
    return Sword(**{**base, **overrides})


def _state(**overrides) -> RunState:
    base = dict(
        active=True, round=7, deadline_round=24, wallet=9000, pending_tribute=0,
        successful_tributes=6, missed_tributes=0, ward_charges=1, sword_credits=1,
        rerolls=0, rewind_charges=0, shopping=False, finished=False, won=False,
        broken_swords=2, great_events=3, hold_events=4, damage_events=1,
        fever_events=0, gold_earned=20000, highest_grade=10, play_seconds=125.0,
        relics=(Relic("nail", 2),), offers=(Offer("hold", 1, False),),
        swords=(_sword(),), consumables=0,
    )
    return RunState(**{**base, **overrides})


def _texts(lines):
    return "\n".join(text for text, _ in lines)


def test_shows_round_progress_and_wallet():
    text = _texts(format_state(_state()))

    assert "Vòng 7/24" in text
    assert "còn 17" in text
    assert "9,000" in text


def test_warns_when_tribute_exceeds_wallet():
    lines = format_state(_state(wallet=100, pending_tribute=500))

    assert any(tag == "warn" and "Thiếu" in text for text, tag in lines)


def test_lists_only_live_swords_sorted_by_value():
    swords = (
        _sword(serial=1, value=500),
        _sword(serial=2, value=9000),
        _sword(serial=3, value=99999, broken=True),
        _sword(serial=4, value=88888, active=False),
    )
    text = _texts(format_state(_state(swords=swords)))

    assert text.index("9,000") < text.index("   500")
    assert "99,999" not in text and "88,888" not in text


def test_sword_line_shows_success_rate_and_heated_flag():
    text = _texts(format_state(_state(swords=(_sword(heated=True),))))

    assert "75%" in text
    assert "NUNG" in text


def test_shop_section_only_while_shopping():
    assert "Shop" not in _texts(format_state(_state(shopping=False)))
    assert "hold" in _texts(format_state(_state(shopping=True)))


def test_relics_and_shop_use_readable_names():
    names = {"nail": "Đinh", "hold": "Giữ"}
    text = _texts(format_state(_state(shopping=True), names))

    assert "Đinh r2" in text
    assert "Giữ - 1" in text


def test_sword_line_shows_peak_damage_and_fever():
    sword = _sword(value=800, peak=1200, damage_count=2, fever_remaining=3.0)
    text = _texts(format_state(_state(swords=(sword,))))

    assert "đỉnh 1,200" in text
    assert "hỏng 2" in text
    assert "FEVER" in text


def test_consumables_count_shown_when_present():
    assert "Tiêu hao 2" in _texts(format_state(_state(consumables=2)))
    assert "Tiêu hao" not in _texts(format_state(_state(consumables=0)))


def test_sword_odds_line_shows_verdict_and_uses_fever_odds():
    from forgetax_overlay.advisor import SwordOdds
    normal = SwordOdds.from_permille([359, 42, 62, 496, 41])
    fever = SwordOdds.from_permille([0, 65, 97, 774, 64])
    calm = _sword(serial=1, fever_remaining=0.0)
    hot = _sword(serial=2, fever_remaining=2.0)
    odds = {1: (normal, fever), 2: (normal, fever)}

    lines = format_state(_state(swords=(calm, hot)), odds=odds, multiplier=1.5)
    text = _texts(lines)

    assert "gãy 36%" in text and "DỪNG" in text
    assert "ĐẬP (an toàn)" in text  # thanh đang fever dùng tỉ lệ fever
    assert any(tag == "warn" and "DỪNG" in t for t, tag in lines)


def test_shop_items_show_descriptions():
    text = _texts(format_state(_state(shopping=True), {"hold": "Kìm Giữ"},
                               descriptions={"hold": "Giữ nguyên 1 lần."}))

    assert "Kìm Giữ - 1" in text
    assert "Giữ nguyên 1 lần." in text


def test_shop_simulation_shows_effect_on_most_valuable_sword():
    from forgetax_overlay.advisor import SwordOdds
    now = SwordOdds.from_permille([359, 42, 62, 496, 41])
    better = SwordOdds.from_permille([250, 42, 62, 600, 46])
    sword = _sword(serial=11, value=500000)
    state = _state(shopping=True, swords=(sword,), offers=(Offer("nail", 2, False),))

    text = _texts(format_state(state, odds={11: (now, now)}, multiplier=1.5,
                               shop_sim=ShopSimulation(buy={"nail": {11: better}})))

    assert "+5 dưới sàn: gãy 36%->25%" in text
    assert "EV x0.93->" in text


def test_shop_simulation_reports_no_odds_change():
    from forgetax_overlay.advisor import SwordOdds
    now = SwordOdds.from_permille([359, 42, 62, 496, 41])
    sword = _sword(serial=11, value=500000)
    state = _state(shopping=True, swords=(sword,), offers=(Offer("coin", 2, False),))

    text = _texts(format_state(state, odds={11: (now, now)},
                               shop_sim=ShopSimulation(buy={"coin": {11: now}})))

    assert "không đổi tỉ lệ" in text


def test_relic_section_shows_drop_advice():
    from forgetax_overlay.advisor import SwordOdds
    now = SwordOdds.from_permille([359, 42, 62, 496, 41])
    worse = SwordOdds.from_permille([450, 42, 62, 410, 36])
    sword = _sword(serial=11, value=500000)
    state = _state(swords=(sword,), relics=(Relic("nail", 1), Relic("knot", 1)))
    sim = ShopSimulation(drop={"nail": {11: worse}, "knot": {11: now}})

    text = _texts(format_state(state, {"knot": "Nút Thắt"}, odds={11: (now, now)}, shop_sim=sim))

    assert "Nút Thắt" in text
    assert "có thể bỏ" in text and "nên bỏ" in text
    assert "bỏ: EV x0.93->" in text


def test_none_state_shows_waiting_message():
    text = _texts(format_state(None))

    assert "Chưa có" in text


def test_tribute_line_shows_tomorrow_quota():
    text = _texts(format_state(_state(), quota=800, next_quota=4350))

    assert "ngày mai 4,350" in text


def test_run_summary_appended_when_given():
    text = _texts(format_state(_state(), runs_summary="Lượt chơi: 2"))

    assert "Lượt chơi: 2" in text


def test_relic_rank_section_stars_unsold_shop_offer():
    rank = parse_relic_rank({"baseline": {"8": [50, 0, 0, 0, 0], "12": [150, 0, 0, 0, 0],
                                          "16": [250, 0, 0, 0, 0]},
                             "items": {"hold": {"8": [40, 0, 0, 0, 0], "12": [120, 0, 0, 0, 0],
                                                "16": [200, 0, 0, 0, 0]}}})
    text = _texts(format_state(_state(shopping=True), names={"hold": "Đá Phong Ấn"},
                               relic_rank=rank))

    assert "Relic giảm gãy (@+8/+12/+16, chỉ hiệu ứng cố định):" in text
    assert "★ Đá Phong Ấn: gãy 5.0%->4.0% | 15.0%->12.0% | 25.0%->20.0%" in text
    assert "Có điều kiện (không mô phỏng được):" in text


def test_relic_rank_section_hidden_without_simulation():
    assert "Relic giảm gãy" not in _texts(format_state(_state()))


def test_tribute_area_shows_schedule_and_pace():
    lines = format_state(_state(swords=(_sword(value=3000),)), quota=2000,
                         schedule=(8700.0, 13200.0, 20100.0))
    text = _texts(lines)

    assert "ngày mai 8,700" in text
    assert "Cống sắp tới: d8 8.7k, d9 13.2k, d10 20.1k" in text
    assert "Chậm: thiếu" in text
