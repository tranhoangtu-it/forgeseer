"""Phần hiển thị kiếm: tình trạng cống, nhóm kiếm giống nhau, tỉ lệ và kế hoạch đập.

Thứ tự ưu tiên gợi ý cho mỗi kiếm:
1. Đang Xuất Thần -> theo tỉ lệ Xuất Thần (không gãy).
2. Cống nạp làm đổi quyết định (giữ đủ cống / thiếu cống) -> theo cống.
3. Kế hoạch nhiều nhát (nếu bảng tỉ lệ theo grade hợp lệ).
4. Kỳ vọng một nhát.
"""
from __future__ import annotations

from dataclasses import dataclass

from .advisor import Advice, GradeOddsTable, SwordOdds, advise
from .planner import FEVER_THRESHOLD, Plan, plan_sword
from .save_reader import RunState, Sword
from .tribute import TributeStatus, tribute_override, tribute_status

TITLE, NORMAL, GOOD, WARN, DIM = "title", "normal", "good", "warn", "dim"
Line = tuple[str, str]
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]
MAX_GROUPS_SHOWN = 8


def tribute_lines(state: RunState, quota: float) -> list[Line]:
    status = tribute_status(state, quota)
    if status is None:
        return []
    head = f"Cống: cần {status.quota:,.0f} | đã nộp {status.delivered:,.0f} | kiếm {status.holdings:,.0f}"
    if status.need <= 0:
        return [(head + " -> ĐÃ ĐỦ", GOOD)]
    if status.shortfall > 0:
        return [(head + f" -> THIẾU {status.shortfall:,.0f}", WARN)]
    return [(head + " -> ĐỦ nếu nộp", GOOD)]


def _group_key(sw: Sword, odds: OddsMap) -> tuple:
    return (sw.grade, sw.value, sw.strikes, sw.success_streak, sw.damage_count, sw.heated,
            sw.fever_remaining > 0, sw.charge, sw.peak, odds.get(sw.serial))


def _label(sw: Sword, count: int) -> str:
    if count > 1:
        return f"x{count} {sw.tag} {sw.value:>8,}  đập {sw.strikes}"
    rate = "--" if sw.success_rate is None else f"{sw.success_rate:.0%}"
    extras = []
    if sw.peak > sw.value:
        extras.append(f"đỉnh {sw.peak:,}")  # từng có giá trị cao hơn rồi bị tụt
    if sw.damage_count:
        extras.append(f"hỏng {sw.damage_count}")
    if sw.heated:
        extras.append("NUNG")
    if sw.fever_remaining > 0:
        extras.append("FEVER")
    tail = (" " + " ".join(extras)) if extras else ""
    return (f"{sw.tag:<14} {sw.value:>8,}  "
            f"đập {sw.strikes} chuỗi {sw.success_streak} tỉ lệ {rate}{tail}")


@dataclass(frozen=True)
class SwordVerdict:
    verdict: str          # bắt đầu bằng "ĐẬP" hoặc "DỪNG"
    odds: SwordOdds       # tỉ lệ đang áp dụng (Xuất Thần nếu đang Xuất Thần)
    one_step: Advice
    plan: Plan | None


def sword_verdict(sw: Sword, odds: OddsMap, multiplier: float, status: TributeStatus | None,
                  table: GradeOddsTable | None) -> SwordVerdict | None:
    """Gợi ý cuối cùng cho một kiếm theo thứ tự ưu tiên ở đầu module."""
    pair = odds.get(sw.serial)
    if pair is None:
        return None
    in_fever = sw.fever_remaining > 0
    o = pair[1] if in_fever else pair[0]
    one_step = advise(o, multiplier)
    plan = None
    if not in_fever and table is not None and table.valid:
        plan = plan_sword(sw.grade, sw.charge, table.normal, table.fever, multiplier)
    verdict = None if in_fever else tribute_override(sw, o, status, multiplier)
    if verdict is None and plan is not None:
        verdict = plan.verdict
        if verdict == "ĐẬP" and o.destruction <= 0:
            verdict = "ĐẬP (an toàn)"
    return SwordVerdict(verdict or one_step.verdict, o, one_step, plan)


def _advice_lines(sw: Sword, odds: OddsMap, multiplier: float, status: TributeStatus | None,
                  table: GradeOddsTable | None) -> list[Line]:
    v = sword_verdict(sw, odds, multiplier, status, table)
    if v is None:
        return []
    o, one_step, plan, verdict = v.odds, v.one_step, v.plan, v.verdict
    lines: list[Line] = [(
        f"     gãy {o.destruction:.0%} hỏng {o.damage:.0%} giữ {o.hold:.0%} "
        f"thành {o.success:.0%} đại {o.great:.0%} -> {verdict} (EV x{one_step.ev_ratio:.2f})",
        WARN if verdict.startswith("DỪNG") else GOOD)]
    if plan is not None:
        fever_note = ("Xuất Thần ở nhát kế tiếp" if plan.strikes_to_fever == 0
                      else f"Xuất Thần sau {plan.strikes_to_fever} nhát")
        lines.append((f"     kế hoạch: {plan.verdict}, kỳ vọng x{plan.ratio:.2f} | {fever_note}", DIM))
    return lines


def sword_lines(state: RunState, odds: OddsMap, multiplier: float, quota: float,
                table: GradeOddsTable | None) -> list[Line]:
    live = sorted((sw for sw in state.swords if sw.is_live), key=lambda sw: sw.value, reverse=True)
    lines: list[Line] = [(f"Kiếm ({len(live)}):", TITLE)]
    if not live:
        return lines + [("  (không có)", DIM)]
    groups: dict[tuple, list[Sword]] = {}
    for sw in live:  # dict giữ thứ tự chèn -> nhóm vẫn xếp theo giá trị giảm dần
        groups.setdefault(_group_key(sw, odds), []).append(sw)
    status = tribute_status(state, quota)
    for members in list(groups.values())[:MAX_GROUPS_SHOWN]:
        sw = members[0]
        charge = f" | tích lực {sw.charge}/{FEVER_THRESHOLD}" if sw.charge and len(members) == 1 else ""
        lines.append(("  " + _label(sw, len(members)) + charge, GOOD if sw.heated else NORMAL))
        lines += _advice_lines(sw, odds, multiplier, status, table)
    hidden = sum(len(m) for m in list(groups.values())[MAX_GROUPS_SHOWN:])
    if hidden:
        lines.append((f"  ... +{hidden} thanh nữa", DIM))
    lines.append((f"  Tổng giá trị: {sum(sw.value for sw in live):,}", GOOD))
    return lines
