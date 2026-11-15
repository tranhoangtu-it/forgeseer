"""Chuyển RunState thành các dòng hiển thị (text, tag màu). Hàm thuần, không phụ thuộc UI.

Các phần cách nhau một dòng trống; dòng dài được tách thành dòng chính + dòng phụ thụt vào.
"""
from __future__ import annotations

from dataclasses import dataclass

from .action_plan import merchant_name, offered_ids
from .advisor import GradeOddsTable, ShopSimulation, SwordOdds
from .fever_calibration import DEFAULT_FEVER_STRIKES
from .i18n import t
from .merchant_advice import MerchantItem
from .relic_names import display_name
from .relic_rank import RelicRank, rank_relics, relic_rank_lines
from .save_reader import RunState, Sword
from .shop_advice import best_drop, buy_line, drop_line, grade_line, target_sword
from .sword_section import sword_lines, tribute_lines
from .text_format import LOW, SEP, fmt_int, fmt_ratio, low, plain, wrap_lines

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
                 schedule: tuple[float, ...] = (), keep_priority: bool = False) -> list[Line]:
    """``names``: id di vật -> tên; ``odds``/``shop_sim``/``quota``/``grade_odds``/``relic_rank``/
    ``schedule``: chỉ có khi đọc trực tiếp từ game. ``keep_priority``: giữ phần tử thứ ba LOW
    của dòng ưu tiên thấp (overlay dùng để co khung cho vừa màn hình)."""
    if state is None:
        return [("ForgeTax", TITLE), (t("state.no_run"), DIM)]
    names = names or {}
    odds = odds or {}
    ctx = _AdviceContext(target_sword(state.swords, odds), odds,
                         shop_sim or ShopSimulation(), multiplier, names)
    sections: list[list[Line]] = [
        [("ForgeTax", TITLE)] + _campaign_lines(state),
        tribute_lines(state, quota, next_quota, schedule, grade_odds, multiplier, fever_strikes),
        sword_lines(state, odds, multiplier, quota, grade_odds, fever_strikes),
        _relic_lines(state, names, ctx),
        low(relic_rank_lines(relic_rank, names, offered_ids(state, merchant))),
    ]
    if state.shopping:
        sections.append(_shop_lines(state, names, descriptions or {}, ctx))
    if merchant:
        starred = {r.id for r in rank_relics(relic_rank)}
        sections.append(_merchant_lines(merchant, names, starred))
    sections.append(low(_stats_lines(state, fever_strikes)
                        + ([(runs_summary, DIM)] if runs_summary else [])))
    lines = wrap_lines(join_sections(sections))
    return lines if keep_priority else plain(lines)


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
    lines: list[Line] = [(t("merchant.title"), TITLE)]
    for item in items:
        name = merchant_name(item.offer.id, names)
        if item.offer.id in starred and not item.offer.sold:
            name = f"★ {name}"
        ratio = t("merchant.worth", ratio=fmt_ratio(item.ratio, 1)) if item.ratio is not None else ""
        mark = SEP + t("merchant.buy_first") if item.best else ""
        tag = (GOOD if item.verdict == t("merchant.buy")
               else WARN if item.verdict == t("merchant.no_gold") else DIM)
        lines.append((f"  {name}{SEP}" + t("merchant.price", price=fmt_int(item.offer.price))
                      + f" → {item.verdict}{ratio}{mark}", tag))
        if item.note:
            lines.append((f"      {item.note}", DIM))
    return lines


def _campaign_lines(s: RunState) -> list[Line]:
    rounds_left = max(s.deadline_round - s.round, 0)
    lines: list[Line] = [
        (t("campaign.day", day=s.round, deadline=s.deadline_round, left=rounds_left) + SEP
         + t("campaign.gold", gold=fmt_int(s.wallet)), GOOD),
    ]
    if s.pending_tribute > 0:
        lines.append((t("campaign.pending", value=fmt_int(s.pending_tribute)), NORMAL))
        if s.pending_tribute > s.wallet:
            lines.append((t("campaign.pending_short", gold=fmt_int(s.pending_tribute - s.wallet)),
                          WARN))
    lines.append((t("campaign.tributes", done=s.successful_tributes) + SEP
                  + t("campaign.missed", count=s.missed_tributes),
                  WARN if s.missed_tributes else NORMAL))
    lines.append((SEP.join((t("campaign.ward", count=s.ward_charges),
                            t("campaign.rewind", count=s.rewind_charges),
                            t("campaign.credits", count=s.sword_credits),
                            t("campaign.rerolls", count=s.rerolls))), NORMAL))
    if s.consumables:
        lines.append((t("campaign.consumables", count=s.consumables), NORMAL))
    if s.finished:
        lines.append((t("campaign.won") if s.won else t("campaign.lost"), GOOD if s.won else WARN))
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
    lines: list[Line] = [(t("relics.title", count=len(s.relics)), TITLE)]
    best = best_drop(ctx.target, ctx.odds, ctx.sim, ctx.multiplier)
    for r in s.relics:
        rank = t("relics.rank", rank=r.rank) if r.rank > 1 else ""
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
    lines: list[Line] = [(t("shop.title"), TITLE)]
    for o in s.offers:
        status = t("shop.sold") if o.sold else ""
        lines.append((f"  {display_name(o.id, names)}{SEP}"
                      + t("shop.price", price=fmt_int(o.price)) + status,
                      DIM if o.sold else GOOD))
        if not o.sold:
            lines += [(f"      {row}", DIM, LOW) for row in _wrap(descriptions.get(o.id, ""))]
            effect = buy_line(o.id, ctx.target, ctx.odds, ctx.sim, ctx.multiplier, ctx.names)
            if effect is not None:
                lines.append(effect)
            by_grade = grade_line(o.id, ctx.target, ctx.sim, ctx.multiplier)
            if by_grade is not None:
                lines.append(by_grade)
    return lines


def _stats_lines(s: RunState, fever_strikes: int) -> list[Line]:
    minutes, seconds = divmod(int(s.play_seconds), 60)
    events = ((t("outcome.great"), s.great_events), (t("outcome.hold"), s.hold_events),
              (t("outcome.damage"), s.damage_events), (t("word.fever"), s.fever_events),
              (t("outcome.break"), s.broken_swords))
    return [
        (t("stats.title"), TITLE),
        ("  " + SEP.join(f"{name} {count}" for name, count in events), DIM),
        ("  " + SEP.join((t("stats.gold", gold=fmt_int(s.gold_earned)),
                          t("stats.best_grade", grade=s.highest_grade),
                          t("stats.time", time=f"{minutes}:{seconds:02d}"))), DIM),
        ("  " + t("stats.fever", count=fever_strikes), DIM),
    ]
