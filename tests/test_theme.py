import pytest

from desktop_organizer.core.theme import DARK, LIGHT, Tokens, build_stylesheet, token_names


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("t", [LIGHT, DARK], ids=["light", "dark"])
def test_text_contrast_meets_aa(t: Tokens) -> None:
    for fg in ("text", "text_secondary", "accent", "success", "warning", "error"):
        for bg in ("window", "surface", "surface_alt"):
            assert contrast(getattr(t, fg), getattr(t, bg)) >= 4.5, (fg, bg)
    assert contrast(t.text, t.selection) >= 4.5
    assert contrast(t.on_accent, t.accent) >= 4.5
    assert contrast(t.on_error, t.error) >= 4.5


@pytest.mark.parametrize("t", [LIGHT, DARK], ids=["light", "dark"])
def test_control_borders_meet_non_text_contrast(t: Tokens) -> None:
    assert contrast(t.control_border, t.surface) >= 3.0
    assert contrast(t.accent, t.surface) >= 3.0  # focus indicator


def test_stylesheet_uses_tokens_only() -> None:
    sheet = build_stylesheet(LIGHT)
    import re

    colors = set(re.findall(r"#[0-9A-Fa-f]{6}", sheet))
    allowed = {getattr(LIGHT, name) for name in token_names()}
    assert colors <= allowed
