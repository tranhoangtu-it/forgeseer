"""Chuyển RunState thành các dòng hiển thị (text, tag màu). Hàm thuần, không phụ thuộc UI."""
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

# Tag màu dùng chung với overlay.py
TITLE, NORMAL, GOOD, WARN, DIM = "title", "normal", "good", "warn", "dim"

Line = tuple[str, str]
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]  # serial -> (bình thường, fever)

DESCRIPTION_WIDTH = 64  # số ký tự mỗi dòng mô tả relic trong shop


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
    """``names``: id relic -> tên; ``odds``/``shop_sim``/``quota``/``grade_odds``/``relic_rank``/
    ``schedule``: chỉ có khi LIVE."""
    if state is None:
        return [("ForgeTax", TITLE), ("Chưa có lượt chơi nào được lưu.", DIM)]
    names = names or {}
    odds = odds or {}
    lines: list[Line] = [("ForgeTax", TITLE)]
    lines += _campaign_lines(state)
    lines += tribute_lines(state, quota, next_quota, schedule, grade_odds, multiplier,
                           fever_strikes)
    lines += sword_lines(state, odds, multiplier, quota, grade_odds, fever_strikes)
    ctx = _AdviceContext(target_sword(state.swords, odds), odds,
                         shop_sim or ShopSimulation(), multiplier, names)
    lines += _relic_lines(state, names, ctx)
    on_sale = offered_ids(state, merchant)
    lines += relic_rank_lines(relic_rank, names, on_sale)
    if state.shopping:
        lines += _shop_lines(state, names, descriptions or {}, ctx)
    if merchant:
        starred = {r.id for r in rank_relics(relic_rank)}
        lines += _merchant_lines(merchant, names, starred)
    lines += _stats_lines(state, fever_strikes)
    if runs_summary:
        lines.append((runs_summary, DIM))
    return lines


def _merchant_lines(items: list[MerchantItem], names: dict[str, str],
                    starred: set[str]) -> list[Line]:
    """``starred``: id nằm trong top relic giảm gãy -> thêm "★"."""
    lines: list[Line] = [("Thương nhân ma:", TITLE)]
    for item in items:
        name = MERCHANT_SWORD_NAMES.get(item.offer.id) or display_name(item.offer.id, names)
        if item.offer.id in starred and not item.offer.sold:
            name = f"★ {name}"
        ratio = f" x{item.ratio:.1f}" if item.ratio is not None else ""
        mark = "  <- mua trước" if item.best else ""
        note = f" ({item.note})" if item.note else ""
        tag = GOOD if item.verdict == "MUA" else WARN if item.verdict == "thiếu vàng" else DIM
        lines.append((f"  {name} - {item.offer.price:,.0f}: {item.verdict}{ratio}{note}{mark}", tag))
    return lines


def _campaign_lines(s: RunState) -> list[Line]:
    rounds_left = max(s.deadline_round - s.round, 0)
    lines: list[Line] = [
        (f"Vòng {s.round}/{s.deadline_round} (còn {rounds_left}) | Vàng: {s.wallet:,}", GOOD),
    ]
    if s.pending_tribute > 0:
        lines.append((f"Cống chờ: {s.pending_tribute:,}", NORMAL))
        if s.pending_tribute > s.wallet:
            lines.append((f"Thiếu {s.pending_tribute - s.wallet:,} vàng để nộp cống!", WARN))
    lines.append((f"Cống OK {s.successful_tributes} | lỡ {s.missed_tributes} | "
                  f"Ward {s.ward_charges} | Credit {s.sword_credits} | "
                  f"Reroll {s.rerolls} | Rewind {s.rewind_charges}",
                  WARN if s.missed_tributes else NORMAL))
    if s.consumables:
        lines.append((f"Tiêu hao {s.consumables}", NORMAL))
    if s.finished:
        lines.append(("THẮNG" if s.won else "THUA", GOOD if s.won else WARN))
    return lines


@dataclass(frozen=True)
class _AdviceContext:
    """Dữ liệu dùng chung cho gợi ý mua/bỏ/đổi relic (so trên kiếm giá trị nhất)."""
    target: Sword | None
    odds: OddsMap
    sim: ShopSimulation
    multiplier: float
    names: dict[str, str]


def _relic_lines(s: RunState, names: dict[str, str], ctx: _AdviceContext) -> list[Line]:
    if not s.relics:
        return []
    lines: list[Line] = [(f"Relic ({len(s.relics)}):", TITLE)]
    best = best_drop(ctx.target, ctx.odds, ctx.sim, ctx.multiplier)
    for r in s.relics:
        rank = f" r{r.rank}" if r.rank > 1 else ""
        name = f"  {display_name(r.id, names)}{rank}"
        advice = drop_line(r.id, ctx.target, ctx.odds, ctx.sim, ctx.multiplier, best)
        if advice is None:
            lines.append((name, NORMAL))
        else:  # gợi ý bỏ nằm cùng dòng với tên cho gọn
            text, tag = advice
            lines.append((f"{name}  · {text.strip()}", tag))
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
    lines: list[Line] = [("Shop:", TITLE)]
    for o in s.offers:
        status = " (đã mua)" if o.sold else ""
        lines.append((f"  {display_name(o.id, names)} - {o.price}{status}",
                      DIM if o.sold else GOOD))
        if not o.sold:
            lines += [(f"     {row}", DIM) for row in _wrap(descriptions.get(o.id, ""))]
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
        (f"Great {s.great_events} | Hold {s.hold_events} | Damage {s.damage_events} | "
         f"Fever {s.fever_events} | Gãy {s.broken_swords} | Tổng vàng {s.gold_earned:,} | "
         f"G max {s.highest_grade} | {minutes}:{seconds:02d} | XT ~{fever_strikes} nhát", DIM),
    ]
