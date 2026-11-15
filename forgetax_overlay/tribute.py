"""Tình trạng cống nạp và gợi ý ưu tiên sống sót (đủ cống) hơn tối đa giá trị.

quota = "CỐNG PHẨM PHẢI NỘP" của vòng hiện tại (field GPT6ForgeRoom.quota),
delivered = giá trị đã nộp trong vòng, holdings = tổng giá trị kiếm còn trong tay.
"""
from __future__ import annotations

from dataclasses import dataclass

from .advisor import SwordOdds
from .save_reader import RunState, Sword
from .text_format import fmt_pct

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


MAX_EXACT_SWORDS = 12  # 2^12 tập con: duyệt hết vẫn nhanh


def choose_tribute(swords: list[Sword], need: float, ratios: dict[int, float]) -> list[Sword]:
    """Chọn kiếm nộp cống: đủ ``need`` và mất ít giá trị tương lai nhất.

    Mất mát của một kiếm = giá trị x ``ratios[serial]`` (Plan.ratio; kiếm đã xong = 1; thiếu
    -> 1). Hòa thì chọn nộp dư ít nhất, rồi ít kiếm nhất. Duyệt mọi tập con khi n <= 12;
    nhiều hơn thì tham lam (tỉ lệ tương lai thấp trước, giá trị nhỏ trước). Kết quả xếp theo
    giá trị tăng dần; rỗng nếu nộp hết vẫn chưa đủ.
    """
    if need <= 0 or sum(s.value for s in swords) < need:
        return []
    loss = [s.value * ratios.get(s.serial, 1.0) for s in swords]
    if len(swords) > MAX_EXACT_SWORDS:
        order = sorted(range(len(swords)), key=lambda i: (loss[i] / max(swords[i].value, 1),
                                                          swords[i].value))
        picked, total = [], 0.0
        for i in order:
            if total >= need:
                break
            picked.append(swords[i])
            total += swords[i].value
        return sorted(picked, key=lambda s: s.value)
    best_key, best_mask = None, 0
    for mask in range(1, 1 << len(swords)):
        members = [i for i in range(len(swords)) if mask >> i & 1]
        total = sum(swords[i].value for i in members)
        if total < need:
            continue
        key = (round(sum(loss[i] for i in members), 6), total - need, len(members))
        if best_key is None or key < best_key:
            best_key, best_mask = key, mask
    return sorted((s for i, s in enumerate(swords) if best_mask >> i & 1), key=lambda s: s.value)


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
            return f"DỪNG (đang đủ cống; đập thì {fmt_pct(1 - p_enough)} rủi ro thiếu)"
        return None
    if p_enough > 0:
        return f"ĐẬP (đang thiếu cống; {fmt_pct(p_enough)} đủ sau 1 nhát)"
    return None
