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
from .fever_calibration import DEFAULT_FEVER_STRIKES
from .i18n import t
from .pace import contract_pace, pace_detail, pace_line, schedule_lines
from .planner import FEVER_THRESHOLD, Plan, plan_sword
from .save_reader import RunState, Sword, display_sort_key
from .text_format import LOW, SEP, fmt_int, fmt_pct, fmt_ratio
from .tribute import TributeStatus, tribute_decision, tribute_override, tribute_status

TITLE, NORMAL, GOOD, WARN, DIM = "title", "normal", "good", "warn", "dim"
Line = tuple[str, str]
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]
MAX_GROUPS_SHOWN = 8


def tribute_lines(state: RunState, quota: float, next_quota: float = 0.0,
                  schedule: tuple[float, ...] = (), table: GradeOddsTable | None = None,
                  multiplier: float = 1.5,
                  fever_strikes: int = DEFAULT_FEVER_STRIKES) -> list[Line]:
    """Dòng cống hôm nay + cống các ngày tới + tiến độ (khi biết lịch cống)."""
    status = tribute_status(state, quota)
    if status is None:
        return []
    schedule = schedule or ((next_quota,) if next_quota > 0 else ())
    head = t("tribute.today", quota=fmt_int(status.quota), delivered=fmt_int(status.delivered))
    if status.need <= 0:
        lines = [(head + t("tribute.done"), GOOD)]
    elif status.shortfall > 0:
        lines = [(head + t("tribute.short", amount=fmt_int(status.shortfall)), WARN)]
    else:
        lines = [(head + t("tribute.enough_if_offered"), GOOD)]
    lines.append(("  " + t("tribute.holdings", value=fmt_int(status.holdings)), NORMAL))
    if schedule:
        lines += [("  " + row, DIM) for row in schedule_lines(state.round, schedule)]
    live = [sw for sw in state.swords if sw.is_live]
    pace = contract_pace(live, status.need, schedule, table, multiplier, fever_strikes)
    if pace is not None:
        text, tag = pace_line(pace)
        lines += [("  " + text, tag), ("    " + pace_detail(pace), DIM)]
    return lines


def _group_key(sw: Sword, odds: OddsMap) -> tuple:
    return (sw.grade, sw.value, sw.strikes, sw.success_streak, sw.damage_count, sw.heated,
            sw.fever_remaining > 0, sw.charge, sw.peak, odds.get(sw.serial))


def _label(sw: Sword, count: int) -> tuple[str, list[str]]:
    """(dòng chính, các ý của dòng phụ) mô tả một kiếm hoặc một nhóm kiếm giống nhau."""
    if count > 1:
        return (t("sword.group", count=count, tag=sw.tag, value=fmt_int(sw.value)),
                [t("sword.strikes", count=sw.strikes)])
    head = t("sword.head", tag=sw.tag, value=fmt_int(sw.value))
    if sw.peak > sw.value:
        head += t("sword.peak", value=fmt_int(sw.peak))  # từng có giá trị cao hơn rồi bị tụt
    if sw.heated:
        head += SEP + t("sword.heated")
    if sw.fever_remaining > 0:
        head += SEP + t("sword.in_fever")
    details = [t("sword.strikes", count=sw.strikes), t("sword.streak", count=sw.success_streak)]
    if sw.success_rate is not None:
        details.append(t("sword.success_rate", pct=fmt_pct(sw.success_rate)))
    if sw.damage_count:
        details.append(t("sword.damage_count", count=sw.damage_count))
    if sw.charge:
        details.append(t("sword.charge", charge=sw.charge, threshold=FEVER_THRESHOLD))
    return head, details


@dataclass(frozen=True)
class SwordVerdict:
    verdict: str          # chữ hiển thị, bắt đầu bằng "ĐẬP" hoặc "DỪNG" của ngôn ngữ đang dùng
    odds: SwordOdds       # tỉ lệ đang áp dụng (Xuất Thần nếu đang Xuất Thần)
    one_step: Advice
    plan: Plan | None
    strike: bool = False
    safe: bool = False     # nhát này không thể gãy
    tribute: bool = False  # quyết định do cống hôm nay


def sword_verdict(sw: Sword, odds: OddsMap, multiplier: float, status: TributeStatus | None,
                  table: GradeOddsTable | None,
                  fever_strikes: int = DEFAULT_FEVER_STRIKES) -> SwordVerdict | None:
    """Gợi ý cuối cùng cho một kiếm theo thứ tự ưu tiên ở đầu module."""
    pair = odds.get(sw.serial)
    if pair is None:
        return None
    in_fever = sw.fever_remaining > 0
    o = pair[1] if in_fever else pair[0]
    one_step = advise(o, multiplier)
    plan = None
    if not in_fever and table is not None and table.valid:
        plan = plan_sword(sw.grade, sw.charge, table.normal, table.fever, multiplier,
                          fever_strikes)
    decision = None if in_fever else tribute_decision(sw, o, status, multiplier)
    if decision is not None:
        return SwordVerdict(tribute_override(sw, o, status, multiplier) or "", o, one_step, plan,
                            strike=decision[0], tribute=True)
    if plan is not None:
        safe = plan.strike and o.destruction <= 0
        verdict = t("verdict.strike_safe") if safe else plan.verdict
        return SwordVerdict(verdict, o, one_step, plan, strike=plan.strike, safe=safe)
    return SwordVerdict(one_step.verdict, o, one_step, plan, strike=one_step.strike,
                        safe=one_step.safe)


def _advice_lines(sw: Sword, odds: OddsMap, multiplier: float, status: TributeStatus | None,
                  table: GradeOddsTable | None, fever_strikes: int) -> list[Line]:
    v = sword_verdict(sw, odds, multiplier, status, table, fever_strikes)
    if v is None:
        return []
    o, one_step, plan = v.odds, v.one_step, v.plan
    lines: list[Line] = [
        (f"    {odds_text(o)}", NORMAL),
        (f"    → {v.verdict}{SEP}" + t("sword.one_strike_ev", ratio=fmt_ratio(one_step.ev_ratio)),
         GOOD if v.strike else WARN),
    ]
    if plan is not None:
        fever_note = (t("sword.fever_next") if plan.strikes_to_fever == 0
                      else t("sword.fever_in", count=plan.strikes_to_fever))
        lines.append(("    " + t("sword.plan", verdict=plan.verdict, ratio=fmt_ratio(plan.ratio))
                      + SEP + fever_note, DIM, LOW))
    return lines


def odds_text(o: SwordOdds) -> str:
    """'Gãy 19% · Hư tổn 3% · Không đổi 16% · Thành công 48% · Xuất sắc 14%' (tên kết quả của game)."""
    parts = (("outcome.break", o.destruction), ("outcome.damage", o.damage),
             ("outcome.hold", o.hold), ("outcome.success", o.success), ("outcome.great", o.great))
    return SEP.join(f"{t(key)} {fmt_pct(p)}" for key, p in parts)


def sword_lines(state: RunState, odds: OddsMap, multiplier: float, quota: float,
                table: GradeOddsTable | None,
                fever_strikes: int = DEFAULT_FEVER_STRIKES) -> list[Line]:
    live = sorted((sw for sw in state.swords if sw.is_live), key=display_sort_key)
    lines: list[Line] = [(t("sword.title", count=len(live)), TITLE)]
    if not live:
        return lines + [("  " + t("sword.none"), DIM)]
    groups: dict[tuple, list[Sword]] = {}
    for sw in live:  # dict giữ thứ tự chèn -> nhóm vẫn xếp theo giá trị giảm dần
        groups.setdefault(_group_key(sw, odds), []).append(sw)
    status = tribute_status(state, quota)
    for members in list(groups.values())[:MAX_GROUPS_SHOWN]:
        sw = members[0]
        head, details = _label(sw, len(members))
        lines.append(("  " + head, GOOD if sw.heated else NORMAL))
        lines.append(("    " + SEP.join(details), DIM, LOW))
        lines += _advice_lines(sw, odds, multiplier, status, table, fever_strikes)
    hidden = sum(len(m) for m in list(groups.values())[MAX_GROUPS_SHOWN:])
    if hidden:
        lines.append(("  " + t("sword.hidden", count=hidden), DIM))
    lines.append(("  " + t("sword.total", value=fmt_int(sum(sw.value for sw in live))), GOOD))
    return lines
