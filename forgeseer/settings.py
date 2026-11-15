"""Overlay settings chosen on the start-up screen, kept in config.json under ``settings``.

Pure logic only (no Tk): defaults, validation/clamping, persistence and the small decisions the
overlay makes from the settings (which panels are visible, which language override applies).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

from .config import load_config, update_config
from .i18n import SUPPORTED

LANG_AUTO = "auto"  # follow the game, then Windows
OPACITY_MIN, OPACITY_MAX = 40, 100  # percent
FONT_MIN, FONT_MAX = 8, 16  # points
CONFIG_KEY = "settings"


@dataclass(frozen=True)
class Settings:
    language: str = LANG_AUTO
    opacity: int = 85
    font_size: int = 10
    show_details: bool = True
    show_todo: bool = True
    show_legend: bool = False
    live: bool = True
    skip_settings: bool = False
    check_updates: bool = True  # ask GitHub for a newer release at start-up

    @property
    def alpha(self) -> float:
        return self.opacity / 100


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return default
    return max(low, min(high, number))


def from_dict(raw: Any) -> Settings:
    """Build valid settings from untrusted data: unknown keys ignored, bad values -> default."""
    defaults = Settings()
    if not isinstance(raw, dict):
        return defaults
    language = raw.get("language", defaults.language)
    if language != LANG_AUTO and language not in SUPPORTED:
        language = defaults.language
    flags = {f.name: (raw[f.name] if isinstance(raw.get(f.name), bool) else getattr(defaults, f.name))
             for f in fields(Settings) if isinstance(getattr(defaults, f.name), bool)}
    return Settings(
        language=language,
        opacity=_clamp_int(raw.get("opacity"), OPACITY_MIN, OPACITY_MAX, defaults.opacity),
        font_size=_clamp_int(raw.get("font_size"), FONT_MIN, FONT_MAX, defaults.font_size),
        **flags,
    )


def to_dict(settings: Settings) -> dict[str, Any]:
    return asdict(settings)


def load_settings(path: Path) -> Settings:
    return from_dict(load_config(path).get(CONFIG_KEY))


def save_settings(path: Path, settings: Settings) -> None:
    update_config(path, **{CONFIG_KEY: to_dict(settings)})


def language_override(settings: Settings) -> str | None:
    """Language forced by the settings; None for "auto" (game language, then Windows)."""
    return None if settings.language == LANG_AUTO else settings.language


def panel_visibility(settings: Settings, hidden: bool, legend_on: bool) -> tuple[bool, bool, bool]:
    """(details, to do, legend) shown? F8 (``hidden``) hides everything."""
    if hidden:
        return False, False, False
    return settings.show_details, settings.show_todo, legend_on


def apply_cli(settings: Settings, lang: str | None, no_live: bool) -> Settings:
    """Cờ dòng lệnh (--lang, --no-live) điền sẵn vào cài đặt của lần chạy này."""
    if lang:
        settings = replace(settings, language=lang)
    if no_live:
        settings = replace(settings, live=False)
    return settings
