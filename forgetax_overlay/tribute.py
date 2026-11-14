"""Tình trạng cống nạp và gợi ý ưu tiên sống sót (đủ cống) hơn tối đa giá trị.

quota = "CỐNG PHẨM PHẢI NỘP" của vòng hiện tại (field GPT6ForgeRoom.quota),
delivered = giá trị đã nộp trong vòng, holdings = tổng giá trị kiếm còn trong tay.
"""
from __future__ import annotations

from dataclasses import dataclass

from .advisor import SwordOdds
from .save_reader import RunState, Sword

EPSILON = 1e-9


@dataclass(frozen=True)
class TributeStatus:
    quota: float
    delivered: float
    holdings: float

    @property
    def need(self) -> float:
        """Còn phải nộp thêm bao nhiêu trong vòng này."""
        return max(self.quota - self.delivered, 0.0)

    @property
    def shortfall(self) -> float:
        """Nộp hết kiếm đang có thì vẫn thiếu bao nhiêu."""
        return max(self.need - self.holdings, 0.0)


def tribute_status(state: RunState, quota: float) -> TributeStatus | None:
    if quota <= 0:
        return None
    holdings = sum(sw.value for sw in state.swords if sw.is_live)
    return TributeStatus(quota=quota, delivered=float(state.delivered), holdings=float(holdings))


def tribute_override(sword: Sword, odds: SwordOdds, status: TributeStatus | None,
                     multiplier: float) -> str | None:
    """Gợi ý theo cống cho thanh kiếm; None nếu cống không làm đổi quyết định."""
    if status is None or status.need <= 0:
        return None
    others = status.holdings - sword.value
    outcomes = [(odds.success, multiplier), (odds.great, multiplier ** 2), (odds.hold, 1.0),
                (odds.damage, 1.0 / multiplier), (odds.destruction, 0.0)]
    p_enough = sum(p for p, factor in outcomes if others + sword.value * factor >= status.need)
    if others + sword.value >= status.need:
        if p_enough < 1.0 - EPSILON:
            return f"DỪNG (đang đủ cống; đập có {1 - p_enough:.0%} rủi ro thiếu)"
        return None
    if p_enough > 0:
        return f"ĐẬP (thiếu cống; 1 nhát đủ cống: {p_enough:.0%})"
    return None
