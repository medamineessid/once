"""The Home hero: a sky block with clipped Anton lines and two real actions.

The display lines are uppercase Anton at 128px in an 0.85 line box. The second
line is deliberately positioned so its final glyph runs past the panel edge and
is cropped by it; ``second_line_cropped()`` lets a test measure that instead of
trusting the screenshot.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.components.buttons import ActionButton
from ui.components.phosphor_icons import render_icon_pixmap
from ui.styles import (
    BAND_CROP_PX,
    CIRCLE_BUTTON_PX,
    DISPLAY_FONT,
    DISPLAY_LINE_HEIGHT,
    NAVY,
    SPACING_LG,
    SPACING_SM,
    SPACING_XL,
    SPACING_XS,
    TYPE_HERO_PX,
    TYPE_HOME_SUBTITLE_PX,
    UI_FONT,
)


class MicroLabel(QLabel):
    """A small uppercase label carrying a real count."""

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        *,
        on_hero: bool = False,
    ) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("heroMicro" if on_hero else "pageMicro")


def hero_font(pixel_size: int = TYPE_HERO_PX) -> QFont:
    """The display face at the hero size."""
    font = QFont(DISPLAY_FONT)
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.Normal)
    return font


def hero_line_height(pixel_size: int = TYPE_HERO_PX) -> int:
    """The 0.85 line box that makes the two lines read as one block."""
    return round(pixel_size * DISPLAY_LINE_HEIGHT)


def hero_line_width(text: str, pixel_size: int = TYPE_HERO_PX) -> int:
    """Rendered width of one display line (plus the deliberate crop)."""
    metrics = QFontMetrics(hero_font(pixel_size))
    return metrics.horizontalAdvance(text.upper()) + BAND_CROP_PX


class _ClippedLines(QWidget):
    """Holds the two display lines and clips whatever runs past its edge."""

    def __init__(self, lines: tuple[tuple[str, bool], ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("heroLines")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._labels: list[QLabel] = []
        self._line_height = hero_line_height()
        self.setFixedHeight(self._line_height * len(lines))
        for index, (text, accent) in enumerate(lines):
            label = QLabel(text.upper(), self)
            label.setObjectName("heroLineAccent" if accent else "heroLine")
            label.setFont(hero_font())
            label.setWordWrap(False)
            label.setFixedHeight(self._line_height)
            label.setFixedWidth(hero_line_width(text))
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            label.move(0, index * self._line_height)
            self._labels.append(label)

    @property
    def labels(self) -> list[QLabel]:
        """The display labels, in order."""
        return self._labels

    def line_rects(self) -> list[QRect]:
        """Geometry of each display line inside the clipping host."""
        return [label.geometry() for label in self._labels]

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt name
        super().resizeEvent(event)
        # The last line is right-hung past the edge, so its glyph is cropped.
        if len(self._labels) > 1:
            last = self._labels[-1]
            last.move(self.width() - last.width() + BAND_CROP_PX, last.y())

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt name
        return QSize(0, self._line_height * len(self._labels))


class Hero(QFrame):
    """Sky block: micro label, cropped display lines, subtitle, two actions."""

    record_requested = Signal()
    build_requested = Signal()

    def __init__(
        self,
        micro_text: str,
        lines: tuple[tuple[str, bool], ...],
        *,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("heroPanel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        outer.setSpacing(SPACING_SM)

        self.micro_label = MicroLabel(micro_text, self, on_hero=True)
        outer.addWidget(self.micro_label)

        self._lines = _ClippedLines(lines, self)
        outer.addWidget(self._lines)
        self.line_labels = self._lines.labels

        self._subtitle = QLabel(subtitle, self)
        self._subtitle.setObjectName("heroSubtitle")
        self._subtitle.setWordWrap(False)
        subtitle_font = QFont(UI_FONT)
        subtitle_font.setPixelSize(TYPE_HOME_SUBTITLE_PX)
        self._subtitle.setFont(subtitle_font)
        outer.addWidget(self._subtitle)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(SPACING_LG)

        self.record_button = QPushButton("Record", self)
        self.record_button.setObjectName("circleButton")
        self.record_button.setFixedSize(CIRCLE_BUTTON_PX, CIRCLE_BUTTON_PX)
        self.record_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_button.setIcon(self._circle_icon("record"))
        self.record_button.setIconSize(QSize(32, 32))
        self.record_button.clicked.connect(self.record_requested.emit)

        self.build_button = ActionButton("Build", variant="hero", with_arrow=True, parent=self)
        self.build_button.setMinimumWidth(150)
        self.build_button.clicked.connect(self.build_requested.emit)

        actions.addWidget(self.record_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        actions.addWidget(self.build_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        actions.addStretch(1)
        outer.addSpacing(SPACING_XS)
        outer.addLayout(actions)

    def _circle_icon(self, name: str) -> QIcon:
        pixmap = render_icon_pixmap(
            name,
            weight="Fill",
            logical_size=32,
            color=NAVY,
            device_pixel_ratio=self.devicePixelRatioF(),
        )
        return QIcon(pixmap)

    # -------------------------------------------------------------- inspection
    def second_line_cropped(self) -> bool:
        """True when the last display line runs past the clipping host."""
        if len(self.line_labels) < 2:
            return False
        last = self.line_labels[-1]
        return last.geometry().right() > self._lines.rect().right()

    def set_micro(self, text: str) -> None:
        """Update the real count above the display lines."""
        self.micro_label.setText(text.upper())
