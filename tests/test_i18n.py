import json
import re

import pytest

from forgeseer import i18n
from forgeseer.i18n import SUPPORTED, catalog, choose_language, normalize, set_language, t
from forgeseer.legend import legend_lines
from forgeseer.text_format import LINE_WIDTH, display_width, fmt_dec, fmt_int, fmt_pct, fmt_ratio

PLACEHOLDER = re.compile(r"{(\w+)}")


def test_every_supported_language_ships_a_catalog():
    for lang in SUPPORTED:
        path = i18n.LOCALES_DIR / f"{lang}.json"
        assert path.exists(), lang
        json.loads(path.read_text(encoding="utf-8"))


def test_catalogs_have_identical_keys():
    reference = set(catalog("vi"))
    for lang in SUPPORTED:
        assert set(catalog(lang)) == reference, lang


def test_catalogs_use_the_same_placeholders():
    for key, text in catalog("vi").items():
        expected = set(PLACEHOLDER.findall(text))
        for lang in SUPPORTED:
            assert set(PLACEHOLDER.findall(catalog(lang)[key])) == expected, (lang, key)


def test_merchant_and_verdict_words_are_distinct_in_every_language():
    keys = ("merchant.buy", "merchant.consider", "merchant.skip", "merchant.no_gold",
            "merchant.see_description")
    for lang in SUPPORTED:
        words = [catalog(lang)[k] for k in keys]
        assert len(set(words)) == len(words), lang
        assert catalog(lang)["verdict.strike"] != catalog(lang)["verdict.stop"], lang


def test_t_falls_back_to_english_then_key(monkeypatch):
    set_language("ja")
    monkeypatch.setitem(catalog("en"), "test.only_en", "english {n}")

    assert t("test.only_en", n=3) == "english 3"
    assert t("test.missing.key") == "test.missing.key"


def test_t_keeps_text_when_a_placeholder_is_missing():
    assert t("sword.strikes") == "Đã đập {count} nhát"
    assert t("sword.strikes", other=1) == "Đã đập {count} nhát"


def test_set_language_rejects_unknown_codes():
    assert set_language("xx") == "en"
    assert set_language("vi_VN") == "vi"


@pytest.mark.parametrize("raw, expected", [
    ("vi", "vi"), ("vi-VN", "vi"), ("en_US", "en"), ("ko-KR", "ko"), ("ja", "ja"),
    ("zh-Hans", "zh-CN"), ("zh_CN", "zh-CN"), ("zh-Hant-TW", "zh-TW"), ("zh-HK", "zh-TW"),
    ("pt", "pt-BR"), ("pt_BR", "pt-BR"), ("de-AT", "de"), ("Korean", "ko"), ("", None),
    (None, None), ("tlh", None),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_choose_language_order():
    assert choose_language("de", "ja", "vi") == "de"
    assert choose_language(None, "ja", "vi") == "ja"
    assert choose_language(None, None, "vi") == "vi"
    assert choose_language(None, "??", None) == "en"


@pytest.mark.parametrize("lang, integer, decimal", [
    ("vi", "44.200", "1,21"), ("en", "44,200", "1.21"), ("de", "44.200", "1,21"),
    ("es", "44.200", "1,21"), ("pt-BR", "44.200", "1,21"), ("ru", "44 200", "1,21"),
    ("ja", "44,200", "1.21"), ("ko", "44,200", "1.21"), ("zh-CN", "44,200", "1.21"),
    ("zh-TW", "44,200", "1.21"),
])
def test_number_format_follows_language(lang, integer, decimal):
    set_language(lang)

    assert fmt_int(44200) == integer
    assert fmt_dec(1.2149) == decimal
    assert fmt_ratio(1.2149) == "×" + decimal
    assert fmt_pct(0.195, 1) == fmt_dec(19.5, 1) + "%"


def test_place_names_follow_language():
    from forgeseer.save_reader import PLACE_ANVIL, Sword
    sword = Sword(1, 8, 100, 100, 0, 0, 0, 0, False, False, True, -1, 0, 0.0, place=PLACE_ANVIL)

    set_language("en")
    assert sword.tag == "+8 on the anvil"
    set_language("vi")
    assert sword.tag == "+8 trên đe"


def test_legend_fits_width_in_every_language():
    for lang in SUPPORTED:
        set_language(lang)
        lines = legend_lines()
        assert lines[0][0] == t("legend.title")
        assert all(display_width(text) <= LINE_WIDTH for text, _ in lines), lang


def test_every_language_ships_an_extra_catalog_with_the_same_keys():
    keys = None
    for lang in SUPPORTED:
        path = i18n.LOCALES_DIR / f"{lang}.extra.json"
        extra = json.loads(path.read_text(encoding="utf-8"))
        keys = keys or set(extra)
        assert set(extra) == keys, lang
        assert set(extra) <= set(catalog(lang)), lang  # merged into the catalog


def test_extra_catalog_is_merged_over_the_base(tmp_path, monkeypatch):
    (tmp_path / "en.json").write_text('{"a": "base", "b": "keep"}', encoding="utf-8")
    (tmp_path / "en.extra.json").write_text('{"a": "extra", "c": "new"}', encoding="utf-8")
    monkeypatch.setattr(i18n, "LOCALES_DIR", tmp_path)
    catalog.cache_clear()
    try:
        assert catalog("en") == {"a": "extra", "b": "keep", "c": "new"}
    finally:
        catalog.cache_clear()


def test_display_width_counts_wide_characters_twice():
    assert display_width("abc") == 3
    assert display_width("破壊") == 4
    assert display_width("Gãy") == 3
