from forgetax_overlay.advisor import ShopSimulation, SwordOdds
from forgetax_overlay.save_reader import Sword
from forgetax_overlay.shop_advice import (
    best_break_reduction, best_drop, buy_line, drop_line, grade_line,
)

NOW = SwordOdds.from_permille([359, 42, 62, 496, 41])
BETTER = SwordOdds.from_permille([250, 42, 62, 600, 46])
WORSE = SwordOdds.from_permille([450, 42, 62, 410, 36])


def _sword() -> Sword:
    return Sword(serial=6, grade=17, value=533936, peak=533936, strikes=16, success_streak=3,
                 normal_hits=10, normal_successes=7, heated=False, broken=False, active=True,
                 rack=0, damage_count=0, fever_remaining=0.0)


ODDS = {6: (NOW, NOW)}


def test_buy_line_with_free_slot_uses_buy_simulation():
    sim = ShopSimulation(buy={"pin": {6: BETTER}})

    text, tag = buy_line("pin", _sword(), ODDS, sim, 1.5, {})

    assert "gãy 36%->25%" in text and tag == "good"


def test_buy_line_with_full_shelf_picks_best_swap():
    sim = ShopSimulation(swap={"pin": {"nail": {6: WORSE}, "knot": {6: BETTER}}})

    text, _ = buy_line("pin", _sword(), ODDS, sim, 1.5, {"knot": "Nút Thắt"})

    assert "đổi Nút Thắt" in text
    assert "gãy 36%->25%" in text


def test_drop_line_marks_harmless_relic_as_droppable():
    sim = ShopSimulation(drop={"knot": {6: NOW}})

    text, _ = drop_line("knot", _sword(), ODDS, sim, 1.5, best="knot")

    assert "có thể bỏ" in text and "nên bỏ" in text


def test_drop_line_shows_ev_loss_for_useful_relic():
    sim = ShopSimulation(drop={"nail": {6: WORSE}})

    text, tag = drop_line("nail", _sword(), ODDS, sim, 1.5, best=None)

    assert "bỏ: EV x0.93->" in text and tag == "warn"


def test_best_drop_is_relic_with_smallest_ev_loss():
    sim = ShopSimulation(drop={"nail": {6: WORSE}, "knot": {6: NOW}})

    assert best_drop(_sword(), ODDS, sim, 1.5) == "knot"


def test_no_target_sword_gives_no_lines():
    sim = ShopSimulation(buy={"pin": {6: BETTER}})

    assert buy_line("pin", None, ODDS, sim, 1.5, {}) is None
    assert best_drop(None, ODDS, sim, 1.5) is None


G8 = SwordOdds.from_permille([100, 50, 50, 750, 50])
G12 = SwordOdds.from_permille([400, 50, 50, 450, 50])
G12_SAFER = SwordOdds.from_permille([300, 50, 50, 550, 50])


def test_grade_line_shows_break_odds_at_target_grades():
    sim = ShopSimulation(grade_base={8: G8, 12: G12}, grade_buy={"pin": {8: G8, 12: G12_SAFER}})

    text, tag = grade_line("pin", _sword(), sim, 1.5)

    assert "@+8: gãy 10%->10%" in text and "@+12: gãy 40%->30%" in text
    assert tag == "good"


def test_grade_line_for_full_shelf_uses_swap_picked_for_target():
    sim = ShopSimulation(swap={"pin": {"nail": {6: WORSE}, "knot": {6: BETTER}}},
                         grade_base={12: G12},
                         grade_swap={"pin": {"nail": {12: G12}, "knot": {12: G12_SAFER}}})

    text, _ = grade_line("pin", _sword(), sim, 1.5)

    assert "@+12: gãy 40%->30%" in text


def test_grade_line_none_without_grade_data():
    assert grade_line("pin", _sword(), ShopSimulation(), 1.5) is None


def test_best_break_reduction_picks_largest_drop_at_highest_grade():
    sim = ShopSimulation(grade_base={8: G8, 12: G12},
                         grade_buy={"pin": {12: G12_SAFER}, "nail": {12: G12}})

    assert best_break_reduction(["nail", "pin"], None, sim, 1.5) == ("pin", None, 12, G12, G12_SAFER)
    assert best_break_reduction(["nail"], None, sim, 1.5) is None
