"""Danh sách các bước nên làm ngay (khung bên phải overlay).

Thứ tự ưu tiên: Xuất Thần -> nộp cống -> đập kiếm (kèm Vảy Rồng/Dây Cót) -> mua di vật
-> mua hàng Thương nhân ma. Mọi gợi ý dùng lại đúng logic của các phần bên trái.
Mỗi bước một dòng ngắn; chi tiết (nếu có) nằm ở dòng phụ thụt vào ``DETAIL``.
"""
from __future__ import annotations

from .advisor import GradeOddsTable, ShopSimulation, SwordOdds
from .fever_calibration import DEFAULT_FEVER_STRIKES
from .merchant_advice import MerchantItem
from .pace import Pace, contract_pace, pace_line, risk_hint
from .relic_names import display_name
from .relic_rank import RelicRank, star_step, top_offer
from .reroll_advice import parse_reroll_text, reroll_line
from .save_reader import RunState, Sword
from .shop_advice import best_break_reduction, best_purchase, target_sword
from .sword_section import sword_verdict
from .text_format import ARROW, SEP, fmt_int, fmt_pct, fmt_ratio, wrap_lines
from .tribute import choose_tribute, tribute_status

TITLE, NORMAL, GOOD, WARN, DIM = "title", "normal", "good", "warn", "dim"
ALERT = "alert"  # chữ to, nền đỏ: việc phải làm NGAY
Line = tuple[str, str]
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]
MERCHANT_SWORD_NAMES = {"sword": "Kiếm Sắt"}
MAX_STRIKE_STEPS = 5
DETAIL = "   "  # thụt đầu dòng phụ của một bước


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
            ratios[serial] = max(v.one_step.ev_ratio, 1.0) if v.one_step.verdict.startswith("ĐẬP") else 1.0
    return ratios


def _strike_steps(live: list[Sword], verdicts: dict, state: RunState, top: Sword | None,
                  reserved: set[int]) -> list[Line]:
    """``reserved``: kiếm đã chọn để nộp cống -> không đập nếu còn rủi ro gãy."""
    steps: list[Line] = []
    groups: dict[tuple, list[Sword]] = {}
    for sw in live:
        v = verdicts.get(sw.serial)
        if v is None or sw.fever_remaining > 0 or not v.verdict.startswith("ĐẬP"):
            continue
        if sw.serial in reserved and v.odds.destruction > 0:
            continue
        groups.setdefault((sw.grade, sw.value, v.verdict), []).append(sw)
    for (grade, _value, verdict), members in list(groups.items())[:MAX_STRIKE_STEPS]:
        sw = members[0]
        safe = " (an toàn)" if "an toàn" in verdict else ""
        if len(members) > 1:
            steps.append((f"Đập {len(members)} kiếm +{grade} {sw.where}{safe}", GOOD))
            continue
        extra = []
        if not safe and sw is top and state.ward_charges > 0:
            extra.append("Bấm Q (Vảy Rồng) trước")
        plan = verdicts[sw.serial].plan
        if plan is not None and plan.strikes_to_fever <= 2:
            extra.append(f"Còn {plan.strikes_to_fever} nhát nữa tới Xuất Thần")
        steps.append((f"Đập {sw.tag}{safe}", GOOD))
        if extra:
            steps.append((DETAIL + SEP.join(extra), DIM))
    return steps


def _tomorrow_lines(next_quota: float, left: float) -> list[Line]:
    """Cống ngày mai so với giá trị kiếm còn giữ lại: còn phải rèn tăng bao nhiêu lần."""
    detail = f"{DETAIL}Sau khi nộp hôm nay còn {fmt_int(left)}"
    if left >= next_quota:
        return [(f"Ngày mai cống {fmt_int(next_quota)}: đủ", DIM), (detail, DIM)]
    head = f"Ngày mai cống {fmt_int(next_quota)}: chưa đủ"
    if left <= 0:
        return [(head, WARN), (f"{detail}{ARROW}cần kiếm mới / rèn thêm", DIM)]
    return [(head, WARN), (f"{detail}{ARROW}cần tăng {fmt_ratio(next_quota / left, 1)}", DIM)]


def _risk_step(top: Sword | None, verdicts: dict, pace: Pace | None, state: RunState,
               reserved: set[int]) -> Line | None:
    """Đẩy/giữ an toàn kiếm chính theo tiến độ; không bao giờ đè quy tắc an toàn cống hôm nay."""
    v = verdicts.get(top.serial) if top is not None else None
    if v is None:
        return None
    locked = (top.serial in reserved and v.odds.destruction > 0) or "cống" in v.verdict
    hint = risk_hint(top, v.plan, v.odds, pace, state.ward_charges, locked)
    if hint is None:
        return None
    return hint, (GOOD if hint.startswith("Đang chậm") else WARN)


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
        swap = f"Bỏ {display_name(drop, names)}{SEP}" if drop else ""
        mark = "★ " if offer_id == star_id else ""
        lines += [(f"{mark}Mua di vật {display_name(offer_id, names)}", GOOD),
                  (f"{DETAIL}{swap}kỳ vọng {fmt_ratio(ev0)}{ARROW}{fmt_ratio(ev1)}"
                   f"{SEP}trả bằng kiếm +0", DIM)]
    else:
        hint = best_break_reduction(offer_ids, top, sim, multiplier)
        if hint is not None and hint[0] != star_id:
            offer_id, drop, grade, before, after = hint
            swap = f"Bỏ {display_name(drop, names)}{SEP}" if drop else ""
            lines += [(f"Cân nhắc mua di vật {display_name(offer_id, names)}", NORMAL),
                      (f"{DETAIL}{swap}ở cấp +{grade}: gãy {fmt_pct(before.destruction)}{ARROW}"
                       f"{fmt_pct(after.destruction)} (lợi khi kiếm lên cao)", DIM)]
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
    lines: list[Line] = [("Việc cần làm", TITLE)]
    if state is None:
        return lines + [("Chưa có dữ liệu lượt chơi.", DIM)]
    names = names or {}
    live = sorted((s for s in state.swords if s.is_live), key=lambda s: s.value, reverse=True)
    status = tribute_status(state, quota)
    verdicts = {s.serial: v for s in live
                if (v := sword_verdict(s, odds, multiplier, status, table, fever_strikes)) is not None}
    top = target_sword(state.swords, odds)

    for sw in live:  # 1. Xuất Thần: tận dụng ngay, không thể gãy
        if sw.fever_remaining > 0:
            lines += [(f"XUẤT THẦN {sw.tag}: ĐẬP LIÊN TỤC!", ALERT),
                      (f"{DETAIL}~{fever_strikes} nhát, không thể gãy", GOOD)]

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
            lines.append(("Cống hôm nay: đã đủ", DIM))
            left_after = status.holdings
        elif status.shortfall > 0:
            lines += [(f"Thiếu {fmt_int(status.shortfall)} cống", WARN),
                      (f"{DETAIL}Đập kiếm để tăng giá trị", DIM)]
        else:
            chosen = choose_tribute(live, status.need, _future_ratios(verdicts))
            if chosen:
                reserved = {s.serial for s in chosen}
                ids = ", ".join(s.tag for s in chosen)
                total = sum(s.value for s in chosen)
                left_after = status.holdings - total
                lines += [(f"Cuối ngày nộp cống: {ids}", GOOD),
                          (f"{DETAIL}Tổng {fmt_int(total)} / cần {fmt_int(status.need)}"
                           f"{SEP}giữ lại, đừng đập liều", DIM)]

    if next_quota > 0 and left_after is not None:
        lines += _tomorrow_lines(next_quota, left_after)
    hint = _risk_step(top, verdicts, pace, state, reserved)
    hold_back = set(reserved)
    if hint is not None:
        lines.append(hint)
        if top is not None and "chơi an toàn" in hint[0]:
            hold_back.add(top.serial)  # đã khuyên đừng mạo hiểm -> không hiện bước "Đập" mâu thuẫn
    lines += _strike_steps(live, verdicts, state, top, hold_back)  # 3. Đập kiếm
    if top is not None and state.rewind_charges > 0 and odds[top.serial][0].destruction > 0:
        lines.append((f"Nếu {top.tag} gãy: bấm R (Dây Cót) để hồi", DIM))

    if state.shopping:  # 4. Cửa hàng di vật
        lines += _shop_steps(state, top, odds, multiplier, shop_sim or ShopSimulation(), names,
                             reroll_text, relic_rank)

    for item in sorted(merchant or [], key=lambda i: i.ratio or 0, reverse=True):  # 5. Thương nhân
        if item.verdict == "MUA":
            name = MERCHANT_SWORD_NAMES.get(item.offer.id) or display_name(item.offer.id, names)
            lines.append((f"Thương nhân ma: mua {name} ({fmt_int(item.offer.price)} G)", GOOD))
    merchant_ids = [i.offer.id for i in merchant or [] if not i.offer.sold]
    star = star_step(relic_rank, merchant_ids, names)  # hàng Thương nhân nằm trong top giảm gãy
    if star and star[0] not in lines:
        lines += star

    if len(lines) == 1:
        lines.append(("Không có việc cần làm ngay", DIM))
    return wrap_lines(lines)
