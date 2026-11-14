"""Gợi ý mua / bỏ / đổi relic, dựa trên mô phỏng bằng hàm tính tỉ lệ của game.

So sánh chính làm trên thanh kiếm giá trị nhất (thanh đang gánh rủi ro lớn nhất); thêm tỉ lệ
ở các grade mục tiêu (+8, +12, ...) để relic giảm gãy vẫn được đánh giá khi kiếm còn thấp.
"""
from __future__ import annotations

from .advisor import ShopSimulation, SwordOdds, advise
from .relic_names import display_name
from .save_reader import Sword

GOOD, WARN, DIM = "good", "warn", "dim"
ODDS_EPSILON = 0.0005  # chênh lệch < 0.05% coi như không đổi
BREAK_REDUCTION_HINT = 0.02  # giảm gãy >= 2 điểm % ở grade cao -> đáng cân nhắc
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]
Line = tuple[str, str]
_FIELDS = ("destruction", "damage", "hold", "success", "great")


def target_sword(swords: tuple[Sword, ...], odds: OddsMap) -> Sword | None:
    live = [sw for sw in swords if sw.is_live and sw.serial in odds]
    return max(live, key=lambda sw: sw.value, default=None)


def _unchanged(a: SwordOdds, b: SwordOdds) -> bool:
    return all(abs(getattr(a, f) - getattr(b, f)) < ODDS_EPSILON for f in _FIELDS)


def _ev(o: SwordOdds, multiplier: float) -> float:
    return advise(o, multiplier).ev_ratio


def _delta_text(before: SwordOdds, after: SwordOdds, multiplier: float) -> str:
    return (f"gãy {before.destruction:.0%}->{after.destruction:.0%} "
            f"thành {before.success:.0%}->{after.success:.0%} "
            f"EV x{_ev(before, multiplier):.2f}->{_ev(after, multiplier):.2f}")


def _tag(before: SwordOdds, after: SwordOdds, multiplier: float) -> str:
    return GOOD if _ev(after, multiplier) > _ev(before, multiplier) else WARN


def _after_purchase(offer_id: str, target: Sword, sim: ShopSimulation,
                    multiplier: float) -> tuple[str | None, SwordOdds] | None:
    """(relic phải bỏ hoặc None, tỉ lệ sau khi mua) cho phương án tốt nhất của một món."""
    swaps = sim.swap.get(offer_id)
    if swaps:
        options = [(rid, per[target.serial]) for rid, per in swaps.items() if target.serial in per]
        return max(options, key=lambda item: _ev(item[1], multiplier)) if options else None
    after = sim.buy.get(offer_id, {}).get(target.serial)
    return (None, after) if after is not None else None


def best_purchase(offer_ids: list[str], target: Sword | None, odds: OddsMap,
                  sim: ShopSimulation, multiplier: float) -> tuple[str, str | None, float, float] | None:
    """Món relic làm EV kiếm quý nhất tăng nhiều nhất: (id, relic phải bỏ, EV trước, EV sau)."""
    if target is None or target.serial not in odds:
        return None
    ev0 = _ev(odds[target.serial][0], multiplier)
    best = None
    for offer_id in offer_ids:
        found = _after_purchase(offer_id, target, sim, multiplier)
        if found is None:
            continue
        ev1 = _ev(found[1], multiplier)
        if ev1 > ev0 + ODDS_EPSILON and (best is None or ev1 > best[3]):
            best = (offer_id, found[0], ev0, ev1)
    return best


def buy_line(offer_id: str, target: Sword | None, odds: OddsMap, sim: ShopSimulation,
             multiplier: float, names: dict[str, str]) -> Line | None:
    """Kệ còn chỗ -> hiệu ứng khi mua; kệ đầy -> phương án đổi relic tốt nhất."""
    if target is None:
        return None
    before = odds[target.serial][0]
    found = _after_purchase(offer_id, target, sim, multiplier)
    if found is None:
        return None
    relic_id, after = found
    prefix = (f"     -> đổi {display_name(relic_id, names)}: " if relic_id
              else f"     -> {target.tag}: ")
    if _unchanged(before, after):
        return f"{prefix}không đổi tỉ lệ", DIM
    return prefix + _delta_text(before, after, multiplier), _tag(before, after, multiplier)


def best_drop(target: Sword | None, odds: OddsMap, sim: ShopSimulation,
              multiplier: float) -> str | None:
    """Relic mà bỏ đi thì EV của kiếm quý nhất giảm ít nhất (nên bỏ khi cần chỗ)."""
    if target is None:
        return None
    options = [(rid, per[target.serial]) for rid, per in sim.drop.items() if target.serial in per]
    if not options:
        return None
    return max(options, key=lambda item: _ev(item[1], multiplier))[0]


def drop_line(relic_id: str, target: Sword | None, odds: OddsMap, sim: ShopSimulation,
              multiplier: float, best: str | None) -> Line | None:
    if target is None:
        return None
    after = sim.drop.get(relic_id, {}).get(target.serial)
    if after is None:
        return None
    before = odds[target.serial][0]
    mark = "  <- nên bỏ" if relic_id == best else ""
    if _unchanged(before, after):
        return f"     bỏ: không đổi tỉ lệ (có thể bỏ){mark}", DIM
    ev0, ev1 = _ev(before, multiplier), _ev(after, multiplier)
    return f"     bỏ: EV x{ev0:.2f}->{ev1:.2f}{mark}", WARN if ev1 < ev0 else GOOD


GradeOdds = dict[int, SwordOdds]


def _grade_after(offer_id: str, target: Sword | None, sim: ShopSimulation,
                 multiplier: float) -> tuple[str | None, GradeOdds] | None:
    """(relic phải bỏ, tỉ lệ theo grade sau khi mua). Đổi relic -> cùng lựa chọn như với kiếm
    quý nhất; không có kiếm thì chọn phương án gãy ít nhất ở grade cao nhất."""
    swaps = sim.grade_swap.get(offer_id)
    if swaps:
        picked = _after_purchase(offer_id, target, sim, multiplier) if target is not None else None
        if picked is not None and picked[0] in swaps:
            return picked[0], swaps[picked[0]]
        options = [(rid, per) for rid, per in swaps.items() if per]
        if not options:
            return None
        return min(options, key=lambda item: item[1][max(item[1])].destruction)
    after = sim.grade_buy.get(offer_id)
    return (None, after) if after else None


def grade_line(offer_id: str, target: Sword | None, sim: ShopSimulation,
               multiplier: float) -> Line | None:
    """'@+8: gãy a%->b%, @+12: ...' so với tỉ lệ hiện tại ở cùng grade."""
    found = _grade_after(offer_id, target, sim, multiplier)
    if found is None:
        return None
    after = found[1]
    grades = [g for g in sorted(after) if g in sim.grade_base]
    if not grades:
        return None
    parts = [f"@+{g}: gãy {sim.grade_base[g].destruction:.0%}->{after[g].destruction:.0%}"
             for g in grades]
    better = any(after[g].destruction < sim.grade_base[g].destruction - ODDS_EPSILON for g in grades)
    worse = any(after[g].destruction > sim.grade_base[g].destruction + ODDS_EPSILON for g in grades)
    return "     " + ", ".join(parts), GOOD if better and not worse else WARN if worse else DIM


def best_break_reduction(offer_ids: list[str], target: Sword | None, sim: ShopSimulation,
                         multiplier: float) -> tuple[str, str | None, int, SwordOdds, SwordOdds] | None:
    """Món giảm gãy nhiều nhất ở grade mục tiêu cao nhất: (id, relic bỏ, grade, trước, sau)."""
    if not sim.grade_base:
        return None
    best = None
    for offer_id in offer_ids:
        found = _grade_after(offer_id, target, sim, multiplier)
        if found is None:
            continue
        common = [g for g in found[1] if g in sim.grade_base]
        if not common:
            continue
        g = max(common)
        before, after = sim.grade_base[g], found[1][g]
        drop = before.destruction - after.destruction
        if drop >= BREAK_REDUCTION_HINT - ODDS_EPSILON and (best is None or drop > best[0]):
            best = (drop, (offer_id, found[0], g, before, after))
    return best[1] if best else None
