"""Color-token discipline test for Once UI.

Every hex color must live in ``ui/styles/__init__.py``. Component files use
the named tokens, never raw ``#RRGGBB`` literals. Geometry values (px offsets
used in paint math) are legitimate and are not scanned here.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from ui.styles import COLOR_TOKENS

_TOKENS_FILE = Path("ui/styles/__init__.py").resolve()
_HEX = re.compile(r"#([a-fA-F0-9]{6})\b")


def _scan_hex_literals() -> list[tuple[str, str]]:
    """Return (file, literal) for every hex color outside the tokens file."""
    found: list[tuple[str, str]] = []
    for root, _dirs, files in os.walk("ui"):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = Path(root) / fname
            if fpath.resolve() == _TOKENS_FILE:
                continue
            content = fpath.read_text(encoding="utf-8")
            for match in _HEX.finditer(content):
                found.append((str(fpath), match.group(0)))
    return found


def test_no_hex_literals_outside_tokens() -> None:
    """No component file may hardcode a hex color."""
    offending = _scan_hex_literals()
    assert offending == [], f"Hardcoded hex colors found outside tokens: {offending}"


def test_tokens_file_defines_every_color_token() -> None:
    """The color-token table is non-empty and well formed."""
    assert len(COLOR_TOKENS) > 0
    for name, value in COLOR_TOKENS.items():
        assert re.fullmatch(r"#[a-fA-F0-9]{6}", value), f"invalid token {name}={value!r}"
