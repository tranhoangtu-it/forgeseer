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

    assert "Ngày 7/24 (còn 17 ngày) · Vàng: 9.000" in text


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

    assert text.index("giá trị 9.000") < text.index("giá trị 500")
    assert "99.999" not in text and "88.888" not in text


def test_sword_line_shows_success_rate_and_heated_flag():
    text = _texts(format_state(_state(swords=(_sword(heated=True),))))

    assert "Tỉ lệ thành công: 75%" in text
    assert "đang nung" in text


def test_shop_section_only_while_shopping():
    assert "Cửa hàng di vật" not in _texts(format_state(_state(shopping=False)))
    assert "Cửa hàng di vật" in _texts(format_state(_state(shopping=True)))
    assert "hold" in _texts(format_state(_state(shopping=True)))


def test_relics_and_shop_use_readable_names():
    names = {"nail": "Đinh", "hold": "Giữ"}
    text = _texts(format_state(_state(shopping=True), names))

    assert "Đinh (bậc 2)" in text
    assert "Giữ · giá 1" in text


def test_sword_line_shows_peak_damage_and_fever():
    sword = _sword(value=800, peak=1200, damage_count=2, fever_remaining=3.0)
    text = _texts(format_state(_state(swords=(sword,))))

    assert "(từng đạt 1.200)" in text
    assert "Hư tổn: 2 lần" in text
    assert "ĐANG XUẤT THẦN" in text


def test_consumables_count_shown_when_present():
    assert "Vật phẩm tiêu hao: 2" in _texts(format_state(_state(consumables=2)))
    assert "tiêu hao" not in _texts(format_state(_state(consumables=0)))


def test_sword_odds_line_shows_verdict_and_uses_fever_odds():
    from forgetax_overlay.advisor import SwordOdds
    normal = SwordOdds.from_permille([359, 42, 62, 496, 41])
    fever = SwordOdds.from_permille([0, 65, 97, 774, 64])
    calm = _sword(serial=1, fever_remaining=0.0)
    hot = _sword(serial=2, fever_remaining=2.0)
    odds = {1: (normal, fever), 2: (normal, fever)}

    lines = format_state(_state(swords=(calm, hot)), odds=odds, multiplier=1.5)
    text = _texts(lines)

    assert "Gãy 36% · Hư tổn 4% · Không đổi 6% · Thành công 50% · Xuất sắc 4%" in text
    assert "→ DỪNG · kỳ vọng 1 nhát ×0,93" in text
    assert "ĐẬP (an toàn)" in text  # thanh đang fever dùng tỉ lệ fever
    assert any(tag == "warn" and "DỪNG" in t for t, tag in lines)


def test_shop_items_show_descriptions():
    text = _texts(format_state(_state(shopping=True), {"hold": "Kìm Giữ"},
                               descriptions={"hold": "Giữ nguyên 1 lần."}))

    assert "Kìm Giữ · giá 1" in text
    assert "Giữ nguyên 1 lần." in text


def test_shop_simulation_shows_effect_on_most_valuable_sword():
    from forgetax_overlay.advisor import SwordOdds
    now = SwordOdds.from_permille([359, 42, 62, 496, 41])
    better = SwordOdds.from_permille([250, 42, 62, 600, 46])
    sword = _sword(serial=11, value=500000)
    state = _state(shopping=True, swords=(sword,), offers=(Offer("nail", 2, False),))

    text = _texts(format_state(state, odds={11: (now, now)}, multiplier=1.5,
                               shop_sim=ShopSimulation(buy={"nail": {11: better}})))

    assert "Nếu mua, kiếm +5 dưới sàn: Gãy 36% → 25%" in text
    assert "kỳ vọng ×0,93 → " in text


def test_shop_simulation_reports_no_odds_change():
    from forgetax_overlay.advisor import SwordOdds
    now = SwordOdds.from_permille([359, 42, 62, 496, 41])
    sword = _sword(serial=11, value=500000)
    state = _state(shopping=True, swords=(sword,), offers=(Offer("coin", 2, False),))

    text = _texts(format_state(state, odds={11: (now, now)},
                               shop_sim=ShopSimulation(buy={"coin": {11: now}})))

    assert "Nếu mua, kiếm +5 dưới sàn: tỉ lệ không đổi" in text


def test_relic_section_shows_drop_advice():
    from forgetax_overlay.advisor import SwordOdds
    now = SwordOdds.from_permille([359, 42, 62, 496, 41])
    worse = SwordOdds.from_permille([450, 42, 62, 410, 36])
    sword = _sword(serial=11, value=500000)
    state = _state(swords=(sword,), relics=(Relic("nail", 1), Relic("knot", 1)))
    sim = ShopSimulation(drop={"nail": {11: worse}, "knot": {11: now}})

    text = _texts(format_state(state, {"knot": "Nút Thắt"}, odds={11: (now, now)}, shop_sim=sim))

    assert "Nút Thắt" in text
    assert "có thể bỏ" in text and "nên bỏ nhất" in text
    assert "Nếu bỏ: kỳ vọng ×0,93 → " in text


def test_none_state_shows_waiting_message():
    text = _texts(format_state(None))

    assert "Chưa có" in text


def test_tribute_line_shows_tomorrow_quota():
    text = _texts(format_state(_state(), quota=800, next_quota=4350))

    assert "Cống sắp tới: ngày 8: 4.350" in text


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

    assert "Di vật giảm Gãy (tỉ lệ Gãy ở cấp +8 / +12 / +16):" in text
    assert ("  ★ Đá Phong Ấn\n      Gãy +8: 5,0% → 4,0% · +12: 15,0% → 12,0% · "
            "+16: 25,0% → 20,0%") in text
    assert "Di vật có điều kiện (không mô phỏng được):" in text


def test_relic_rank_section_hidden_without_simulation():
    assert "Di vật giảm Gãy" not in _texts(format_state(_state()))


def test_tribute_area_shows_schedule_and_pace():
    lines = format_state(_state(swords=(_sword(value=3000),)), quota=2000,
                         schedule=(8700.0, 13200.0, 20100.0))
    text = _texts(lines)

    assert "Cống hôm nay: cần 2.000 · đã nộp 0 → ĐỦ nếu nộp" in text
    assert "Cống sắp tới: ngày 8: 8.700 · ngày 9: 13.200 · ngày 10: 20.100" in text
    assert "Chậm tiến độ: thiếu" in text
    assert "Ước tính sẽ có" in text
