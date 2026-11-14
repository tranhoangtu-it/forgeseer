"""Lưu/đọc vị trí overlay giữa các lần mở."""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_CONFIG_FILE = (
    Path(os.environ.get("APPDATA", str(Path.home()))) / "ForgeTaxOverlay" / "config.json"
)


def load_position(path: Path = DEFAULT_CONFIG_FILE) -> tuple[int, int] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return int(raw["x"]), int(raw["y"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def save_position(path: Path, x: int, y: int) -> None:
    """Ghi vị trí; lỗi ghi file chỉ làm mất vị trí đã lưu, không được làm sập overlay."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"x": x, "y": y}), encoding="utf-8")
    except OSError:
        pass
