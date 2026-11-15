import json

import pytest

from forgeseer.config import load_config
from forgeseer.i18n import SUPPORTED, catalog, choose_language, set_language, t
from forgeseer.settings import (FONT_MAX, FONT_MIN, LANG_AUTO, OPACITY_MAX, OPACITY_MIN, Settings,
                                apply_cli, from_dict, language_override, load_settings,
                                panel_visibility, save_settings, to_dict)


def test_defaults_show_both_panels_and_read_live():
    settings = Settings()

    assert settings.language == LANG_AUTO
    assert (settings.show_details, settings.show_todo, settings.show_legend) == (True, True, False)
    assert settings.live is True
    assert settings.skip_settings is False
    assert OPACITY_MIN <= settings.opacity <= OPACITY_MAX
    assert FONT_MIN <= settings.font_size <= FONT_MAX


@pytest.mark.parametrize("raw, opacity, font", [
    ({"opacity": 5, "font_size": 99}, OPACITY_MIN, FONT_MAX),
    ({"opacity": 250, "font_size": 1}, OPACITY_MAX, FONT_MIN),
    ({"opacity": "70", "font_size": 12.6}, 70, 13),
    ({"opacity": "x", "font_size": None}, Settings().opacity, Settings().font_size),
    ({"opacity": True, "font_size": False}, Settings().opacity, Settings().font_size),
])
def test_numbers_are_clamped_or_defaulted(raw, opacity, font):
    settings = from_dict(raw)

    assert (settings.opacity, settings.font_size) == (opacity, font)


def test_bad_language_and_flags_fall_back_to_defaults():
    settings = from_dict({"language": "tlh", "show_todo": "no", "live": 0, "extra": 1})

    assert settings == Settings()


def test_non_dict_gives_defaults():
    assert from_dict(None) == Settings()
    assert from_dict([1, 2]) == Settings()


def test_alpha_is_opacity_fraction():
    assert from_dict({"opacity": 60}).alpha == pytest.approx(0.6)


def test_round_trip_keeps_other_config_keys(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"x": 5, "y": 6, "game_lang": "ja"}), encoding="utf-8")
    settings = Settings(language="de", opacity=55, font_size=14, show_details=False,
                        show_todo=True, show_legend=True, live=False, skip_settings=True)

    save_settings(cfg, settings)

    assert load_settings(cfg) == settings
    raw = load_config(cfg)
    assert (raw["x"], raw["y"], raw["game_lang"]) == (5, 6, "ja")
    assert raw["settings"] == to_dict(settings)


def test_missing_or_broken_file_gives_defaults(tmp_path):
    broken = tmp_path / "config.json"
    broken.write_text("{nope", encoding="utf-8")

    assert load_settings(tmp_path / "missing.json") == Settings()
    assert load_settings(broken) == Settings()


def test_auto_language_follows_game_then_windows():
    auto = language_override(Settings())

    assert auto is None
    assert choose_language(auto, "ja", "vi") == "ja"
    assert choose_language(auto, None, "vi") == "vi"


def test_picked_language_wins_over_game():
    picked = language_override(Settings(language="de"))

    assert choose_language(picked, "ja", "vi") == "de"


@pytest.mark.parametrize("details, todo, hidden, legend_on, expected", [
    (True, True, False, False, (True, True, False)),
    (False, True, False, True, (False, True, True)),
    (True, False, False, False, (True, False, False)),
    (True, True, True, True, (False, False, False)),
])
def test_panel_visibility_respects_flags_and_f8(details, todo, hidden, legend_on, expected):
    settings = Settings(show_details=details, show_todo=todo)

    assert panel_visibility(settings, hidden, legend_on) == expected


def test_cli_flags_prefill_settings():
    base = Settings(language="vi", live=True)

    assert apply_cli(base, None, False) == base
    assert apply_cli(base, "ko", True) == Settings(language="ko", live=False)


def test_settings_screen_text_exists_in_every_language():
    keys = [k for k in catalog("en") if k.startswith(("settings.", "hotkey."))]
    assert len(keys) >= 20
    for lang in SUPPORTED:
        set_language(lang)
        assert all(t(key) != key and t(key).strip() for key in keys), lang
        assert t("hint.keys").startswith("F6"), lang


def test_update_check_flag_defaults_on_and_ignores_bad_values():
    assert Settings().check_updates is True
    assert from_dict({"check_updates": False}).check_updates is False
    assert from_dict({"check_updates": "no"}).check_updates is True
