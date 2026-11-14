from dataclasses import replace

from forgetax_overlay.advisor import GradeOddsTable, SwordOdds
from forgetax_overlay.merchant_advice import evaluate_merchant, merchant_active
from forgetax_overlay.save_reader import MerchantOffer, RunState, Sword

RISKY = SwordOdds.from_permille([350, 30, 240, 330, 50])
SAFE = SwordOdds.from_permille([0, 50, 150, 700, 100])


def _sword(serial: int, value: int, grade: int) -> Sword:
    return Sword(serial=serial, grade=grade, value=value, peak=value, strikes=10, success_streak=0,
                 normal_hits=10, normal_successes=5, heated=False, broken=False, active=True,
                 rack=0, damage_count=0, fever_remaining=0.0)


def _state(offers, wallet=5000, merchant_round=3, round_=3) -> RunState:
    return RunState(
        active=True, round=round_, deadline_round=24, wallet=wallet, pending_tribute=0,
        successful_tributes=0, missed_tributes=0, ward_charges=0, sword_credits=0, rerolls=0,
        rewind_charges=0, shopping=False, finished=False, won=False, broken_swords=0,
        great_events=0, hold_events=0, damage_events=0, fever_events=0, gold_earned=0,
        highest_grade=0, play_seconds=0.0, relics=(), offers=(),
        swords=(_sword(6, 500000, 17),), consumables=0,
        merchant_offers=tuple(offers), merchant_round=merchant_round)


def _offer(id_, price, grade=0, sold=False) -> MerchantOffer:
    return MerchantOffer(id=id_, price=price, sold=sold, grade=grade, stock=3, purchases=0)


ODDS = {6: (RISKY, RISKY)}


def test_merchant_active_only_on_visit_round():
    assert merchant_active(_state([_offer("sword", 1040)]))
    assert not merchant_active(_state([_offer("sword", 1040)], merchant_round=0))
    assert not merchant_active(_state([_offer("sword", 1040, sold=True)]))


def test_ward_worth_is_top_sword_value_times_break_chance():
    [item] = evaluate_merchant(_state([_offer("ward", 1100)]), ODDS, 1.5, None)

    assert item.worth == 500000 * 0.35
    assert item.verdict == "MUA"


def test_sword_uses_plan_expected_value_when_table_valid():
    table = GradeOddsTable(normal={g: SAFE for g in range(30)},
                           fever={g: SAFE for g in range(30)}, valid=True)

    [item] = evaluate_merchant(_state([_offer("sword", 1040)]), ODDS, 1.5, table)

    assert item.worth > 320 * 1.5  # rèn tối ưu > giá trị gốc
    assert "kỳ vọng" in item.note


def test_unaffordable_offer_is_flagged():
    [item] = evaluate_merchant(_state([_offer("rewind", 3980)], wallet=1000), ODDS, 1.5, None)

    assert item.verdict == "thiếu vàng"


def test_best_ratio_offer_is_marked_first_choice():
    items = evaluate_merchant(_state([_offer("ward", 1100), _offer("sword", 1040)]), ODDS, 1.5, None)

    best = [i for i in items if i.best]
    assert len(best) == 1 and best[0].offer.id == "ward"


def test_unknown_offer_has_no_worth():
    [item] = evaluate_merchant(_state([_offer("mystery", 500)]), ODDS, 1.5, None)

    assert item.worth is None and item.verdict == "xem mô tả"


def test_sold_offers_are_skipped():
    state = replace(_state([_offer("ward", 1100, sold=True), _offer("sword", 1040)]))

    assert [i.offer.id for i in evaluate_merchant(state, ODDS, 1.5, None)] == ["sword"]
