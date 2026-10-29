"""WCAG contrast helpers — the token set must pass 4.5:1 (test-enforced)."""

from __future__ import annotations

from dataclasses import dataclass


def _linear_channel(value: float) -> float:
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance of a #RRGGBB color."""
    text = hex_color.lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Expected a #RRGGBB color, got {hex_color!r}")
    channels = (
        int(text[0:2], 16) / 255,
        int(text[2:4], 16) / 255,
        int(text[4:6], 16) / 255,
    )
    linear = tuple(_linear_channel(channel) for channel in channels)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two #RRGGBB colors."""
    light = max(relative_luminance(foreground), relative_luminance(background))
    dark = min(relative_luminance(foreground), relative_luminance(background))
    return (light + 0.05) / (dark + 0.05)


@dataclass(frozen=True)
class ContrastPair:
    """One foreground/background pair with the surface it is used on."""

    name: str
    foreground: str
    background: str


def failing_pairs(
    pairs: tuple[ContrastPair, ...], minimum: float = 4.5
) -> tuple[ContrastPair, ...]:
    """Return the pairs that are below the minimum contrast ratio."""
    return tuple(
        pair for pair in pairs if contrast_ratio(pair.foreground, pair.background) < minimum
    )
