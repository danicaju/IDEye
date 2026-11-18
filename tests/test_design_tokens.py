from ideye.ui import design_tokens as tk


def test_only_two_radii():
    assert tk.ALLOWED_RADII == (8, 14)


def test_single_cyan_accent():
    r, g, b = tk.ACCENT_RGB
    assert tk.ACCENT_HEX.lstrip("#").upper() == f"{r:02X}{g:02X}{b:02X}"
    assert b > r and g > r  # cyan family


def test_duration_respects_reduced_motion():
    assert tk.duration(80, True) == 0
    assert tk.duration(80, False) == 80
