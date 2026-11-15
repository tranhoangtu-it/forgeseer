"""Hiệu chỉnh số nhát người chơi đập được trong một đợt Xuất Thần.

Xuất Thần kéo dài theo thời gian (đo được: feverRemaining bắt đầu ~4.0 giây) nên số nhát phụ
thuộc tốc độ tay. Đã quan sát: nhát thường thứ 10 kích hoạt (feverRemaining > 0 ngay khi
strikes tăng lên), các nhát sau đó mới là nhát Xuất Thần. Theo dõi bản chụp liên tiếp: mốc =
min(nhát hiện tại, nhát ở bản chụp trước + 1) để không tính nhát kích hoạt, kết thúc khi
feverRemaining về 0 hoặc kiếm biến mất. Trung bình cộng dồn được lưu trong config.json (khóa ``fever``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .config import load_config, update_config
from .save_reader import Sword

DEFAULT_FEVER_STRIKES = 7  # hướng dẫn cộng đồng: ~7 nhát khi đập hết tốc
MAX_FEVER_STRIKES = 40     # chặn mẫu bất thường (bản chụp lỗi)
CONFIG_KEY = "fever"


@dataclass(frozen=True)
class FeverStats:
    total: int = 0
    samples: int = 0

    @property
    def strikes(self) -> int:
        """Số nhát trung bình mỗi đợt (làm tròn); mặc định khi chưa có mẫu."""
        if self.samples <= 0:
            return DEFAULT_FEVER_STRIKES
        return max(1, int(self.total / self.samples + 0.5))

    def add(self, count: int) -> "FeverStats":
        return FeverStats(self.total + count, self.samples + 1)


@dataclass(frozen=True)
class FeverTracker:
    prev: dict[int, tuple[int, bool]] = field(default_factory=dict)  # serial -> (nhát, đang XT)
    start: dict[int, int] = field(default_factory=dict)              # serial -> mốc nhát
    last: dict[int, int] = field(default_factory=dict)               # serial -> nhát gần nhất


def observe(tracker: FeverTracker, swords: Iterable[Sword]) -> tuple[FeverTracker, list[int]]:
    """Bản chụp mới -> (tracker mới, số nhát của các đợt vừa kết thúc)."""
    live = {sw.serial: sw for sw in swords if sw.active and not sw.broken}
    start, last, done = dict(tracker.start), dict(tracker.last), []
    for serial, sw in live.items():
        in_fever = sw.fever_remaining > 0
        before = tracker.prev.get(serial)
        if in_fever and serial not in start and before is not None and not before[1]:
            start[serial] = min(sw.strikes, before[0] + 1)
        if serial in start:
            if in_fever:
                last[serial] = sw.strikes
            else:
                done.append(sw.strikes - start.pop(serial))
                last.pop(serial, None)
    for serial in [s for s in start if s not in live]:  # kiếm biến mất giữa đợt
        done.append(last.pop(serial, start[serial]) - start.pop(serial))
    prev = {s: (sw.strikes, sw.fever_remaining > 0) for s, sw in live.items()}
    counts = [c for c in done if 1 <= c <= MAX_FEVER_STRIKES]
    return FeverTracker(prev, start, last), counts


def load_fever_stats(path: Path) -> FeverStats:
    raw = load_config(path).get(CONFIG_KEY)
    try:
        total, samples = int(raw["total"]), int(raw["samples"])
    except (KeyError, TypeError, ValueError):
        return FeverStats()
    return FeverStats(total, samples) if total >= 0 and samples >= 0 else FeverStats()


def save_fever_stats(path: Path, stats: FeverStats) -> None:
    update_config(path, **{CONFIG_KEY: {"total": stats.total, "samples": stats.samples}})
