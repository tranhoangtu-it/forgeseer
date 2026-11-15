"""Gợi ý mua hàng của Thương nhân ma (ghé mỗi 3 ngày, bán kiếm và vật phẩm tiêu hao).

Mỗi món được quy ra "giá trị" (G) để so với giá:
- Kiếm Sắt / kiếm đặc biệt: giá trị gốc x kỳ vọng khi rèn tối ưu (kế hoạch nhiều nhát).
- Vảy Rồng Nứt (ward): dùng TRƯỚC nhát rủi ro -> cứu = giá trị kiếm quý nhất x tỉ lệ gãy.
- Dây Cót Hối Tiếc (rewind): dùng SAU khi kiếm quý bị gãy để hồi lại -> bảo hiểm tối đa
  bằng giá trị kiếm quý nhất (chỉ có ý nghĩa khi kiếm đó còn rủi ro gãy).
Vàng chỉ dùng để mua sắm, còn cống nạp bằng kiếm -> đổi vàng thành kiếm có lời là ưu tiên.
"""
from __future__ import annotations

from dataclasses import dataclass

from .advisor import GradeOddsTable, SwordOdds
from .fever_calibration import DEFAULT_FEVER_STRIKES
from .planner import plan_sword
from .save_reader import MerchantOffer, RunState
from .shop_advice import target_sword
from .text_format import fmt_int, fmt_pct

BASE_SWORD_VALUE = 320.0   # ForgeEnhancementBalance.baseValue
SWORD_IDS = {"sword", "worldtree"}
BUY_RATIO = 1.5            # giá trị >= 1.5 lần giá -> MUA
CONSIDER_RATIO = 1.0
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]


@dataclass(frozen=True)
class MerchantItem:
    offer: MerchantOffer
    worth: float | None
    note: str
    verdict: str
    best: bool = False

    @property
    def ratio(self) -> float | None:
        return None if self.worth is None or self.offer.price <= 0 else self.worth / self.offer.price


def merchant_active(state: RunState) -> bool:
    return (state.merchant_round == state.round and state.round > 0
            and any(not o.sold for o in state.merchant_offers))


def _worth(offer: MerchantOffer, state: RunState, odds: OddsMap, multiplier: float,
           table: GradeOddsTable | None, fever_strikes: int) -> tuple[float | None, str]:
    top = target_sword(state.swords, odds)
    if offer.id in SWORD_IDS:
        base = BASE_SWORD_VALUE * multiplier ** offer.grade
        plan = (plan_sword(offer.grade, 0, table.normal, table.fever, multiplier, fever_strikes)
                if table is not None and table.valid else None)
        if plan is None:
            return base, f"giá trị gốc {fmt_int(base)}"
        return base * plan.ratio, f"kỳ vọng ~{fmt_int(base * plan.ratio)} nếu rèn tối ưu"
    if offer.id == "ward" and top is not None:
        p = odds[top.serial][0].destruction
        return top.value * p, f"cứu ~{fmt_int(top.value * p)} cho kiếm {top.tag} (Gãy {fmt_pct(p)} mỗi nhát)"
    if offer.id == "rewind" and top is not None:
        if odds[top.serial][0].destruction <= 0:
            return 0.0, f"kiếm {top.tag} chưa có rủi ro Gãy"
        return float(top.value), f"bảo hiểm tới {fmt_int(top.value)} cho kiếm {top.tag} (dùng sau khi gãy)"
    return None, ""


def _verdict(worth: float | None, price: float, wallet: int) -> str:
    if price > wallet:
        return "thiếu vàng"
    if worth is None:
        return "xem mô tả"
    ratio = worth / price if price > 0 else float("inf")
    if ratio >= BUY_RATIO:
        return "MUA"
    return "cân nhắc" if ratio >= CONSIDER_RATIO else "bỏ qua"


def evaluate_merchant(state: RunState, odds: OddsMap, multiplier: float,
                      table: GradeOddsTable | None,
                      fever_strikes: int = DEFAULT_FEVER_STRIKES) -> list[MerchantItem]:
    items = []
    for offer in state.merchant_offers:
        if offer.sold:
            continue
        worth, note = _worth(offer, state, odds, multiplier, table, fever_strikes)
        items.append(MerchantItem(offer, worth, note, _verdict(worth, offer.price, state.wallet)))
    buyable = [i for i in items if i.verdict == "MUA" and i.ratio is not None]
    if buyable:
        best = max(buyable, key=lambda i: i.ratio)
        items = [MerchantItem(i.offer, i.worth, i.note, i.verdict, best=i is best) for i in items]
    return items
