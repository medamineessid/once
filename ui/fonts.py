"""Bundled font loading for Once.

Fonts are shipped in ``assets/fonts`` (all SIL Open Font License 1.1) so the
app never depends on what is installed on the user's machine. ``load_fonts``
must run after QApplication exists and before any widget is created; it is
idempotent and returns the family names Qt registered.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtGui import QFontDatabase

#: Repository-level fonts directory (read-only at runtime).
FONT_DIR: Final = Path(__file__).resolve().parents[1] / "assets" / "fonts"

#: Font files the UI depends on, in load order.
UI_FONT_FILES: Final = (
    "Inter-Regular.ttf",
    "Inter-Medium.ttf",
    "Inter-SemiBold.ttf",
)
DISPLAY_FONT_FILES: Final = ("Anton-Regular.ttf",)

_LOADED = False
_LOADED_FAMILIES: tuple[str, ...] = ()


def load_fonts(font_dir: Path | None = None) -> tuple[str, ...]:
    """Register every bundled font with Qt and return the family names.

    Safe to call repeatedly; only the first call touches QFontDatabase.
    Missing files are skipped so the app still starts, but the font tests
    assert the required files exist.
    """
    global _LOADED, _LOADED_FAMILIES
    if _LOADED:
        return _LOADED_FAMILIES

    directory = FONT_DIR if font_dir is None else Path(font_dir)
    families: list[str] = []
    for filename in (*UI_FONT_FILES, *DISPLAY_FONT_FILES):
        path = directory / filename
        if not path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        for family in QFontDatabase.applicationFontFamilies(font_id):
            if family not in families:
                families.append(family)

    _LOADED = True
    _LOADED_FAMILIES = tuple(families)
    return _LOADED_FAMILIES


def reset_for_tests() -> None:
    """Forget the load memo so a test can observe a fresh registration."""
    global _LOADED, _LOADED_FAMILIES
    _LOADED = False
    _LOADED_FAMILIES = ()
