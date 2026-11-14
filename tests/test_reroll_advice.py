from forgetax_overlay.reroll_advice import RerollCost, parse_reroll_text, reroll_line


def test_parse_paid_and_free_reroll_text():
    assert parse_reroll_text("390 G") == RerollCost(free=False, price=390)
    assert parse_reroll_text("1,250 G") == RerollCost(free=False, price=1250)
    assert parse_reroll_text("1 LẦN MIỄN PHÍ") == RerollCost(free=True, price=0)
    assert parse_reroll_text("") is None
    assert parse_reroll_text("???") is None


def test_free_reroll_advised_when_nothing_worth_buying():
    text, _ = reroll_line(RerollCost(True, 0), wallet=100, has_good_offer=False)

    assert "miễn phí" in text


def test_paid_reroll_only_when_gold_is_plentiful():
    assert reroll_line(RerollCost(False, 390), wallet=1000, has_good_offer=False) is None
    text, _ = reroll_line(RerollCost(False, 390), wallet=5000, has_good_offer=False)

    assert "390" in text


def test_no_reroll_when_an_offer_improves_ev():
    assert reroll_line(RerollCost(True, 0), wallet=9999, has_good_offer=True) is None
    assert reroll_line(None, wallet=9999, has_good_offer=False) is None
