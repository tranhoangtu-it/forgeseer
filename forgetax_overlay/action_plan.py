"""Danh sách các bước nên làm ngay (khung bên phải overlay).

Thứ tự ưu tiên: Xuất Thần -> nộp cống -> đập kiếm (kèm Vảy Rồng/Dây Cót) -> mua relic
-> mua hàng Thương nhân ma. Mọi gợi ý dùng lại đúng logic của các phần bên trái.
"""
from __future__ import annotations

from .advisor import GradeOddsTable, ShopSimulation, SwordOdds
from .merchant_advice import MerchantItem
from .relic_names import display_name
from .save_reader import RunState, Sword
from .shop_advice import best_purchase, target_sword
from .sword_section import sword_verdict
from .tribute import tribute_status

TITLE, NORMAL, GOOD, WARN, DIM = "title", "normal", "good", "warn", "dim"
Line = tuple[str, str]
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]
MERCHANT_SWORD_NAMES = {"sword": "Kiếm Sắt"}
MAX_STRIKE_STEPS = 5


def choose_tribute(swords: list[Sword], need: float, finished: set[int]) -> list[Sword]:
    """Chọn kiếm để nộp: ưu tiên kiếm đã 'xong' (nên DỪNG), giá trị nhỏ trước, tới khi đủ.

    Giữ lại kiếm còn tiềm năng; kiếm lớn để dành cho các vòng sau (cống tăng rất nhanh).
    """
    done = sorted((s for s in swords if s.serial in finished), key=lambda s: s.value)
    growing = sorted((s for s in swords if s.serial not in finished), key=lambda s: s.value)
    chosen, total = [], 0.0
    for sw in done + growing:
        if total >= need:
            break
        chosen.append(sw)
        total += sw.value
    return chosen if total >= need else []


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
            steps.append((f"Đập x{len(members)} kiếm +{grade} {sw.where}{safe}", GOOD))
            continue
        extra = ""
        if not safe and sw is top and state.ward_charges > 0:
            extra = " - bấm Q (Vảy Rồng) trước"
        plan = verdicts[sw.serial].plan
        if plan is not None and plan.strikes_to_fever <= 2:
            extra += f" - còn {plan.strikes_to_fever} nhát tới Xuất Thần"
        steps.append((f"Đập {sw.tag}{safe}{extra}", GOOD))
    return steps


def build_steps(state: RunState | None, odds: OddsMap, multiplier: float, quota: float = 0.0,
                table: GradeOddsTable | None = None, shop_sim: ShopSimulation | None = None,
                names: dict[str, str] | None = None,
                merchant: list[MerchantItem] | None = None) -> list[Line]:
    lines: list[Line] = [("Việc cần làm", TITLE)]
    if state is None:
        return lines + [("Chưa có dữ liệu lượt chơi.", DIM)]
    names = names or {}
    live = sorted((s for s in state.swords if s.is_live), key=lambda s: s.value, reverse=True)
    status = tribute_status(state, quota)
    verdicts = {s.serial: v for s in live
                if (v := sword_verdict(s, odds, multiplier, status, table)) is not None}
    top = target_sword(state.swords, odds)

    for sw in live:  # 1. Xuất Thần: tận dụng ngay, không thể gãy
        if sw.fever_remaining > 0:
            lines.append((f"XUẤT THẦN {sw.tag}: đập liên tục thật nhanh!", WARN))

    reserved: set[int] = set()
    if status is not None:  # 2. Cống nạp
        if status.need <= 0:
            lines.append(("Cống hôm nay: đã đủ", DIM))
        elif status.shortfall > 0:
            lines.append((f"Thiếu {status.shortfall:,.0f} cống: đập kiếm để tăng giá trị", WARN))
        else:
            finished = {s for s, v in verdicts.items() if v.verdict.startswith("DỪNG")}
            chosen = choose_tribute(live, status.need, finished)
            if chosen:
                reserved = {s.serial for s in chosen}
                ids = ", ".join(s.tag for s in chosen)
                total = sum(s.value for s in chosen)
                lines.append((f"Cuối ngày nộp cống: {ids} (= {total:,} / cần {status.need:,.0f}) "
                              f"- giữ, đừng đập liều", GOOD))

    lines += _strike_steps(live, verdicts, state, top, reserved)  # 3. Đập kiếm
    if top is not None and state.rewind_charges > 0 and odds[top.serial][0].destruction > 0:
        lines.append((f"Nếu {top.tag} gãy: bấm R (Dây Cót) để hồi", DIM))

    if state.shopping:  # 4. Máy relic
        offer_ids = [o.id for o in state.offers if not o.sold]
        best = best_purchase(offer_ids, top, odds, shop_sim or ShopSimulation(), multiplier)
        if best is not None:
            offer_id, drop, ev0, ev1 = best
            swap = f", bỏ {display_name(drop, names)}" if drop else ""
            lines.append((f"Mua relic {display_name(offer_id, names)}{swap} "
                          f"(EV x{ev0:.2f}->{ev1:.2f}; trả bằng kiếm +0)", GOOD))

    for item in sorted(merchant or [], key=lambda i: i.ratio or 0, reverse=True):  # 5. Thương nhân
        if item.verdict == "MUA":
            name = MERCHANT_SWORD_NAMES.get(item.offer.id) or display_name(item.offer.id, names)
            lines.append((f"Thương nhân: mua {name} - {item.offer.price:,.0f}", GOOD))

    if len(lines) == 1:
        lines.append(("Không có việc cần làm ngay", DIM))
    return lines
