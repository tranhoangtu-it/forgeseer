from forgeseer.dpi import BASE_DPI, clamp_dpi, font_pixels, scale_for


def test_font_pixels_follow_monitor_dpi():
    assert font_pixels(10, 96) == -13
    assert font_pixels(10, 120) == -17   # 125%
    assert font_pixels(10, 144) == -20   # 150%
    assert font_pixels(8, 192) == -21    # 200%
    assert font_pixels(1, 10) == -1      # never zero (Tk would treat 0 as default size)


def test_scale_and_clamp():
    assert scale_for(96) == 1.0 and scale_for(144) == 1.5
    assert clamp_dpi(144) == 144
    assert clamp_dpi(0) == BASE_DPI and clamp_dpi(None) == BASE_DPI
    assert clamp_dpi(5000) == BASE_DPI and clamp_dpi(10, fallback=120) == 120
