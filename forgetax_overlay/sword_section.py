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
from .pace import contract_pace, pace_detail, pace_line, schedule_lines
from .planner import FEVER_THRESHOLD, Plan, plan_sword
from .save_reader import RunState, Sword
from .text_format import SEP, fmt_int, fmt_pct, fmt_ratio
from .tribute import TributeStatus, tribute_override, tribute_status

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
    head = f"Cống hôm nay: cần {fmt_int(status.quota)}{SEP}đã nộp {fmt_int(status.delivered)}"
    if status.need <= 0:
        lines = [(head + " → ĐÃ ĐỦ", GOOD)]
    elif status.shortfall > 0:
        lines = [(head + f" → THIẾU {fmt_int(status.shortfall)}", WARN)]
    else:
        lines = [(head + " → ĐỦ nếu nộp", GOOD)]
    lines.append((f"  Kiếm đang giữ: {fmt_int(status.holdings)}", NORMAL))
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
        return (f"{count} thanh {sw.tag}{SEP}giá trị {fmt_int(sw.value)}/thanh",
                [f"Đã đập {sw.strikes} nhát"])
    head = f"{sw.tag}{SEP}giá trị {fmt_int(sw.value)}"
    if sw.peak > sw.value:
        head += f" (từng đạt {fmt_int(sw.peak)})"  # từng có giá trị cao hơn rồi bị tụt
    if sw.heated:
        head += f"{SEP}đang nung"
    if sw.fever_remaining > 0:
        head += f"{SEP}ĐANG XUẤT THẦN"
    details = [f"Đã đập {sw.strikes} nhát", f"Thành công liên tiếp: {sw.success_streak}"]
    if sw.success_rate is not None:
        details.append(f"Tỉ lệ thành công: {fmt_pct(sw.success_rate)}")
    if sw.damage_count:
        details.append(f"Hư tổn: {sw.damage_count} lần")
    if sw.charge:
        details.append(f"Tích lực Xuất Thần: {sw.charge}/{FEVER_THRESHOLD}")
    return head, details


@dataclass(frozen=True)
class SwordVerdict:
    verdict: str          # bắt đầu bằng "ĐẬP" hoặc "DỪNG"
    odds: SwordOdds       # tỉ lệ đang áp dụng (Xuất Thần nếu đang Xuất Thần)
    one_step: Advice
    plan: Plan | None


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
    verdict = None if in_fever else tribute_override(sw, o, status, multiplier)
    if verdict is None and plan is not None:
        verdict = plan.verdict
        if verdict == "ĐẬP" and o.destruction <= 0:
            verdict = "ĐẬP (an toàn)"
    return SwordVerdict(verdict or one_step.verdict, o, one_step, plan)


def _advice_lines(sw: Sword, odds: OddsMap, multiplier: float, status: TributeStatus | None,
                  table: GradeOddsTable | None, fever_strikes: int) -> list[Line]:
    v = sword_verdict(sw, odds, multiplier, status, table, fever_strikes)
    if v is None:
        return []
    o, one_step, plan, verdict = v.odds, v.one_step, v.plan, v.verdict
    lines: list[Line] = [
        (f"    {odds_text(o)}", NORMAL),
        (f"    → {verdict}{SEP}kỳ vọng 1 nhát {fmt_ratio(one_step.ev_ratio)}",
         WARN if verdict.startswith("DỪNG") else GOOD),
    ]
    if plan is not None:
        fever_note = ("nhát kế tiếp vào Xuất Thần" if plan.strikes_to_fever == 0
                      else f"còn {plan.strikes_to_fever} nhát nữa tới Xuất Thần")
        lines.append((f"    Kế hoạch nhiều nhát: {plan.verdict} (kỳ vọng {fmt_ratio(plan.ratio)})"
                      f"{SEP}{fever_note}", DIM))
    return lines


def odds_text(o: SwordOdds) -> str:
    """'Gãy 19% · Hư tổn 3% · Không đổi 16% · Thành công 48% · Xuất sắc 14%' (tên kết quả của game)."""
    return SEP.join((f"Gãy {fmt_pct(o.destruction)}", f"Hư tổn {fmt_pct(o.damage)}",
                     f"Không đổi {fmt_pct(o.hold)}", f"Thành công {fmt_pct(o.success)}",
                     f"Xuất sắc {fmt_pct(o.great)}"))


def sword_lines(state: RunState, odds: OddsMap, multiplier: float, quota: float,
                table: GradeOddsTable | None,
                fever_strikes: int = DEFAULT_FEVER_STRIKES) -> list[Line]:
    live = sorted((sw for sw in state.swords if sw.is_live), key=lambda sw: sw.value, reverse=True)
    lines: list[Line] = [(f"Kiếm đang giữ ({len(live)}):", TITLE)]
    if not live:
        return lines + [("  (không có)", DIM)]
    groups: dict[tuple, list[Sword]] = {}
    for sw in live:  # dict giữ thứ tự chèn -> nhóm vẫn xếp theo giá trị giảm dần
        groups.setdefault(_group_key(sw, odds), []).append(sw)
    status = tribute_status(state, quota)
    for members in list(groups.values())[:MAX_GROUPS_SHOWN]:
        sw = members[0]
        head, details = _label(sw, len(members))
        lines.append(("  " + head, GOOD if sw.heated else NORMAL))
        lines.append(("    " + SEP.join(details), DIM))
        lines += _advice_lines(sw, odds, multiplier, status, table, fever_strikes)
    hidden = sum(len(m) for m in list(groups.values())[MAX_GROUPS_SHOWN:])
    if hidden:
        lines.append((f"  … và {hidden} thanh nữa (không hiện)", DIM))
    lines.append((f"  Tổng giá trị: {fmt_int(sum(sw.value for sw in live))}", GOOD))
    return lines
