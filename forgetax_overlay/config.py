"""Lưu/đọc cấu hình overlay (vị trí, số liệu hiệu chỉnh) giữa các lần mở.

Mọi khóa nằm chung một file JSON; mỗi lần ghi chỉ cập nhật khóa liên quan, giữ nguyên khóa khác.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_FILE = (
    Path(os.environ.get("APPDATA", str(Path.home()))) / "ForgeTaxOverlay" / "config.json"
)


def load_config(path: Path = DEFAULT_CONFIG_FILE) -> dict[str, Any]:
    """Toàn bộ cấu hình; file thiếu/hỏng -> rỗng."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def update_config(path: Path, **values: Any) -> None:
    """Gộp ``values`` vào file cấu hình; lỗi ghi không được làm sập overlay."""
    merged = {**load_config(path), **values}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def load_position(path: Path = DEFAULT_CONFIG_FILE) -> tuple[int, int] | None:
    raw = load_config(path)
    try:
        return int(raw["x"]), int(raw["y"])
    except (KeyError, TypeError, ValueError):
        return None


def save_position(path: Path, x: int, y: int) -> None:
    update_config(path, x=x, y=y)
