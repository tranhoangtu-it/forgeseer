import json

from forgeseer.relic_names import (
    RelicText,
    display_name,
    load_relic_names,
    load_relic_texts,
    parse_relic_texts,
)


def test_parse_relic_texts_skips_bad_entries():
    texts = parse_relic_texts({"nail": {"name": "Đinh Cong", "description": "+4"},
                               "bad": "x", "noname": {"description": "y"}})

    assert texts == {"nail": RelicText("Đinh Cong", "+4")}


def test_load_relic_texts_reads_cache_or_returns_empty(tmp_path):
    f = tmp_path / "relic_texts.json"
    f.write_text(json.dumps({"nail": {"name": "Đinh Cong", "description": "+4"}}), encoding="utf-8")

    assert load_relic_texts(f)["nail"].description == "+4"
    assert load_relic_texts(tmp_path / "missing.json") == {}


def test_load_relic_texts_picks_language_with_vietnamese_fallback(tmp_path):
    f = tmp_path / "relic_texts.json"
    f.write_text(json.dumps({"vi": {"nail": {"name": "Đinh Cong"}},
                             "de": {"nail": {"name": "Krummer Nagel"}}}), encoding="utf-8")

    assert load_relic_texts(f, "de")["nail"].name == "Krummer Nagel"
    assert load_relic_texts(f, "en")["nail"].name == "Đinh Cong"
    assert load_relic_texts(f)["nail"].name == "Đinh Cong"


def test_display_name_uses_mapping_and_keeps_id():
    assert display_name("nail", {"nail": "Đinh"}) == "Đinh"


def test_display_name_falls_back_to_id():
    assert display_name("mystery", {}) == "mystery"


def test_load_relic_names_reads_json_file(tmp_path):
    f = tmp_path / "names.json"
    f.write_text(json.dumps({"nail": "Đinh", "bad": 3}), encoding="utf-8")

    assert load_relic_names(f) == {"nail": "Đinh"}  # bỏ giá trị không phải chuỗi


def test_load_relic_names_returns_empty_on_missing_or_broken_file(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{oops", encoding="utf-8")

    assert load_relic_names(tmp_path / "missing.json") == {}
    assert load_relic_names(broken) == {}


def test_bundled_names_cover_relics_seen_in_real_saves():
    names = load_relic_names()

    for relic_id in ("nail", "file", "discount", "dice", "seal", "hold", "hourglass", "apron"):
        assert relic_id in names
