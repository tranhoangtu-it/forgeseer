from forgetax_overlay.action_plan import build_steps, choose_tribute
from forgetax_overlay.advisor import ShopSimulation, SwordOdds
from forgetax_overlay.merchant_advice import MerchantItem
from forgetax_overlay.relic_rank import parse_relic_rank
from forgetax_overlay.save_reader import MerchantOffer, Offer, RunState, Sword

RISKY = SwordOdds.from_permille([350, 30, 240, 330, 50])
SAFE = SwordOdds.from_permille([0, 50, 150, 700, 100])


def _sword(serial, value, grade, fever=0.0) -> Sword:
    return Sword(serial=serial, grade=grade, value=value, peak=value, strikes=5, success_streak=0,
                 normal_hits=5, normal_successes=3, heated=False, broken=False, active=True,
                 rack=0, damage_count=0, fever_remaining=fever)


def _state(swords, ward=0, shopping=False, offers=(), delivered=0) -> RunState:
    return RunState(
        active=True, round=5, deadline_round=24, wallet=5000, pending_tribute=0,
        successful_tributes=0, missed_tributes=0, ward_charges=ward, sword_credits=0, rerolls=0,
        rewind_charges=0, shopping=shopping, finished=False, won=False, broken_swords=0,
        great_events=0, hold_events=0, damage_events=0, fever_events=0, gold_earned=0,
        highest_grade=0, play_seconds=0.0, relics=(), offers=tuple(offers),
        swords=tuple(swords), consumables=0, delivered=delivered)


def _text(lines):
    return "\n".join(t for t, _ in lines)


def test_fever_sword_is_first_step():
    swords = (_sword(1, 5000, 8), _sword(2, 900, 3, fever=2.0))
    lines = build_steps(_state(swords), {1: (RISKY, SAFE), 2: (RISKY, SAFE)}, 1.5)

    assert "XUẤT THẦN +3 dưới sàn" in lines[1][0]


def test_fever_step_is_alert_and_shows_calibrated_strikes():
    swords = (_sword(2, 900, 3, fever=2.0),)
    lines = build_steps(_state(swords), {2: (RISKY, SAFE)}, 1.5, fever_strikes=9)

    text, tag = lines[1]
    assert tag == "alert"
    assert "~9 nhát" in text


def test_tribute_step_prefers_finished_swords_and_reaches_need():
    swords = (_sword(1, 5000, 10), _sword(2, 320, 0), _sword(3, 320, 0))
    odds = {1: (RISKY, SAFE), 2: (SAFE, SAFE), 3: (SAFE, SAFE)}

    text = _text(build_steps(_state(swords), odds, 1.5, quota=3000))

    assert "nộp cống: +10 dưới sàn" in text


def test_swords_reserved_for_tribute_are_not_struck_when_risky():
    good_but_risky = SwordOdds.from_permille([100, 20, 80, 700, 100])
    swords = (_sword(1, 3000, 6), _sword(2, 2000, 5))
    odds = {1: (good_but_risky, SAFE), 2: (good_but_risky, SAFE)}

    text = _text(build_steps(_state(swords), odds, 1.5, quota=4500))

    assert "nộp cống: +5 dưới sàn, +6 dưới sàn" in text
    assert "Đập +5" not in text and "Đập +6" not in text


def test_tribute_shortfall_tells_to_raise_value():
    swords = (_sword(2, 320, 0),)
    text = _text(build_steps(_state(swords), {2: (SAFE, SAFE)}, 1.5, quota=3000))

    assert "Thiếu" in text


def test_risky_top_sword_strike_suggests_ward_when_available():
    swords = (_sword(1, 5000, 8),)
    risky_but_good = SwordOdds.from_permille([100, 20, 80, 700, 100])

    text = _text(build_steps(_state(swords, ward=1), {1: (risky_but_good, SAFE)}, 1.5))

    assert "Đập +8 dưới sàn" in text and "Q" in text


def test_identical_safe_swords_grouped_in_one_step():
    swords = tuple(_sword(i, 320, 0) for i in range(1, 5))
    odds = {i: (SAFE, SAFE) for i in range(1, 5)}

    text = _text(build_steps(_state(swords), odds, 1.5))

    assert "Đập x4 kiếm +0 dưới sàn" in text


def test_shop_and_merchant_purchases_are_listed():
    sword = _sword(1, 5000, 8)
    better = SwordOdds.from_permille([50, 20, 80, 750, 100])
    state = _state((sword,), shopping=True, offers=(Offer("pin", 1, False),))
    sim = ShopSimulation(buy={"pin": {1: better}})
    item = MerchantItem(MerchantOffer("ward", 1100, False, 0, 3, 0), 175000, "cứu", "MUA", best=True)

    text = _text(build_steps(state, {1: (RISKY, SAFE)}, 1.5, shop_sim=sim,
                             names={"pin": "Kim Ghim", "ward": "Vảy Rồng Nứt"}, merchant=[item]))

    assert "Mua relic Kim Ghim" in text
    assert "Thương nhân: mua Vảy Rồng Nứt" in text


def test_choose_tribute_uses_small_finished_swords_first():
    swords = [_sword(1, 9000, 12), _sword(2, 2000, 6), _sword(3, 1500, 5)]

    chosen = choose_tribute(swords, need=3000, finished={1, 2, 3})

    assert [s.serial for s in chosen] == [3, 2]


def test_break_reducing_relic_suggested_when_no_ev_gain_now():
    sword = _sword(1, 320, 0)
    g12 = SwordOdds.from_permille([400, 50, 50, 450, 50])
    safer = SwordOdds.from_permille([300, 50, 50, 550, 50])
    state = _state((sword,), shopping=True, offers=(Offer("pin", 1, False),))
    sim = ShopSimulation(buy={"pin": {1: SAFE}}, grade_base={12: g12}, grade_buy={"pin": {12: safer}})

    text = _text(build_steps(state, {1: (SAFE, SAFE)}, 1.5, shop_sim=sim, names={"pin": "Kim Ghim"}))

    assert "Cân nhắc relic Kim Ghim" in text and "@+12 gãy 40%->30%" in text


def test_tomorrow_quota_compared_with_value_left_after_tribute():
    swords = (_sword(1, 5000, 10), _sword(2, 320, 0), _sword(3, 320, 0))
    odds = {1: (RISKY, SAFE), 2: (SAFE, SAFE), 3: (SAFE, SAFE)}

    text = _text(build_steps(_state(swords), odds, 1.5, quota=3000, next_quota=4350))

    assert "Ngày mai cống 4,350: sau khi nộp còn 640 -> cần tăng x6.8" in text


def test_tomorrow_quota_already_covered():
    swords = (_sword(1, 5000, 10), _sword(2, 9000, 12))
    odds = {1: (RISKY, SAFE), 2: (RISKY, SAFE)}

    text = _text(build_steps(_state(swords), odds, 1.5, quota=3000, next_quota=4350))

    assert "Ngày mai cống 4,350: sau khi nộp còn 9,000 (đủ)" in text


def test_free_reroll_suggested_when_no_offer_helps():
    sword = _sword(1, 5000, 8)
    state = _state((sword,), shopping=True, offers=(Offer("pin", 1, False),))
    sim = ShopSimulation(buy={"pin": {1: RISKY}})

    text = _text(build_steps(state, {1: (RISKY, SAFE)}, 1.5, shop_sim=sim,
                             reroll_text="1 LẦN MIỄN PHÍ"))

    assert "đổi lượt (miễn phí)" in text


def _rank(*ids):
    base = {"8": [50, 0, 0, 0, 0], "12": [150, 0, 0, 0, 0], "16": [250, 0, 0, 0, 0]}
    items = {rid: {"8": [40, 0, 0, 0, 0], "12": [150 - 10 * (i + 1), 0, 0, 0, 0],
                   "16": [200, 0, 0, 0, 0]} for i, rid in enumerate(ids)}
    return parse_relic_rank({"baseline": base, "items": items})


def test_star_step_for_top_ranked_shop_offer_and_no_reroll():
    state = _state((_sword(1, 5000, 8),), shopping=True, offers=(Offer("seal", 1, False),))

    text = _text(build_steps(state, {1: (RISKY, SAFE)}, 1.5, names={"seal": "Nút Thắt Đen"},
                             reroll_text="1 LẦN MIỄN PHÍ", relic_rank=_rank("seal")))

    assert "★ Mua Nút Thắt Đen: giảm gãy @+12 15.0%->14.0%" in text
    assert "đổi lượt" not in text


def test_star_marks_best_purchase_instead_of_duplicating():
    better = SwordOdds.from_permille([50, 20, 80, 750, 100])
    state = _state((_sword(1, 5000, 8),), shopping=True, offers=(Offer("pin", 1, False),))
    sim = ShopSimulation(buy={"pin": {1: better}})

    text = _text(build_steps(state, {1: (RISKY, SAFE)}, 1.5, shop_sim=sim, names={"pin": "Kim Ghim"},
                             relic_rank=_rank("pin")))

    assert "★ Mua relic Kim Ghim" in text
    assert text.count("Kim Ghim") == 1
