"""Danh sách các bước nên làm ngay (khung bên phải overlay).

Thứ tự ưu tiên: Xuất Thần -> nộp cống -> đập kiếm (kèm Vảy Rồng/Dây Cót) -> mua di vật
-> mua hàng Thương nhân ma. Mọi gợi ý dùng lại đúng logic của các phần bên trái.
Mỗi bước một dòng ngắn; chi tiết (nếu có) nằm ở dòng phụ thụt vào ``DETAIL``.
"""
from __future__ import annotations

from .advisor import GradeOddsTable, ShopSimulation, SwordOdds
from .fever_calibration import DEFAULT_FEVER_STRIKES
from .i18n import t
from .merchant_advice import MerchantItem
from .pace import Pace, contract_pace, pace_line, risk_hint
from .relic_names import display_name
from .relic_rank import RelicRank, star_step, top_offer
from .reroll_advice import parse_reroll_text, reroll_line
from .save_reader import RunState, Sword, display_sort_key
from .shop_advice import best_break_reduction, best_purchase, target_sword
from .sword_section import sword_verdict
from .text_format import ARROW, SEP, fmt_int, fmt_pct, fmt_ratio, wrap_lines
from .tribute import choose_tribute, tribute_status

TITLE, NORMAL, GOOD, WARN, DIM = "title", "normal", "good", "warn", "dim"
ALERT = "alert"  # chữ to, nền đỏ: việc phải làm NGAY
Line = tuple[str, str]
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]
MERCHANT_SWORD_KEYS = {"sword": "merchant.iron_sword"}  # hàng không nằm trong bảng tên di vật
MAX_STRIKE_STEPS = 5
DETAIL = "   "  # thụt đầu dòng phụ của một bước


def merchant_name(item_id: str, names: dict[str, str]) -> str:
    key = MERCHANT_SWORD_KEYS.get(item_id)
    return t(key) if key else display_name(item_id, names)


def _future_ratios(verdicts: dict) -> dict[int, float]:
    """Tỉ lệ giá trị tương lai mỗi kiếm cho việc chọn kiếm nộp cống.

    Kiếm đã 'xong' (kế hoạch/EV nói DỪNG) = 1; còn lại = Plan.ratio, không có kế hoạch thì EV
    một nhát (>= 1). DỪNG chỉ vì cống KHÔNG tính là 'xong'.
    """
    ratios: dict[int, float] = {}
    for serial, v in verdicts.items():
        if v.plan is not None:
            ratios[serial] = v.plan.ratio
        else:
            ratios[serial] = max(v.one_step.ev_ratio, 1.0) if v.one_step.strike else 1.0
    return ratios


def _strike_steps(live: list[Sword], verdicts: dict, state: RunState, top: Sword | None,
                  reserved: set[int]) -> list[Line]:
    """``reserved``: kiếm đã chọn để nộp cống -> không đập nếu còn rủi ro gãy."""
    steps: list[Line] = []
    groups: dict[tuple, list[Sword]] = {}
    for sw in live:
        v = verdicts.get(sw.serial)
        if v is None or sw.fever_remaining > 0 or not v.strike:
            continue
        if sw.serial in reserved and v.odds.destruction > 0:
            continue
        groups.setdefault((sw.grade, sw.value, v.verdict, v.safe), []).append(sw)
    for (grade, _value, _verdict, is_safe), members in list(groups.items())[:MAX_STRIKE_STEPS]:
        sw = members[0]
        safe = t("step.safe_suffix") if is_safe else ""
        if len(members) > 1:
            steps.append((t("step.strike_group", count=len(members), grade=grade, where=sw.where)
                          + safe, GOOD))
            continue
        extra = []
        if not safe and sw is top and state.ward_charges > 0:
            extra.append(t("step.ward_first"))
        plan = verdicts[sw.serial].plan
        if plan is not None and plan.strikes_to_fever <= 2:
            extra.append(t("step.fever_in", count=plan.strikes_to_fever))
        steps.append((t("step.strike", tag=sw.tag) + safe, GOOD))
        if extra:
            steps.append((DETAIL + SEP.join(extra), DIM))
    return steps


def _tomorrow_lines(next_quota: float, left: float) -> list[Line]:
    """Cống ngày mai so với giá trị kiếm còn giữ lại: còn phải rèn tăng bao nhiêu lần."""
    detail = DETAIL + t("step.left_after", value=fmt_int(left))
    if left >= next_quota:
        return [(t("step.tomorrow_ok", quota=fmt_int(next_quota)), DIM), (detail, DIM)]
    head = t("step.tomorrow_short", quota=fmt_int(next_quota))
    if left <= 0:
        return [(head, WARN), (detail + ARROW + t("step.need_new_swords"), DIM)]
    return [(head, WARN),
            (detail + ARROW + t("step.need_growth", ratio=fmt_ratio(next_quota / left, 1)), DIM)]


def _risk_step(top: Sword | None, verdicts: dict, pace: Pace | None, state: RunState,
               reserved: set[int]) -> Line | None:
    """Đẩy/giữ an toàn kiếm chính theo tiến độ; không bao giờ đè quy tắc an toàn cống hôm nay."""
    v = verdicts.get(top.serial) if top is not None else None
    if v is None:
        return None
    locked = (top.serial in reserved and v.odds.destruction > 0) or v.tribute
    hint = risk_hint(top, v.plan, v.odds, pace, state.ward_charges, locked)
    if hint is None:
        return None
    # risk_hint chỉ khuyên đẩy khi chậm tiến độ, còn lại là khuyên chơi an toàn.
    return hint, (GOOD if pace is not None and pace.behind else WARN)


def offered_ids(state: RunState, merchant: list[MerchantItem] | None) -> list[str]:
    """Id món đang bán chưa mua: cửa hàng di vật (giờ mua sắm) + Thương nhân ma."""
    shop = [o.id for o in state.offers if not o.sold] if state.shopping else []
    return shop + [i.offer.id for i in merchant or [] if not i.offer.sold]


def _shop_steps(state: RunState, top: Sword | None, odds: OddsMap, multiplier: float,
                sim: ShopSimulation, names: dict[str, str], reroll_text: str,
                relic_rank: RelicRank | None) -> list[Line]:
    """Mua di vật tăng kỳ vọng / giảm gãy; ★ = món nằm trong top giảm gãy (không lặp tên 2 lần)."""
    lines: list[Line] = []
    offer_ids = [o.id for o in state.offers if not o.sold]
    starred = top_offer(relic_rank, offer_ids)
    star_id = starred.id if starred is not None else None
    best = best_purchase(offer_ids, top, odds, sim, multiplier)
    hint = None
    if best is not None:
        offer_id, drop, ev0, ev1 = best
        swap = t("step.drop", name=display_name(drop, names)) + SEP if drop else ""
        mark = "★ " if offer_id == star_id else ""
        lines += [(mark + t("step.buy_relic", name=display_name(offer_id, names)), GOOD),
                  (f"{DETAIL}{swap}{t('word.ev')} {fmt_ratio(ev0)}{ARROW}{fmt_ratio(ev1)}"
                   + SEP + t("step.pay_with_sword"), DIM)]
    else:
        hint = best_break_reduction(offer_ids, top, sim, multiplier)
        if hint is not None and hint[0] != star_id:
            offer_id, drop, grade, before, after = hint
            swap = t("step.drop", name=display_name(drop, names)) + SEP if drop else ""
            lines += [(t("step.consider_relic", name=display_name(offer_id, names)), NORMAL),
                      (DETAIL + swap + t("shop.at_grade", grade=grade,
                                         before=fmt_pct(before.destruction),
                                         after=fmt_pct(after.destruction))
                       + t("step.pays_off_later"), DIM)]
    if star_id is not None and (best is None or best[0] != star_id):
        lines += star_step(relic_rank, offer_ids, names)
    if best is None:
        reroll = reroll_line(parse_reroll_text(reroll_text), state.wallet,
                             has_good_offer=hint is not None or star_id is not None)
        if reroll is not None:
            lines.append(reroll)
    return lines


def build_steps(state: RunState | None, odds: OddsMap, multiplier: float, quota: float = 0.0,
                table: GradeOddsTable | None = None, shop_sim: ShopSimulation | None = None,
                names: dict[str, str] | None = None,
                merchant: list[MerchantItem] | None = None,
                fever_strikes: int = DEFAULT_FEVER_STRIKES,
                next_quota: float = 0.0, reroll_text: str = "",
                relic_rank: RelicRank | None = None,
                schedule: tuple[float, ...] = ()) -> list[Line]:
    """``schedule``: cống các ngày tới (ngày mai trước), do game tính trên campaign giả lập."""
    lines: list[Line] = [(t("step.title"), TITLE)]
    if state is None:
        return lines + [(t("step.no_data"), DIM)]
    names = names or {}
    live = sorted((s for s in state.swords if s.is_live), key=display_sort_key)
    status = tribute_status(state, quota)
    verdicts = {s.serial: v for s in live
                if (v := sword_verdict(s, odds, multiplier, status, table, fever_strikes)) is not None}
    top = target_sword(state.swords, odds)

    for sw in live:  # 1. Xuất Thần: tận dụng ngay, không thể gãy
        if sw.fever_remaining > 0:
            lines += [(t("step.fever_alert", tag=sw.tag), ALERT),
                      (DETAIL + t("step.fever_detail", count=fever_strikes), GOOD)]

    schedule = schedule or ((next_quota,) if next_quota > 0 else ())
    next_quota = next_quota or (schedule[0] if schedule else 0.0)
    pace = contract_pace(live, status.need if status else 0.0, schedule, table, multiplier,
                         fever_strikes)
    if pace is not None and pace.behind:
        lines.append(pace_line(pace))

    reserved: set[int] = set()
    left_after: float | None = None  # giá trị kiếm còn lại sau khi nộp cống hôm nay
    if status is not None:  # 2. Cống nạp
        if status.need <= 0:
            lines.append((t("step.tribute_done"), DIM))
            left_after = status.holdings
        elif status.shortfall > 0:
            lines += [(t("step.tribute_short", amount=fmt_int(status.shortfall)), WARN),
                      (DETAIL + t("step.tribute_short_detail"), DIM)]
        else:
            chosen = choose_tribute(live, status.need, _future_ratios(verdicts))
            if chosen:
                reserved = {s.serial for s in chosen}
                ids = ", ".join(s.tag for s in chosen)
                total = sum(s.value for s in chosen)
                left_after = status.holdings - total
                lines += [(t("step.offer", swords=ids), GOOD),
                          (DETAIL + t("step.offer_detail", total=fmt_int(total),
                                      need=fmt_int(status.need)), DIM)]

    if next_quota > 0 and left_after is not None:
        lines += _tomorrow_lines(next_quota, left_after)
    hint = _risk_step(top, verdicts, pace, state, reserved)
    hold_back = set(reserved)
    if hint is not None:
        lines.append(hint)
        if top is not None and hint[1] == WARN:
            hold_back.add(top.serial)  # đã khuyên đừng mạo hiểm -> không hiện bước "Đập" mâu thuẫn
    lines += _strike_steps(live, verdicts, state, top, hold_back)  # 3. Đập kiếm
    if top is not None and state.rewind_charges > 0 and odds[top.serial][0].destruction > 0:
        lines.append((t("step.rewind_hint", tag=top.tag), DIM))

    if state.shopping:  # 4. Cửa hàng di vật
        lines += _shop_steps(state, top, odds, multiplier, shop_sim or ShopSimulation(), names,
                             reroll_text, relic_rank)

    for item in sorted(merchant or [], key=lambda i: i.ratio or 0, reverse=True):  # 5. Thương nhân
        if item.verdict == t("merchant.buy"):
            lines.append((t("step.merchant_buy", name=merchant_name(item.offer.id, names),
                            price=fmt_int(item.offer.price)), GOOD))
    merchant_ids = [i.offer.id for i in merchant or [] if not i.offer.sold]
    star = star_step(relic_rank, merchant_ids, names)  # hàng Thương nhân nằm trong top giảm gãy
    if star and star[0] not in lines:
        lines += star

    if len(lines) == 1:
        lines.append((t("step.nothing"), DIM))
    return wrap_lines(lines)
