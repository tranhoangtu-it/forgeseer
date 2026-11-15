"""Xếp hạng relic theo mức giảm tỉ lệ gãy, do chính hàm tính tỉ lệ theo grade của game tính.

``live_relic_rank.js`` mô phỏng từng relic chưa có trên một campaign giả lập (campaign hiện tại
+ relic đó) ở các grade +8/+12/+16 với giá trị chuẩn baseValue × hệ số^grade. Chỉ bắt được hiệu
ứng cố định: relic có điều kiện (sau Thành công, sau Hư tổn, lần gãy đầu...) không mô phỏng được.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from typing import Any

from .advisor import SwordOdds
from .relic_names import display_name

TITLE, NORMAL, GOOD, DIM = "title", "normal", "good", "dim"
Line = tuple[str, str]
GradeOdds = dict[int, SwordOdds]

RANK_GRADES = (8, 12, 16)
PRIMARY_GRADE = 12
TOP_COUNT = 8
ODDS_EPSILON = 0.0005  # chênh lệch < 0.05% coi như không đổi
LINE_WIDTH = 64
# Relic giảm gãy theo điều kiện trong lúc rèn -> mô phỏng tĩnh không thấy được.
CONDITIONAL_IDS = ("brace", "repair", "star", "thread", "cornerstone", "insurance", "phoenix",
                   "spine", "eternalseed")


@dataclass(frozen=True)
class RelicRank:
    baseline: GradeOdds = field(default_factory=dict)            # campaign hiện tại
    items: dict[str, GradeOdds] = field(default_factory=dict)    # thêm relic chưa có
    owned: dict[str, GradeOdds] = field(default_factory=dict)    # bỏ relic đang có
    shelf_full: bool = False                                     # kệ đầy: thêm = ước lượng


@dataclass(frozen=True)
class RankedRelic:
    id: str
    before: GradeOdds
    after: GradeOdds

    def reduction(self, grade: int) -> float:
        if grade not in self.before or grade not in self.after:
            return 0.0
        return self.before[grade].destruction - self.after[grade].destruction


def _parse_grades(raw: Any) -> GradeOdds:
    """``{"<grade>": [5 phần nghìn]}`` -> GradeOdds; bỏ mục sai định dạng."""
    if not isinstance(raw, dict):
        return {}
    parsed: GradeOdds = {}
    for grade, values in raw.items():
        try:
            parsed[int(grade)] = SwordOdds.from_permille(values)
        except (TypeError, ValueError):
            continue
    return parsed


def _parse_by_id(raw: Any) -> dict[str, GradeOdds]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): g for k, v in raw.items() if isinstance(v, dict) and (g := _parse_grades(v))}


def parse_relic_rank(raw: Any) -> RelicRank:
    if not isinstance(raw, dict):
        return RelicRank()
    return RelicRank(baseline=_parse_grades(raw.get("baseline")),
                     items=_parse_by_id(raw.get("items")),
                     owned=_parse_by_id(raw.get("owned")),
                     shelf_full=bool(raw.get("shelfFull")))


def _sort_key(r: RankedRelic) -> tuple:
    return (-r.reduction(PRIMARY_GRADE), -r.reduction(16), -r.reduction(8), r.id)


def rank_relics(rank: RelicRank | None, limit: int = TOP_COUNT) -> tuple[RankedRelic, ...]:
    """Relic giảm gãy nhiều nhất ở +12 (hòa thì +16 rồi +8); bỏ relic không giảm gãy."""
    if rank is None or not rank.baseline:
        return ()
    ranked = [RankedRelic(rid, rank.baseline, after) for rid, after in rank.items.items()]
    useful = [r for r in ranked if max(r.reduction(g) for g in RANK_GRADES) > ODDS_EPSILON]
    return tuple(sorted(useful, key=_sort_key)[:limit])


def top_offer(rank: RelicRank | None, offer_ids: list[str]) -> RankedRelic | None:
    """Món đang bán xếp hạng cao nhất trong top giảm gãy (None nếu không có)."""
    return next((r for r in rank_relics(rank) if r.id in offer_ids), None)


def _pct(before: SwordOdds, after: SwordOdds) -> str:
    return f"{before.destruction:.1%}->{after.destruction:.1%}"


def _deltas(r: RankedRelic) -> str:
    return " | ".join(_pct(r.before[g], r.after[g]) for g in RANK_GRADES
                      if g in r.before and g in r.after)


def _owned_lines(rank: RelicRank, names: dict[str, str]) -> list[Line]:
    base = rank.baseline.get(PRIMARY_GRADE)
    lines: list[Line] = []
    for rid, after in rank.owned.items():
        removed = after.get(PRIMARY_GRADE)
        if base is None or removed is None or removed.destruction - base.destruction <= ODDS_EPSILON:
            continue
        lines.append((f"  (đang có) {display_name(rid, names)}: bỏ đi gãy @+{PRIMARY_GRADE} "
                      f"{_pct(base, removed)}", DIM))
    return lines


def conditional_lines(names: dict[str, str]) -> list[Line]:
    text = ("Có điều kiện (không mô phỏng được): "
            + ", ".join(display_name(rid, names) for rid in CONDITIONAL_IDS))
    return [(f"  {row}", DIM) for row in textwrap.wrap(text, LINE_WIDTH)]


def relic_rank_lines(rank: RelicRank | None, names: dict[str, str],
                     offer_ids: list[str]) -> list[Line]:
    """Khung "Relic giảm gãy"; ★ = món đang bán. Rỗng khi chưa có mô phỏng (không LIVE)."""
    if rank is None or not rank.baseline:
        return []
    shelf = " - kệ đầy: phải bỏ 1 relic" if rank.shelf_full else ""
    lines: list[Line] = [(f"Relic giảm gãy (@+8/+12/+16, chỉ hiệu ứng cố định):{shelf}", TITLE)]
    for r in rank_relics(rank):
        offered = r.id in offer_ids
        star = "★ " if offered else ""
        lines.append((f"  {star}{display_name(r.id, names)}: gãy {_deltas(r)}",
                      GOOD if offered else NORMAL))
    return lines + _owned_lines(rank, names) + conditional_lines(names)


def star_step(rank: RelicRank | None, offer_ids: list[str], names: dict[str, str]) -> Line | None:
    """Bước "★ Mua <tên>: giảm gãy @+12 a%->b%" cho món đang bán nằm trong top giảm gãy."""
    best = top_offer(rank, offer_ids)
    if best is None or PRIMARY_GRADE not in best.after:
        return None
    shelf = " (kệ đầy: bỏ 1 relic)" if rank is not None and rank.shelf_full else ""
    return (f"★ Mua {display_name(best.id, names)}: giảm gãy @+{PRIMARY_GRADE} "
            f"{_pct(best.before[PRIMARY_GRADE], best.after[PRIMARY_GRADE])}{shelf}", GOOD)
