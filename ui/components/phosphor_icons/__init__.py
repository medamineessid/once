"""Phosphor Icons for Once — MIT licensed, bundled SVG assets.

Icons live in ``assets/icons/bold`` and ``assets/icons/fill`` (downloaded from
phosphor-icons/core, MIT). Every icon is rendered through QSvgRenderer at the
pixmap's device pixel size, so it stays sharp at 100%, 125% and 150% scaling.

Weights: Bold is used for inactive sidebar/toolbar items, Fill for active ones.
No emoji, one icon set only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

#: Repository-level assets directory (never write here at runtime).
ICON_ROOT: Final = Path(__file__).resolve().parents[3] / "assets" / "icons"

#: Logical (device-independent) sizes used by the design.
SIDEBAR_ICON_LOGICAL_SIZE: Final = 24
BUTTON_ICON_LOGICAL_SIZE: Final = 20
EMPTY_STATE_ICON_LOGICAL_SIZE: Final = 48

#: Names required by the design. Each must exist in both weights.
REQUIRED_ICONS: Final = (
    "house",
    "rows-arrow-up-down",
    "pulse",
    "sliders",
    "record-circle",
    "plus",
    "play",
    "arrow-right",
    "trash",
    "pencil",
    "check",
    "x",
    "warning",
    "clock",
)

_WEIGHT_DIRS: Final = {"Bold": "bold", "Fill": "fill"}


def icon_path(icon_name: str, weight: str = "Bold") -> Path:
    """Return the bundled SVG path for an icon name and weight."""
    folder = _WEIGHT_DIRS.get(weight)
    if folder is None:
        raise ValueError(f"unknown icon weight {weight!r}; use Bold or Fill")
    return ICON_ROOT / folder / f"{icon_name}.svg"


def _dpr() -> float:
    app = QApplication.instance()
    if app is None:
        return 1.0
    return float(app.devicePixelRatio())


def render_icon_pixmap(
    icon_name: str,
    weight: str = "Bold",
    logical_size: int = BUTTON_ICON_LOGICAL_SIZE,
    color: QColor | str | None = None,
    device_pixel_ratio: float | None = None,
) -> QPixmap:
    """Render one bundled Phosphor icon into a DPI-correct QPixmap.

    The returned pixmap's pixel size is ``logical_size * device_pixel_ratio``.
    A colour tint recolours the glyph (keeping its alpha) rather than painting
    a solid square over it.
    """
    ratio = _dpr() if device_pixel_ratio is None else float(device_pixel_ratio)
    pixel_size = max(1, round(logical_size * ratio))

    path = icon_path(icon_name, weight)
    pixmap = QPixmap(pixel_size, pixel_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    if not path.is_file():
        # Missing asset stays visually empty rather than drawing a fake icon.
        return pixmap

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer = QSvgRenderer(str(path))
    renderer.render(painter, QRectF(0, 0, pixel_size, pixel_size))
    if color is not None:
        # "currentColor" SVGs render black; recolour by keeping the alpha mask.
        tint = QColor(color) if not isinstance(color, QColor) else color
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), tint)
    painter.end()
    return pixmap


def opaque_fraction(pixmap: QPixmap) -> float:
    """Fraction of pixels with any alpha — used by the icon render test."""
    image = pixmap.toImage()
    if image.width() == 0 or image.height() == 0:
        return 0.0
    drawn = 0
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 0:
                drawn += 1
    return drawn / float(image.width() * image.height())
