"""Nhật ký các lượt chơi đã kết thúc (một dòng JSON mỗi lượt) và dòng tóm tắt.

Ghi vào ``%APPDATA%\\ForgeTaxOverlay\\runs.jsonl`` khi ``RunState.finished`` bật; mỗi lượt
chỉ ghi một lần (theo ``campaign.anonymousRunId``).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .i18n import t
from .save_reader import RunState
from .text_format import SEP

DEFAULT_RUN_LOG = (
    Path(os.environ.get("APPDATA", str(Path.home()))) / "ForgeTaxOverlay" / "runs.jsonl"
)


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    round: int
    won: bool
    gold_earned: int
    highest_grade: int
    missed_tributes: int
    relics: tuple[str, ...]


def record_from_state(state: RunState) -> RunRecord:
    return RunRecord(run_id=state.run_id, round=state.round, won=state.won,
                     gold_earned=state.gold_earned, highest_grade=state.highest_grade,
                     missed_tributes=state.missed_tributes,
                     relics=tuple(r.id for r in state.relics))


def _from_json(raw: Any) -> RunRecord | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("run_id"), str):
        return None
    try:
        return RunRecord(run_id=raw["run_id"], round=int(raw.get("round", 0)),
                         won=bool(raw.get("won", False)),
                         gold_earned=int(raw.get("gold_earned", 0)),
                         highest_grade=int(raw.get("highest_grade", 0)),
                         missed_tributes=int(raw.get("missed_tributes", 0)),
                         relics=tuple(str(r) for r in raw.get("relics", ())))
    except (TypeError, ValueError):
        return None


def load_runs(path: Path = DEFAULT_RUN_LOG) -> list[RunRecord]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    runs = []
    for line in lines:
        try:
            rec = _from_json(json.loads(line))
        except json.JSONDecodeError:
            continue
        if rec is not None:
            runs.append(rec)
    return runs


def append_run(path: Path, record: RunRecord, existing: list[RunRecord]) -> bool:
    """Ghi thêm nếu lượt chưa có trong nhật ký; True nếu đã ghi."""
    if any(r == record or (record.run_id and r.run_id == record.run_id) for r in existing):
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def _describe(r: RunRecord) -> str:
    won = " " + t("runs.won") if r.won else ""
    return t("runs.describe", day=r.round, won=won, grade=r.highest_grade)


def summary_line(runs: list[RunRecord]) -> str:
    if not runs:
        return ""
    best = max(runs, key=lambda r: (r.won, r.round, r.highest_grade, r.gold_earned))
    return SEP.join((t("runs.played", count=len(runs)), t("runs.best", run=_describe(best)),
                     t("runs.latest", run=_describe(runs[-1]))))
