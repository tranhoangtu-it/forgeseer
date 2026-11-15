"""Chuyển RunState thành các dòng hiển thị (text, tag màu). Hàm thuần, không phụ thuộc UI.

Các phần cách nhau một dòng trống; dòng dài được tách thành dòng chính + dòng phụ thụt vào.
"""
from __future__ import annotations

from dataclasses import dataclass

from .action_plan import MERCHANT_SWORD_NAMES, offered_ids
from .advisor import GradeOddsTable, ShopSimulation, SwordOdds
from .fever_calibration import DEFAULT_FEVER_STRIKES
from .merchant_advice import MerchantItem
from .relic_names import display_name
from .relic_rank import RelicRank, rank_relics, relic_rank_lines
from .save_reader import RunState, Sword
from .shop_advice import best_drop, buy_line, drop_line, grade_line, target_sword
from .sword_section import sword_lines, tribute_lines
from .text_format import SEP, fmt_int, fmt_ratio, wrap_lines

# Tag màu dùng chung với overlay.py
TITLE, NORMAL, GOOD, WARN, DIM = "title", "normal", "good", "warn", "dim"

Line = tuple[str, str]
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]  # serial -> (bình thường, fever)

DESCRIPTION_WIDTH = 64  # số ký tự mỗi dòng mô tả di vật trong cửa hàng


def format_state(state: RunState | None, names: dict[str, str] | None = None,
                 odds: OddsMap | None = None, multiplier: float = 1.5,
                 descriptions: dict[str, str] | None = None,
                 shop_sim: ShopSimulation | None = None,
                 quota: float = 0.0,
                 grade_odds: GradeOddsTable | None = None,
                 merchant: list[MerchantItem] | None = None,
                 fever_strikes: int = DEFAULT_FEVER_STRIKES,
                 next_quota: float = 0.0, runs_summary: str = "",
                 relic_rank: RelicRank | None = None,
                 schedule: tuple[float, ...] = ()) -> list[Line]:
    """``names``: id di vật -> tên; ``odds``/``shop_sim``/``quota``/``grade_odds``/``relic_rank``/
    ``schedule``: chỉ có khi đọc trực tiếp từ game."""
    if state is None:
        return [("ForgeTax", TITLE), ("Chưa có lượt chơi nào được lưu.", DIM)]
    names = names or {}
    odds = odds or {}
    ctx = _AdviceContext(target_sword(state.swords, odds), odds,
                         shop_sim or ShopSimulation(), multiplier, names)
    sections: list[list[Line]] = [
        [("ForgeTax", TITLE)] + _campaign_lines(state),
        tribute_lines(state, quota, next_quota, schedule, grade_odds, multiplier, fever_strikes),
        sword_lines(state, odds, multiplier, quota, grade_odds, fever_strikes),
        _relic_lines(state, names, ctx),
        relic_rank_lines(relic_rank, names, offered_ids(state, merchant)),
    ]
    if state.shopping:
        sections.append(_shop_lines(state, names, descriptions or {}, ctx))
    if merchant:
        starred = {r.id for r in rank_relics(relic_rank)}
        sections.append(_merchant_lines(merchant, names, starred))
    sections.append(_stats_lines(state, fever_strikes)
                    + ([(runs_summary, DIM)] if runs_summary else []))
    return wrap_lines(join_sections(sections))


def join_sections(sections: list[list[Line]]) -> list[Line]:
    """Nối các phần, mỗi phần cách nhau một dòng trống; bỏ phần rỗng."""
    lines: list[Line] = []
    for section in sections:
        if not section:
            continue
        if lines:
            lines.append(("", NORMAL))
        lines += section
    return lines


def _merchant_lines(items: list[MerchantItem], names: dict[str, str],
                    starred: set[str]) -> list[Line]:
    """``starred``: id nằm trong top di vật giảm gãy -> thêm "★"."""
    lines: list[Line] = [("Thương nhân ma:", TITLE)]
    for item in items:
        name = MERCHANT_SWORD_NAMES.get(item.offer.id) or display_name(item.offer.id, names)
        if item.offer.id in starred and not item.offer.sold:
            name = f"★ {name}"
        ratio = f" (đáng {fmt_ratio(item.ratio, 1)} giá)" if item.ratio is not None else ""
        mark = f"{SEP}← mua trước" if item.best else ""
        tag = GOOD if item.verdict == "MUA" else WARN if item.verdict == "thiếu vàng" else DIM
        lines.append((f"  {name}{SEP}giá {fmt_int(item.offer.price)} G → {item.verdict}"
                      f"{ratio}{mark}", tag))
        if item.note:
            lines.append((f"      {item.note}", DIM))
    return lines


def _campaign_lines(s: RunState) -> list[Line]:
    rounds_left = max(s.deadline_round - s.round, 0)
    lines: list[Line] = [
        (f"Ngày {s.round}/{s.deadline_round} (còn {rounds_left} ngày){SEP}Vàng: {fmt_int(s.wallet)}",
         GOOD),
    ]
    if s.pending_tribute > 0:
        lines.append((f"Cống đang chờ: {fmt_int(s.pending_tribute)}", NORMAL))
        if s.pending_tribute > s.wallet:
            lines.append((f"Thiếu {fmt_int(s.pending_tribute - s.wallet)} vàng để nộp cống!", WARN))
    lines.append((f"Cống đã nộp đủ: {s.successful_tributes} lần{SEP}Lỡ: {s.missed_tributes}",
                  WARN if s.missed_tributes else NORMAL))
    lines.append((f"Vảy Rồng: {s.ward_charges}{SEP}Dây Cót: {s.rewind_charges}{SEP}"
                  f"Lượt mua di vật: {s.sword_credits}{SEP}Lượt đổi hàng: {s.rerolls}", NORMAL))
    if s.consumables:
        lines.append((f"Vật phẩm tiêu hao: {s.consumables}", NORMAL))
    if s.finished:
        lines.append(("Kết thúc: THẮNG" if s.won else "Kết thúc: THUA", GOOD if s.won else WARN))
    return lines


@dataclass(frozen=True)
class _AdviceContext:
    """Dữ liệu dùng chung cho gợi ý mua/bỏ/đổi di vật (so trên kiếm giá trị nhất)."""
    target: Sword | None
    odds: OddsMap
    sim: ShopSimulation
    multiplier: float
    names: dict[str, str]


def _relic_lines(s: RunState, names: dict[str, str], ctx: _AdviceContext) -> list[Line]:
    if not s.relics:
        return []
    lines: list[Line] = [(f"Di vật đang có ({len(s.relics)}):", TITLE)]
    best = best_drop(ctx.target, ctx.odds, ctx.sim, ctx.multiplier)
    for r in s.relics:
        rank = f" (bậc {r.rank})" if r.rank > 1 else ""
        lines.append((f"  {display_name(r.id, names)}{rank}", NORMAL))
        advice = drop_line(r.id, ctx.target, ctx.odds, ctx.sim, ctx.multiplier, best)
        if advice is not None:
            lines.append(advice)
    return lines


def _wrap(text: str, width: int = DESCRIPTION_WIDTH) -> list[str]:
    words, rows, row = text.split(), [], ""
    for w in words:
        if row and len(row) + 1 + len(w) > width:
            rows.append(row)
            row = w
        else:
            row = f"{row} {w}" if row else w
    return rows + ([row] if row else [])


def _shop_lines(s: RunState, names: dict[str, str], descriptions: dict[str, str],
                ctx: _AdviceContext) -> list[Line]:
    lines: list[Line] = [("Cửa hàng di vật:", TITLE)]
    for o in s.offers:
        status = " (đã mua)" if o.sold else ""
        lines.append((f"  {display_name(o.id, names)}{SEP}giá {fmt_int(o.price)}{status}",
                      DIM if o.sold else GOOD))
        if not o.sold:
            lines += [(f"      {row}", DIM) for row in _wrap(descriptions.get(o.id, ""))]
            effect = buy_line(o.id, ctx.target, ctx.odds, ctx.sim, ctx.multiplier, ctx.names)
            if effect is not None:
                lines.append(effect)
            by_grade = grade_line(o.id, ctx.target, ctx.sim, ctx.multiplier)
            if by_grade is not None:
                lines.append(by_grade)
    return lines


def _stats_lines(s: RunState, fever_strikes: int) -> list[Line]:
    minutes, seconds = divmod(int(s.play_seconds), 60)
    return [
        ("Thống kê lượt này:", TITLE),
        (f"  Xuất sắc {s.great_events}{SEP}Không đổi {s.hold_events}{SEP}"
         f"Hư tổn {s.damage_events}{SEP}Xuất Thần {s.fever_events}{SEP}Gãy {s.broken_swords}", DIM),
        (f"  Tổng vàng {fmt_int(s.gold_earned)}{SEP}cấp cao nhất +{s.highest_grade}"
         f"{SEP}thời gian {minutes}:{seconds:02d}", DIM),
        (f"  Xuất Thần: ~{fever_strikes} nhát/lần", DIM),
    ]
