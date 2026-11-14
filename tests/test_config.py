from forgetax_overlay.config import load_config, load_position, save_position


def test_position_round_trip(tmp_path):
    cfg = tmp_path / "sub" / "config.json"

    save_position(cfg, 1500, 40)

    assert load_position(cfg) == (1500, 40)


def test_save_position_keeps_other_keys(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"fever": {"total": 7, "samples": 1}}', encoding="utf-8")

    save_position(cfg, 1, 2)

    assert load_config(cfg) == {"fever": {"total": 7, "samples": 1}, "x": 1, "y": 2}


def test_load_position_returns_none_when_missing_or_broken(tmp_path):
    broken = tmp_path / "config.json"
    broken.write_text("not json", encoding="utf-8")

    assert load_position(tmp_path / "missing.json") is None
    assert load_position(broken) is None
