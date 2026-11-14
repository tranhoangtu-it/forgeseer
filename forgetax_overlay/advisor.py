"""Gợi ý có nên đập tiếp hay dừng, dựa trên tỉ lệ thật của game cho nhát kế tiếp.

Tỉ lệ lấy từ hàm tính tỉ lệ của chính game (đã gồm relic), đơn vị phần nghìn, thứ tự:
gãy / hỏng / giữ nguyên / thành công / đại thành công.

Mô hình giá trị (đối chiếu với giá trị kiếm thực tế, mỗi grade x gradeMultiplier):
thành công +1 grade, đại thành công +2 grade, giữ nguyên, hỏng -1 grade, gãy mất trắng.
Kỳ vọng tính theo một nhát (trung lập rủi ro); bỏ qua hiệu ứng phụ của relic khi đập.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

PERMILLE = 1000.0


@dataclass(frozen=True)
class SwordOdds:
    destruction: float
    damage: float
    hold: float
    success: float
    great: float

    @classmethod
    def from_permille(cls, values: Sequence[float]) -> "SwordOdds":
        d, dm, h, s, g = (float(v) / PERMILLE for v in values)
        return cls(destruction=d, damage=dm, hold=h, success=s, great=g)


PerSword = dict[int, SwordOdds]  # serial kiếm -> tỉ lệ


@dataclass(frozen=True)
class ShopSimulation:
    """Tỉ lệ mô phỏng bằng hàm của game cho các phương án với relic."""
    buy: dict[str, PerSword] = field(default_factory=dict)             # mua món (kệ còn chỗ)
    drop: dict[str, PerSword] = field(default_factory=dict)            # bỏ relic đang có
    swap: dict[str, dict[str, PerSword]] = field(default_factory=dict)  # mua món X thay relic Y (kệ đầy)


@dataclass(frozen=True)
class GradeOddsTable:
    """Tỉ lệ của game theo từng grade (cho kế hoạch nhiều nhát).

    valid=False khi hàm tỉ lệ theo grade không khớp tỉ lệ thật của kiếm -> không dùng.
    """
    normal: dict[int, SwordOdds] = field(default_factory=dict)
    fever: dict[int, SwordOdds] = field(default_factory=dict)
    valid: bool = False


@dataclass(frozen=True)
class Advice:
    ev_ratio: float  # giá trị kỳ vọng sau 1 nhát / giá trị hiện tại
    verdict: str


def advise(odds: SwordOdds, multiplier: float) -> Advice:
    ev = (odds.success * multiplier
          + odds.great * multiplier ** 2
          + odds.hold
          + odds.damage / multiplier)
    if ev <= 1.0:
        verdict = "DỪNG"
    elif odds.destruction <= 0.0:
        verdict = "ĐẬP (an toàn)"
    else:
        verdict = "ĐẬP"
    return Advice(ev_ratio=ev, verdict=verdict)
