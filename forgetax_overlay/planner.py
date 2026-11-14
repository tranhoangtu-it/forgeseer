"""Kế hoạch đập nhiều nhát (quy hoạch động / dừng tối ưu) cho một thanh kiếm.

Trạng thái: (grade, tích lực Xuất Thần, số nhát còn xét). Mỗi nhát thường: dùng tỉ lệ của
game ở grade đó, tích lực +1. Khi tích lực đạt ngưỡng, nhát kế tiếp vào Xuất Thần: một đợt
FEVER_STRIKES nhát dùng tỉ lệ Xuất Thần (không gãy), sau đó tích lực về 0.

Giả định (ghi rõ vì chưa xác minh tuyệt đối):
- Ngưỡng 10 nhát lấy từ hướng dẫn trong game ("Rèn đủ mười nhát...").
- Xuất Thần tính theo thời gian; FEVER_STRIKES = số nhát trung bình người chơi đập kịp.
- Thành công +1 grade, Xuất sắc +2, Không đổi giữ nguyên, Hư tổn -1, Gãy mất trắng;
  giá trị mỗi grade x multiplier. Relic cộng thêm tích lực/giá trị chưa được tính.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .advisor import SwordOdds

FEVER_THRESHOLD = 10
FEVER_STRIKES = 4
HORIZON = 30          # số nhát (tính cả đợt Xuất Thần là 1 bước) tối đa được xét
EPSILON = 1e-9

GradeOdds = dict[int, SwordOdds]


@dataclass(frozen=True)
class Plan:
    ratio: float            # giá trị kỳ vọng khi chơi tối ưu / giá trị hiện tại
    verdict: str            # "ĐẬP" hoặc "DỪNG"
    strikes_to_fever: int   # số nhát thường nữa thì vào Xuất Thần


def _transitions(o: SwordOdds, g: int) -> list[tuple[float, int]]:
    """Các kết quả còn giữ kiếm: (xác suất, grade mới). Gãy -> mất (không có trong danh sách)."""
    return [(o.success, g + 1), (o.great, g + 2), (o.hold, g), (o.damage, max(g - 1, 0))]


def plan_sword(grade: int, charge: int, normal: GradeOdds, fever: GradeOdds,
               multiplier: float, horizon: int = HORIZON) -> Plan | None:
    if grade not in normal:
        return None

    def rel(g: int) -> float:
        return multiplier ** (g - grade)

    def fever_burst(g: int) -> dict[int, float]:
        dist = {g: 1.0}
        for _ in range(FEVER_STRIKES):
            nxt: dict[int, float] = {}
            for gg, p in dist.items():
                o = fever.get(gg)
                if o is None:  # ngoài bảng tỉ lệ: coi như giữ nguyên
                    nxt[gg] = nxt.get(gg, 0.0) + p
                    continue
                for q, g2 in _transitions(o, gg):
                    nxt[g2] = nxt.get(g2, 0.0) + p * q
            dist = nxt
        return dist

    @lru_cache(maxsize=None)
    def best(g: int, c: int, h: int) -> float:
        stop = rel(g)
        if h == 0 or g not in normal:
            return stop
        return max(stop, strike(g, c, h))

    @lru_cache(maxsize=None)
    def strike(g: int, c: int, h: int) -> float:
        if c >= FEVER_THRESHOLD:
            return sum(p * best(g2, 0, h - 1) for g2, p in fever_burst(g).items())
        return sum(q * best(g2, c + 1, h - 1) for q, g2 in _transitions(normal[g], g))

    c0 = min(max(charge, 0), FEVER_THRESHOLD)
    value = best(grade, c0, horizon)
    verdict = "ĐẬP" if strike(grade, c0, horizon) > 1.0 + EPSILON else "DỪNG"
    return Plan(ratio=value, verdict=verdict, strikes_to_fever=FEVER_THRESHOLD - c0)
