"""Cảnh báo trên overlay: Xuất Thần bắt đầu, thiếu cống trong ngày, di vật ★ đang bán.

Hàm thuần. ``detect_alerts`` so tín hiệu mới với bộ nhớ (bất biến) và trả về các cảnh báo mới,
mỗi sự kiện một lần:

- Xuất Thần: khi một kiếm vào Xuất Thần; cùng kiếm chỉ báo lại nếu đã ra khỏi Xuất Thần quá
  ``FEVER_REARM_SECONDS`` (bản chụp trực tiếp có thể hụt một nhịp giữa đợt).
- Thiếu cống: game không cho biết ngày sắp hết, nên báo một lần cho mỗi ngày (lượt + vòng) ngay
  khi thấy thiếu.
- ★: một lần cho mỗi món ★ đang bán trong ngày.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .relic_rank import RelicRank, top_offer
from .save_reader import RunState
from .tribute import tribute_status

FEVER, TRIBUTE, STAR = "fever", "tribute", "star"
FEVER_REARM_SECONDS = 3.0
SOUND_KEY = "sound_alerts"

DayKey = tuple[str, int]  # (run_id, vòng)


@dataclass(frozen=True)
class AlertSignals:
    day: DayKey
    fever: frozenset[int] = frozenset()      # serial các kiếm đang Xuất Thần
    tribute_short: bool = False              # nộp hết kiếm vẫn thiếu cống hôm nay
    starred: frozenset[str] = frozenset()    # id món ★ đang bán


@dataclass(frozen=True)
class AlertMemory:
    fever_seen: tuple[tuple[int, float], ...] = ()  # (serial, lần cuối thấy đang Xuất Thần)
    tribute_days: frozenset[DayKey] = field(default_factory=frozenset)
    starred_seen: frozenset[tuple[DayKey, str]] = field(default_factory=frozenset)


def detect_alerts(memory: AlertMemory, signals: AlertSignals,
                  now: float) -> tuple[AlertMemory, tuple[str, ...]]:
    seen = {serial: at for serial, at in memory.fever_seen if now - at <= FEVER_REARM_SECONDS}
    fired: list[str] = []
    if any(serial not in seen for serial in signals.fever):
        fired.append(FEVER)
    seen.update({serial: now for serial in signals.fever})

    tribute_days = memory.tribute_days
    if signals.tribute_short and signals.day not in tribute_days:
        fired.append(TRIBUTE)
        tribute_days = tribute_days | {signals.day}

    starred = {(signals.day, item) for item in signals.starred}
    if starred - memory.starred_seen:
        fired.append(STAR)
    new_memory = AlertMemory(tuple(sorted(seen.items())), tribute_days,
                             memory.starred_seen | starred)
    return new_memory, tuple(fired)


def alert_signals(state: RunState, quota: float, relic_rank: RelicRank | None,
                  merchant_ids: Iterable[str] = ()) -> AlertSignals:
    """Tín hiệu từ trạng thái đang hiển thị (cùng nguồn với các khung)."""
    live = [sw for sw in state.swords if sw.is_live]
    status = tribute_status(state, quota)
    shop_ids = [o.id for o in state.offers if not o.sold] if state.shopping else []
    starred = {best.id for ids in (shop_ids, list(merchant_ids))
               if (best := top_offer(relic_rank, ids)) is not None}
    return AlertSignals(day=(state.run_id, state.round),
                        fever=frozenset(sw.serial for sw in live if sw.fever_remaining > 0),
                        tribute_short=status is not None and status.shortfall > 0,
                        starred=frozenset(starred))


def sound_enabled(config: Any) -> bool:
    """Khóa ``settings.sound_alerts`` trong config.json; thiếu hoặc sai kiểu -> bật."""
    settings = config.get("settings") if isinstance(config, dict) else None
    value = settings.get(SOUND_KEY) if isinstance(settings, dict) else None
    return value if isinstance(value, bool) else True
