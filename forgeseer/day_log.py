"""Nhật ký từng ngày của lượt chơi: ``%APPDATA%\\ForgeTaxOverlay\\days.jsonl``.

Mỗi khi ``round`` đổi (hoặc lượt sang lượt khác) ghi bản chụp CUỐI CÙNG của ngày trước đó
(cống, đã nộp, giá trị kiếm còn giữ, grade cao nhất, số lần lỡ cống); khi lượt kết thúc ghi luôn
ngày hiện tại. Mỗi (run_id, round) chỉ ghi một lần. Dùng để xem lại đã hụt tiến độ từ ngày nào.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .run_log import DEFAULT_RUN_LOG
from .save_reader import RunState

DEFAULT_DAY_LOG = DEFAULT_RUN_LOG.with_name("days.jsonl")
DayKey = tuple[str, int]


@dataclass(frozen=True)
class DayRecord:
    run_id: str
    round: int
    quota: float
    delivered: int
    holdings: int
    top_grade: int
    missed: int

    @property
    def key(self) -> DayKey:
        return self.run_id, self.round


@dataclass(frozen=True)
class DayTracker:
    last: DayRecord | None = None


def day_record(state: RunState, quota: float) -> DayRecord:
    live = [sw for sw in state.swords if sw.is_live]
    return DayRecord(run_id=state.run_id, round=state.round, quota=float(quota),
                     delivered=state.delivered, holdings=sum(sw.value for sw in live),
                     top_grade=max((sw.grade for sw in live), default=0),
                     missed=state.missed_tributes)


def observe_day(tracker: DayTracker, state: RunState,
                quota: float) -> tuple[DayTracker, DayRecord | None]:
    """Cập nhật bản chụp; trả bản ghi cần lưu (ngày vừa qua, hoặc ngày cuối khi lượt kết thúc)."""
    current = day_record(state, quota)
    last = tracker.last
    if state.finished:
        return DayTracker(current), current
    if last is not None and last.key != current.key:
        return DayTracker(current), last
    return DayTracker(current), None


def load_day_keys(path: Path = DEFAULT_DAY_LOG) -> set[DayKey]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    keys: set[DayKey] = set()
    for line in lines:
        try:
            raw = json.loads(line)
            keys.add((str(raw["run_id"]), int(raw["round"])))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return keys


def load_days(path: Path = DEFAULT_DAY_LOG) -> list[DayRecord]:
    """Every readable day record, in file order; broken lines are skipped."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    days: list[DayRecord] = []
    for line in lines:
        try:
            raw = json.loads(line)
            days.append(DayRecord(run_id=str(raw["run_id"]), round=int(raw["round"]),
                                  quota=float(raw.get("quota", 0)),
                                  delivered=int(raw.get("delivered", 0)),
                                  holdings=int(raw.get("holdings", 0)),
                                  top_grade=int(raw.get("top_grade", 0)),
                                  missed=int(raw.get("missed", 0))))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError):
            continue
    return days


def append_day(path: Path, record: DayRecord, keys: set[DayKey]) -> bool:
    """Ghi thêm nếu (run_id, round) chưa có; True nếu đã ghi."""
    if record.key in keys:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True
