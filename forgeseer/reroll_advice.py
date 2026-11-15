"""Gợi ý đổi lượt (reroll) máy relic.

Giá đổi lượt đọc từ chữ hiển thị trên máy relic (``ForgeRelicVending.rerollText``):
"390 G" hoặc "1 LẦN MIỄN PHÍ" (khóa ngôn ngữ ``rework.free_reroll``).
Chỉ khuyên đổi khi không món nào làm tăng EV và: được miễn phí, hoặc vàng dư nhiều
(vàng còn dùng mua hàng Thương nhân ma nên ngưỡng để thận trọng).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .i18n import t
from .text_format import fmt_int

GOOD, DIM = "good", "dim"
Line = tuple[str, str]
# Chữ "miễn phí" trên máy relic ở mọi ngôn ngữ của game (khóa rework.free_reroll).
FREE_MARKERS = ("MIỄN PHÍ", "FREE", "KOSTENLOS", "GRATIS", "GRÁTIS", "無料", "免费", "免費",
                "БЕСПЛАТНО", "무료")
PLENTIFUL_GOLD_FACTOR = 10  # ví >= 10 lần giá đổi lượt -> coi là dư vàng
_PRICE = re.compile(r"(\d[\d,.]*)\s*G\b")


@dataclass(frozen=True)
class RerollCost:
    free: bool
    price: int


def parse_reroll_text(text: str) -> RerollCost | None:
    if any(marker in text.upper() for marker in FREE_MARKERS):
        return RerollCost(free=True, price=0)
    match = _PRICE.search(text)
    if match is None:
        return None
    return RerollCost(free=False, price=int(re.sub(r"[,.]", "", match.group(1))))


def reroll_line(cost: RerollCost | None, wallet: int, has_good_offer: bool) -> Line | None:
    if cost is None or has_good_offer:
        return None
    if cost.free:
        return t("reroll.free"), GOOD
    if cost.price > 0 and wallet >= cost.price * PLENTIFUL_GOLD_FACTOR:
        return t("reroll.paid", price=fmt_int(cost.price)), DIM
    return None
