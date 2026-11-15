"""Tên di vật: tên chính thức từ bảng ngôn ngữ của game, dự phòng bằng bảng tự dịch.

Khi đọc trực tiếp, script lấy tên + mô tả ``item.<id>.name/description`` của mọi ngôn ngữ trong
bảng của game và lưu vào ``relic_texts.json``. ``relic_names.json`` là tên tiếng Việt tự dịch
theo nghĩa id, chỉ dùng khi chưa từng kết nối được với game.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BUNDLED_NAMES_FILE = Path(__file__).with_name("relic_names.json")
# Tên + mô tả chính thức (mọi ngôn ngữ có trong bảng) đọc từ game khi chạy live.
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


LanguageTexts = dict[str, dict[str, RelicText]]  # ngôn ngữ -> id relic -> chữ
FALLBACK_TEXT_LANGUAGE = "vi"


def parse_language_texts(raw: Any) -> LanguageTexts:
    """``{lang: {id: {name, description}}}`` -> LanguageTexts. File cache cũ chỉ có một bảng
    ``{id: {name, description}}`` (tiếng Việt) -> coi là ``{"vi": ...}``."""
    if not isinstance(raw, dict):
        return {}
    if any(isinstance(v, dict) and isinstance(v.get("name"), str) for v in raw.values()):
        raw = {FALLBACK_TEXT_LANGUAGE: raw}
    return {str(lang): texts for lang, items in raw.items() if (texts := parse_relic_texts(items))}


def pick_language_texts(texts: LanguageTexts, lang: str | None) -> dict[str, RelicText]:
    """Bảng của ``lang``; không có thì tiếng Việt, rồi bảng đầu tiên; rỗng nếu chưa có gì."""
    if lang in texts:
        return texts[lang]
    if FALLBACK_TEXT_LANGUAGE in texts:
        return texts[FALLBACK_TEXT_LANGUAGE]
    return next(iter(texts.values()), {})


def load_relic_texts(path: Path = TEXTS_CACHE_FILE, lang: str | None = None) -> dict[str, RelicText]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return pick_language_texts(parse_language_texts(raw), lang)


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
