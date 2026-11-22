"""Colour-blocked page header: micro label, clipped Anton title, one line.

Every page opens with this band. The display title is set at 72px Anton with a
0.85 line box and is deliberately wider than the band, so the last glyph is
cropped by the band's own edge instead of being squeezed into the layout. That
is why the title label has a fixed width derived from the font metrics.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.styles import (
    BAND_CROP_PX,
    DISPLAY_FONT,
    DISPLAY_LINE_HEIGHT,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    SPACING_XS,
    TYPE_CAPTION_PX,
    TYPE_PAGE_TITLE_PX,
    TYPE_SUBTITLE_PX,
    UI_FONT,
)


def display_title_font(pixel_size: int = TYPE_PAGE_TITLE_PX) -> QFont:
    """The display face at the given size, never synthesised bold."""
    font = QFont(DISPLAY_FONT)
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.Normal)
    return font


def display_line_height(pixel_size: int = TYPE_PAGE_TITLE_PX) -> int:
    """The clipped line box (0.85 of the font size)."""
    return round(pixel_size * DISPLAY_LINE_HEIGHT)


def cropped_title_width(text: str, pixel_size: int = TYPE_PAGE_TITLE_PX) -> int:
    """Text width plus the deliberate overflow past the band edge."""
    metrics = QFontMetrics(display_title_font(pixel_size))
    return metrics.horizontalAdvance(text.upper()) + BAND_CROP_PX


class PageBand(QFrame):
    """The shared page header block."""

    def __init__(
        self,
        title: str,
        *,
        micro: str = "",
        description: str = "",
        tone: str = "primary",
        primary_label: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pageBand")
        self.setProperty("bandTone", tone)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        layout.setSpacing(SPACING_XS)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(SPACING_SM)
        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(SPACING_XS)

        self._micro = QLabel(micro.upper(), self)
        self._micro.setObjectName("pageMicro")
        micro_font = QFont(UI_FONT)
        micro_font.setPixelSize(TYPE_CAPTION_PX)
        micro_font.setWeight(QFont.Weight.Bold)
        self._micro.setFont(micro_font)

        self._title = QLabel(title.upper(), self)
        self._title.setObjectName("pageTitle")
        self._title.setFont(display_title_font())
        self._title.setWordWrap(False)
        self._title.setFixedHeight(display_line_height())
        self._title.setFixedWidth(cropped_title_width(title))
        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._description = QLabel(description, self)
        self._description.setObjectName("pageSubtitle")
        self._description.setWordWrap(True)
        description_font = QFont(UI_FONT)
        description_font.setPixelSize(TYPE_SUBTITLE_PX)
        self._description.setFont(description_font)

        align = Qt.AlignmentFlag.AlignLeft
        text_column.addWidget(self._micro, alignment=align)
        text_column.addWidget(self._title, alignment=align)
        if description:
            # No alignment flag here: a word-wrapped label only reports the
            # height of its wrapped text when it is allowed to fill the width.
            text_column.addWidget(self._description)
        header_row.addLayout(text_column, stretch=1)

        self._primary: QPushButton | None = None
        if primary_label is not None:
            from ui.components.buttons import ActionButton

            self._primary = ActionButton(primary_label, variant="primary", parent=self)
            header_row.addWidget(self._primary, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header_row)
        _ = SPACING_MD

    # ------------------------------------------------------------------ API
    @property
    def title_label(self) -> QLabel:
        """The display title label, for tests."""
        return self._title

    @property
    def micro_label(self) -> QLabel:
        """The micro label, for tests."""
        return self._micro

    @property
    def description_label(self) -> QLabel:
        """The guiding line, for tests."""
        return self._description

    @property
    def primary_button(self) -> QPushButton | None:
        """The one primary action, or None."""
        return self._primary

    def set_micro(self, text: str) -> None:
        """Update the real count shown above the title."""
        self._micro.setText(text.upper())

    def set_title(self, title: str) -> None:
        """Update the display title (width follows the new text)."""
        self._title.setText(title.upper())
        self._title.setFixedWidth(cropped_title_width(title))
