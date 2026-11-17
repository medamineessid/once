"""Print every color token and the contrast ratio of each text/background pair."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ui.styles as s


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(value: str) -> float:
    channels = []
    for c in hex_to_rgb(value):
        x = c / 255.0
        channels.append(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


COLOR_TOKENS = [
    "BG_APP",
    "BG_CANVAS",
    "DOT_GRID",
    "SURFACE",
    "SURFACE_ALT",
    "BORDER",
    "BORDER_STRONG",
    "ACCENT",
    "ACCENT_TEXT",
    "ACCENT_SOFT",
    "PRIMARY_BTN",
    "TEXT_STRONG",
    "TEXT_BODY",
    "TEXT_FAINT",
    "TEXT_SIDEBAR",
    "TEXT_SIDEBAR_HOVER",
    "GLACIER_600",
    "GLACIER_BLUE",
    "NAVY",
    "WHITE",
    "HERO_BLUE",
    "HERO_BLUE_CONTRAST",
    "LEMON",
]

PAIRS = [
    ("TEXT_STRONG", "SURFACE", 4.5),
    ("TEXT_BODY", "SURFACE", 4.5),
    ("TEXT_BODY", "SURFACE_ALT", 4.5),
    ("ACCENT_TEXT", "ACCENT_SOFT", 4.5),
    ("WHITE", "HERO_BLUE_CONTRAST", 4.5),
    ("NAVY", "HERO_BLUE_CONTRAST", 4.5),
    ("LEMON", "HERO_BLUE_CONTRAST", 3.0),
    ("WHITE", "GLACIER_BLUE", 4.5),
]


def main() -> int:
    print("COLOR TOKENS")
    for name in COLOR_TOKENS:
        print(f"  {name:<20} {getattr(s, name)}")
    print("\nCONTRAST PAIRS (required minimum in brackets)")
    failed = False
    for fg, bg, minimum in PAIRS:
        ratio = contrast(getattr(s, fg), getattr(s, bg))
        verdict = "PASS" if ratio >= minimum else "FAIL"
        if ratio < minimum:
            failed = True
        print(f"  {fg:<18} on {bg:<20} = {ratio:5.2f}:1  need {minimum}:1  {verdict}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
