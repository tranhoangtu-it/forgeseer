from forgetax_overlay.relic_rank import (
    CONDITIONAL_IDS, RelicRank, parse_relic_rank, rank_relics, relic_rank_lines, star_step, top_offer,
)


def _odds(d8, d12, d16):
    return {"8": [d8, 100, 300, 500, 100 - d8 + 0],
            "12": [d12, 100, 300, 400, 200 - d12],
            "16": [d16, 100, 300, 300, 300 - d16]}


RAW = {
    "baseline": _odds(50, 150, 250),
    "items": {
        "seal": _odds(43, 128, 213),   # -15%
        "tongs": _odds(38, 113, 188),  # -25% (từ +6)
        "nail": _odds(48, 140, 240),
        "coin": _odds(50, 150, 250),   # không đổi -> không xếp hạng
        "bad": _odds(60, 170, 270),    # tăng gãy -> không xếp hạng
        "tie": _odds(40, 128, 213),    # bằng seal ở +12/+16, hơn ở +8
    },
    "owned": {"rivet": _odds(55, 160, 262)},
    "shelfFull": True,
}


def test_parse_relic_rank_reads_grades_items_owned_and_shelf_flag():
    rank = parse_relic_rank(RAW)

    assert sorted(rank.baseline) == [8, 12, 16]
    assert rank.baseline[12].destruction == 0.15
    assert rank.items["seal"][16].destruction == 0.213
    assert rank.owned["rivet"][8].destruction == 0.055
    assert rank.shelf_full is True


def test_parse_relic_rank_ignores_malformed_entries():
    rank = parse_relic_rank({"baseline": {"x": [1, 2, 3, 4, 5], "8": [1, 2]},
                             "items": {"seal": "nope", "nail": {"8": [1, 2, 3, 4, 5]}}})

    assert rank.baseline == {}
    assert list(rank.items) == ["nail"]
    assert parse_relic_rank(None) == RelicRank()


def test_rank_orders_by_reduction_at_12_then_16_then_8_and_drops_useless():
    ranked = rank_relics(parse_relic_rank(RAW))

    assert [r.id for r in ranked] == ["tongs", "tie", "seal", "nail"]
    assert abs(ranked[0].reduction(12) - 0.037) < 1e-9


def test_rank_keeps_top_eight():
    items = {f"r{i}": _odds(50, 150 - i, 250) for i in range(1, 12)}
    ranked = rank_relics(parse_relic_rank({"baseline": _odds(50, 150, 250), "items": items}))

    assert len(ranked) == 8
    assert ranked[0].id == "r11"


def test_top_offer_picks_best_ranked_offer():
    rank = parse_relic_rank(RAW)

    assert top_offer(rank, ["nail", "seal", "coin"]).id == "seal"
    assert top_offer(rank, ["coin"]) is None


def test_section_lists_deltas_stars_offers_and_conditional_line():
    names = {"seal": "Nút Thắt Đen", "tongs": "Kìm Vảy Rồng", "rivet": "Đai Sắt",
             "brace": "Bùa Cháy Sém"}
    lines = relic_rank_lines(parse_relic_rank(RAW), names, ["seal"])
    text = "\n".join(t for t, _ in lines)

    assert lines[0][0].startswith("Relic giảm gãy (@+8/+12/+16, chỉ hiệu ứng cố định):")
    assert "kệ đầy" in lines[0][0]
    assert "  Kìm Vảy Rồng: gãy 5.0%->3.8% | 15.0%->11.3% | 25.0%->18.8%" in text
    assert "★ Nút Thắt Đen: gãy 5.0%->4.3%" in text
    assert "Đai Sắt" in text and "bỏ đi" in text
    assert "Có điều kiện (không mô phỏng được):" in text
    assert "Bùa Cháy Sém" in text
    assert "coin" not in text


def test_section_empty_without_simulation():
    assert relic_rank_lines(RelicRank(), {}, []) == []
    assert relic_rank_lines(None, {}, []) == []


def test_conditional_ids_cover_requested_relics():
    assert {"brace", "repair", "star", "thread", "cornerstone", "insurance", "phoenix",
            "spine"} <= set(CONDITIONAL_IDS)


def test_star_step_mentions_reduction_at_12():
    text, tag = star_step(parse_relic_rank(RAW), ["nail", "seal"], {"seal": "Nút Thắt Đen"})

    assert text.startswith("★ Mua Nút Thắt Đen: giảm gãy @+12 15.0%->12.8%")
    assert "kệ đầy" in text
    assert tag == "good"
    assert star_step(parse_relic_rank(RAW), ["coin"], {}) is None
