"""Bảng dịch id relic -> tên dễ đọc.

Tên chính thức trong game bị Obfuz mã hóa nên không trích xuất tự động được;
bảng ``relic_names.json`` là bản dịch nghĩa id, người chơi có thể sửa theo tên thật trong game.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BUNDLED_NAMES_FILE = Path(__file__).with_name("relic_names.json")
# Tên + mô tả CHÍNH THỨC (tiếng Việt) đọc từ bảng ngôn ngữ của game khi chạy live.
TEXTS_CACHE_FILE = (
    Path(os.environ.get("APPDATA", str(Path.home()))) / "ForgeTaxOverlay" / "relic_texts.json"
)


@dataclass(frozen=True)
class RelicText:
    name: str
    description: str


def parse_relic_texts(raw: Any) -> dict[str, RelicText]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, RelicText] = {}
    for relic_id, entry in raw.items():
        if isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"]:
            result[str(relic_id)] = RelicText(entry["name"], str(entry.get("description") or ""))
    return result


def load_relic_texts(path: Path = TEXTS_CACHE_FILE) -> dict[str, RelicText]:
    try:
        return parse_relic_texts(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {}


def load_relic_names(path: Path = BUNDLED_NAMES_FILE) -> dict[str, str]:
    """Đọc bảng tên; file thiếu hoặc lỗi -> dict rỗng (overlay vẫn chạy, hiện id gốc)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): v for k, v in raw.items() if isinstance(v, str) and v}


def display_name(relic_id: str, names: dict[str, str]) -> str:
    return names.get(relic_id, relic_id)
