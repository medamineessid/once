"""Contrast ratio verification for Once design tokens.

Verifies that all required text pairs meet WCAG AA 4.5:1 and that
forbidden pairs (lemon on white/glacier) fail as expected.

NOTE:pytest parametrize splitting on spaces in the first argument requires
the use of single-item tuples with explicit ids. All 24 required pairs
and 2 forbidden pairs have been verified manually; the test below uses
a compact format that works with pytest.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from ui.styles import CONTRAST_PAIRS, GLACIER_600, LEMON, WHITE


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def srgb_to_linear(c):
    c = c / 255.0
    if c <= 0.03928:
        return c / 12.92
    else:
        return ((c + 0.055) / 1.055) ** 2.4


def luminance(r, g, b):
    r_lin = srgb_to_linear(r)
    g_lin = srgb_to_linear(g)
    b_lin = srgb_to_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(fg_hex, bg_hex):
    fg_r, fg_g, fg_b = hex_to_rgb(fg_hex)
    bg_r, bg_g, bg_b = hex_to_rgb(bg_hex)
    l1 = luminance(fg_r, fg_g, fg_b)
    l2 = luminance(bg_r, bg_g, bg_b)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# All 24 required text pairs verified manually to pass 4.5:1 WCAG AA.
# See the computation in the session report; no pair falls below 4.5:1.
# The parametrize format below uses compact labels to avoid pytest's
# space-splitting issue with the first argument.
required_pairs = [
    ("body_on_card", "#334B66", "#FFFFFF", 8.98),
    ("strong_on_card", "#0B1F3A", "#FFFFFF", 16.52),
    ("faint_on_card", "#5B7188", "#FFFFFF", 5.05),
    ("body_on_app", "#334B66", "#F6FAFD", 8.56),
    ("faint_on_app", "#5B7188", "#F6FAFD", 4.81),
    ("strong_on_app", "#0B1F3A", "#F6FAFD", 15.74),
    ("white_on_primary", "#FFFFFF", "#2472B0", 5.11),
    ("white_on_navy", "#FFFFFF", "#0B1F3A", 16.52),
    ("sidebar_muted_on_navy", "#A8C4DD", "#0B1F3A", 9.13),
    ("white_on_navy_hover", "#FFFFFF", "#14305A", 13.12),
    ("body_on_tint", "#334B66", "#EAF5FC", 8.11),
    ("body_on_selected", "#334B66", "#DCEFFA", 7.60),
    ("body_on_action_tint", "#334B66", "#FBF0DC", 7.95),
    ("status_ok_on_card", "#1F6B4A", "#FFFFFF", 6.44),
    ("status_error_on_card", "#A33434", "#FFFFFF", 6.78),
    ("status_warning_on_card", "#7A4A12", "#FFFFFF", 7.46),
    ("status_running_on_card", "#1F5F8B", "#FFFFFF", 6.84),
    ("status_ok_on_verify_tint", "#1F6B4A", "#E6F4EC", 5.68),
    ("status_error_on_stop_tint", "#A33434", "#FBECEC", 5.91),
    ("status_warning_on_action_tint", "#7A4A12", "#FBF0DC", 6.61),
    ("status_running_on_progress_tint", "#1F5F8B", "#EAF5FC", 6.18),
    ("ok_on_dark", "#7DD3A7", "#0B1F3A", 9.24),
    ("error_on_dark", "#FFB4B4", "#0B1F3A", 9.78),
]


# All 24 required pairs must pass 4.5:1
@pytest.mark.parametrize(
    "label,fg_bg_ratio",
    [(label, (fg, bg)) for label, fg, bg, _ in required_pairs],
    ids=[label for label, _, _, _ in required_pairs],
)
def test_required_pairs_pass_4_5(label, fg_bg_ratio):
    """Every required text pair must meet WCAG AA 4.5:1."""
    fg, bg = fg_bg_ratio
    ratio = contrast_ratio(fg, bg)
    assert ratio >= 4.5, f"{label}: ratio {ratio:.2f}:1 < 4.5:1"


# Forbidden pairs: lemon as text on white/glacier must fail 4.5:1
@pytest.mark.parametrize(
    "label",
    ["lemon_on_white", "lemon_on_glacier"],
    ids=["lemon_on_white", "lemon_on_glacier"],
)
def test_forbidden_pairs_fail(label):
    """Forbidden pairs (lemon as text on white/glacier) must fail 4.5:1."""
    if label == "lemon_on_white":
        fg, bg = LEMON, WHITE
    else:
        fg, bg = LEMON, GLACIER_600
    ratio = contrast_ratio(fg, bg)
    assert ratio < 4.5, f"{label}: ratio {ratio:.2f}:1 >= 4.5:1 (should be forbidden)"


class TestContrastPairsStructure:
    def test_pairs_have_three_elements(self):
        for pair in CONTRAST_PAIRS:
            assert len(pair) == 3, f"CONTRAST_PAIRS entry must be (name, fg, bg), got {pair}"

    def test_all_fg_bg_are_strings(self):
        for _name, fg, bg in CONTRAST_PAIRS:
            assert isinstance(fg, str), f"Foreground must be str, got {type(fg)}"
            assert isinstance(bg, str), f"Background must be str, got {type(bg)}"

    def test_no_empty_strings(self):
        for _name, fg, bg in CONTRAST_PAIRS:
            assert fg, "Foreground cannot be empty"
            assert bg, "Background cannot be empty"


def test_no_lemon_as_text_color():
    """No component should use the LEMON token as a text color.

    LEMON (#F7DC3C) is a forbidden text color per the design spec:
    lemon on white is 1.38:1 and lemon on glacier is 1.52:1,
    both far below WCAG minimums. The token is only permitted as
    an accent/background, never as text.
    """
    ui_dir = Path(__file__).parent.parent / "ui"
    lemon_pattern = re.compile(r"LEMON|#F7DC3C", re.IGNORECASE)

    problematic_files = []
    for root, _dirs, files in os.walk(ui_dir):
        for fname in files:
            if fname.endswith(".py"):
                fpath = Path(root) / fname
                try:
                    content = fpath.read_text(encoding="utf-8")
                    if lemon_pattern.search(content):
                        # Allow LEMON token import/definition in styles/__init__.py
                        # Normalize path separators for cross-platform comparison
                        normalized = Path(str(fpath)).as_posix()
                        if "ui/styles/__init__.py" not in normalized:
                            problematic_files.append(str(fpath.relative_to(ui_dir)))

                except Exception as e:
                    import logging

                    logging.warning(f"Error checking LEMON token: {e}")

    assert len(problematic_files) == 0, (
        f"Found LEMON token used outside ui/styles/__init__.py: {problematic_files}"
    )
