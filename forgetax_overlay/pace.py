"""Tiến độ khế ước: giá trị kỳ vọng của kiếm đang giữ so với cống của vài ngày tới.

Giá trị kỳ vọng mỗi kiếm = giá trị x ``Plan.ratio`` (kế hoạch DP với bảng tỉ lệ theo grade của
game; không có bảng -> chỉ tính giá trị hiện tại). Cộng thêm ước lượng kiếm mới mỗi ngày:
``FRESH_SWORDS_PER_DAY`` kiếm +0 (giá trị ``FRESH_SWORD_VALUE``) x tỉ lệ kế hoạch của kiếm +0.
Đây là ước lượng trung bình, không đoán kết quả từng nhát.

Giả định (chưa xác minh): mỗi ngày nhận ``FRESH_SWORDS_PER_DAY`` kiếm +0 mới.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .advisor import GradeOddsTable, SwordOdds
from .fever_calibration import DEFAULT_FEVER_STRIKES
from .planner import EPSILON, Plan, plan_sword
from .save_reader import Sword

GOOD, WARN, DIM = "good", "warn", "dim"
Line = tuple[str, str]

FRESH_SWORD_VALUE = 320.0       # ForgeEnhancementBalance.baseValue (giá trị kiếm +0)
FRESH_SWORDS_PER_DAY = 3        # giả định: số kiếm +0 mới mỗi ngày
PACE_DAYS = 3                   # số ngày tới dùng để so tiến độ
COMFORT_MARGIN = 1.5            # dư >= 1.5 lần nhu cầu -> "dư tiến độ"
RISKY_DESTRUCTION = 0.10        # tỉ lệ gãy từ mức này coi là nhát mạo hiểm
MAX_SCHEDULE_SHOWN = 6


def compact(value: float) -> str:
    """290000 -> "290k", 1280000 -> "1.28M", 1800 -> "1.8k"."""
    for size, unit in ((1e6, "M"), (1e3, "k")):
        if abs(value) >= size:
            return f"{value / size:.3g}{unit}"
    return f"{value:.0f}"


def schedule_line(today: int, schedule: Sequence[float]) -> str:
    """Dòng "Cống sắp tới: d16 290k, ..."; ``schedule[0]`` là cống ngày ``today + 1``."""
    if not schedule:
        return ""
    items = [f"d{today + 1 + i} {compact(q)}" for i, q in enumerate(schedule[:MAX_SCHEDULE_SHOWN])]
    return "Cống sắp tới: " + ", ".join(items)


def _ratios(table: GradeOddsTable | None, multiplier: float, fever_strikes: int):
    """Hàm (grade, tích lực) -> Plan.ratio có cache; 1.0 khi không có bảng/không lập được kế hoạch."""
    cache: dict[tuple[int, int], float] = {}

    def ratio(grade: int, charge: int) -> float:
        if table is None or not table.valid:
            return 1.0
        key = (grade, charge)
        if key not in cache:
            plan = plan_sword(grade, charge, table.normal, table.fever, multiplier, fever_strikes)
            cache[key] = plan.ratio if plan is not None else 1.0
        return cache[key]
    return ratio


def holdings_expected(swords: Iterable[Sword], table: GradeOddsTable | None, multiplier: float,
                      fever_strikes: int = DEFAULT_FEVER_STRIKES) -> float:
    """Σ giá trị x Plan.ratio của các kiếm (đã lọc còn trong tay)."""
    ratio = _ratios(table, multiplier, fever_strikes)
    return sum(sw.value * ratio(sw.grade, sw.charge) for sw in swords)


def incoming_per_day(table: GradeOddsTable | None, multiplier: float,
                     fever_strikes: int = DEFAULT_FEVER_STRIKES) -> float:
    """Ước lượng giá trị kỳ vọng kiếm mới nhận mỗi ngày."""
    ratio = _ratios(table, multiplier, fever_strikes)(0, 0)
    return FRESH_SWORDS_PER_DAY * FRESH_SWORD_VALUE * ratio


@dataclass(frozen=True)
class Pace:
    available: float      # kỳ vọng kiếm đang giữ + kiếm mới trong ``days`` ngày tới
    needed: float         # cống còn thiếu hôm nay + cống ``days`` ngày tới
    days: int             # số ngày tới được so (<= PACE_DAYS, theo dữ liệu có được)
    covered_days: int     # số ngày tới liên tiếp đủ cống theo kỳ vọng

    @property
    def shortfall(self) -> float:
        return max(self.needed - self.available, 0.0)

    @property
    def behind(self) -> bool:
        return self.shortfall > EPSILON

    @property
    def comfortable(self) -> bool:
        return self.available >= COMFORT_MARGIN * self.needed


def evaluate_pace(expected: float, incoming_per_day: float, need_today: float,
                  schedule: Sequence[float], days: int = PACE_DAYS) -> Pace | None:
    """So kỳ vọng với cống cộng dồn; ``schedule[i]`` = cống ngày (hôm nay + i + 1)."""
    if not schedule:
        return None
    need = max(need_today, 0.0)
    covered, counting = 0, expected + EPSILON >= need
    for i, quota in enumerate(schedule, start=1):
        need += quota
        counting = counting and expected + incoming_per_day * i + EPSILON >= need
        covered += counting
    k = min(days, len(schedule))
    return Pace(available=expected + incoming_per_day * k,
                needed=max(need_today, 0.0) + sum(schedule[:k]), days=k, covered_days=covered)


def pace_line(pace: Pace) -> Line:
    detail = f" (kỳ vọng {compact(pace.available)} / cần {compact(pace.needed)})"
    if pace.behind:
        return f"Chậm: thiếu {pace.shortfall:,.0f} cho {pace.days} ngày tới{detail}", WARN
    return f"Tiến độ: đủ cho {pace.covered_days} ngày tới{detail}", GOOD


def risk_hint(sword: Sword, plan: Plan | None, odds: SwordOdds, pace: Pace | None,
              ward_charges: int, tribute_locked: bool) -> str | None:
    """Gợi ý mạo hiểm/an toàn cho kiếm chính theo tiến độ.

    ``tribute_locked``: kiếm đang được giữ để đủ cống HÔM NAY -> không bao giờ khuyên đẩy/đổi.
    """
    if pace is None or tribute_locked:
        return None
    if pace.behind and plan is not None and plan.ratio > 1.0 + EPSILON:
        tools = []
        if sword.fever_remaining > 0 or plan.strikes_to_fever <= 2:
            tools.append("trong Xuất Thần")
        if ward_charges > 0:
            tools.append("dùng Vảy Rồng (Q)")
        how = " " + " / ".join(tools) if tools else f" (kế hoạch x{plan.ratio:.2f})"
        return f"Đang chậm tiến độ → đẩy {sword.tag}{how}"
    if (pace.comfortable and sword.fever_remaining <= 0
            and odds.destruction >= RISKY_DESTRUCTION):
        return (f"Đang dư tiến độ → chơi an toàn, đừng mạo hiểm {sword.tag} "
                f"(gãy {odds.destruction:.0%})")
    return None
