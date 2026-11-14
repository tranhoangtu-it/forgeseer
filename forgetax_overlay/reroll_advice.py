"""Gợi ý đổi lượt (reroll) máy relic.

Giá đổi lượt đọc từ chữ hiển thị trên máy relic (``ForgeRelicVending.rerollText``):
"390 G" hoặc "1 LẦN MIỄN PHÍ" (khóa ngôn ngữ ``rework.free_reroll``).
Chỉ khuyên đổi khi không món nào làm tăng EV và: được miễn phí, hoặc vàng dư nhiều
(vàng còn dùng mua hàng Thương nhân ma nên ngưỡng để thận trọng).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

GOOD, DIM = "good", "dim"
Line = tuple[str, str]
FREE_MARKERS = ("MIỄN PHÍ", "FREE")
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
        return "Máy relic: không món nào tăng EV -> đổi lượt (miễn phí)", GOOD
    if cost.price > 0 and wallet >= cost.price * PLENTIFUL_GOLD_FACTOR:
        return f"Máy relic: không món nào tăng EV -> đổi lượt ({cost.price:,} G, vàng dư)", DIM
    return None
