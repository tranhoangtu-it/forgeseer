"""Overlay text in several languages.

Every string shown on the overlay goes through ``t(key, **values)``. Catalogs live in
``forgeseer/locales/<code>.json`` (flat key -> text, ``str.format`` placeholders), with the
optional ``<code>.extra.json`` (settings-window tabs) merged on top. A missing key
falls back to English, then to the key itself, so a half-finished catalog never crashes.

The active language is picked in this order: ``--lang`` on the command line, the language the
game is running in (sent by the live script), the Windows UI language, then English.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LOCALES_DIR = Path(__file__).with_name("locales")
SUPPORTED = ("vi", "en", "ko", "ja", "zh-CN", "zh-TW", "de", "es", "pt-BR", "ru")
DEFAULT_LANGUAGE = "en"

_ALIASES = {
    "zh-hans": "zh-CN", "zh-sg": "zh-CN", "zh": "zh-CN",
    "zh-hant": "zh-TW", "zh-hk": "zh-TW", "zh-mo": "zh-TW",
    "pt": "pt-BR", "pt-pt": "pt-BR",
    "english": "en", "korean": "ko", "japanese": "ja", "vietnamese": "vi", "german": "de",
    "spanish": "es", "russian": "ru", "portuguese": "pt-BR",
    "chinese": "zh-CN", "chinesesimplified": "zh-CN", "chinesetraditional": "zh-TW",
}

_current = DEFAULT_LANGUAGE


def normalize(code: str | None) -> str | None:
    """'vi_VN' -> 'vi', 'zh-Hant-TW' -> 'zh-TW', 'pt' -> 'pt-BR'; unknown -> None."""
    if not code or not isinstance(code, str):
        return None
    raw = code.strip().replace("_", "-")
    lowered = raw.lower()
    for lang in SUPPORTED:
        if lowered == lang.lower():
            return lang
    compact = lowered.replace(" ", "").replace("(", "").replace(")", "")
    if compact in _ALIASES:
        return _ALIASES[compact]
    parts = lowered.split("-")
    for size in (2, 1):
        prefix = "-".join(parts[:size])
        if prefix in _ALIASES:
            return _ALIASES[prefix]
        for lang in SUPPORTED:
            if prefix == lang.lower():
                return lang
    return None


def windows_ui_language() -> str | None:
    """Language of the Windows display UI ('vi', 'en', ...); None when unavailable."""
    try:
        import ctypes
        import locale
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return normalize(locale.windows_locale.get(lcid))
    except (AttributeError, OSError, ImportError):
        return None


def choose_language(cli: str | None = None, game: str | None = None,
                    system: str | None = None) -> str:
    for candidate in (cli, game, system):
        lang = normalize(candidate)
        if lang is not None:
            return lang
    return DEFAULT_LANGUAGE


def _load_catalog_file(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


@lru_cache(maxsize=None)
def catalog(lang: str) -> dict[str, str]:
    """``<lang>.json`` with the optional ``<lang>.extra.json`` (settings-window texts) on top."""
    return {**_load_catalog_file(LOCALES_DIR / f"{lang}.json"),
            **_load_catalog_file(LOCALES_DIR / f"{lang}.extra.json")}


def set_language(lang: str | None) -> str:
    """Switch the active language (unknown codes fall back to English); returns the code used."""
    global _current
    _current = normalize(lang) or DEFAULT_LANGUAGE
    return _current


def get_language() -> str:
    return _current


def t(key: str, **values: object) -> str:
    text = catalog(_current).get(key)
    if text is None:
        text = catalog(DEFAULT_LANGUAGE).get(key, key)
    if not values:
        return text
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text
