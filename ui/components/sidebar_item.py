"""A painted sidebar item: 24px Phosphor icon, 14px gap, lemon active pill.

Qt's tool button lays the icon and its text out with a style-dependent gap, so
the design's fixed 14px gap cannot be expressed in the stylesheet. This widget
paints the row itself: the icon rect and the text rect are computed by one pure
function so ``tests/test_design_v4.py`` can measure the gap instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolButton, QWidget

from ui.components.phosphor_icons import render_icon_pixmap
from ui.styles import (
    SIDEBAR_ACTIVE_BG,
    SIDEBAR_ACTIVE_TEXT,
    SIDEBAR_BG,
    SIDEBAR_HOVER_BG,
    SIDEBAR_ICON_GAP_PX,
    SIDEBAR_ICON_PX,
    SIDEBAR_ITEM_HEIGHT,
    SIDEBAR_ITEM_INSET,
    SIDEBAR_PILL_RADIUS,
    SIDEBAR_TEXT,
    SIDEBAR_TEXT_HOVER,
    TYPE_BODY_PX,
    UI_FONT,
)


@dataclass(frozen=True)
class SidebarMetrics:
    """The measured geometry of one sidebar row."""

    icon_size: int
    gap: int
    inset: int
    height: int
    radius: int


def sidebar_metrics() -> SidebarMetrics:
    """Return the sidebar row geometry from the design tokens."""
    return SidebarMetrics(
        icon_size=SIDEBAR_ICON_PX,
        gap=SIDEBAR_ICON_GAP_PX,
        inset=SIDEBAR_ITEM_INSET,
        height=SIDEBAR_ITEM_HEIGHT,
        radius=SIDEBAR_PILL_RADIUS,
    )


def sidebar_item_layout(width: int, height: int) -> tuple[QRect, QRect]:
    """Split a row into (icon rect, text rect) using the token metrics."""
    metrics = sidebar_metrics()
    top = (height - metrics.icon_size) // 2
    icon = QRect(metrics.inset, top, metrics.icon_size, metrics.icon_size)
    text_left = icon.right() + 1 + metrics.gap
    text = QRect(text_left, 0, max(0, width - text_left - metrics.inset), height)
    return icon, text


class SidebarItem(QToolButton):
    """One navigation row drawn on the navy rail."""

    def __init__(
        self,
        text: str,
        object_name: str,
        icon_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setObjectName(object_name)
        self._icon_name = icon_name
        self._hover = False
        self.setCheckable(True)
        self.setAutoExclusive(False)
        self.setAutoRepeat(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        self.setFixedHeight(SIDEBAR_ITEM_HEIGHT)
        # Every row spans the rail: a narrow row beside a wide one made the
        # active pill and the focus outline disagree about the row's edges.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._keyboard_focus = False
        self._text_font = QFont(UI_FONT)
        self._text_font.setPixelSize(TYPE_BODY_PX)
        self._text_font.setWeight(QFont.Weight.DemiBold)
        # The widget's own font is the painted font, so measurements (and the
        # --diagnose output) report what is actually drawn.
        self.setFont(self._text_font)

    # ------------------------------------------------------------- geometry
    def icon_rect(self) -> QRect:
        """The icon rectangle, for measurement tests."""
        return sidebar_item_layout(self.width(), self.height())[0]

    def text_rect(self) -> QRect:
        """The label rectangle, for measurement tests."""
        return sidebar_item_layout(self.width(), self.height())[1]

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt name
        metrics = sidebar_metrics()
        width = metrics.inset * 2 + metrics.icon_size + metrics.gap
        width += self.fontMetrics().horizontalAdvance(self.text())
        return QSize(width, metrics.height)

    # --------------------------------------------------------------- events
    def focusInEvent(self, event) -> None:  # noqa: N802 - Qt name
        """Only keyboard focus draws the outline.

        A click focuses the row too, but the checked pill already says where you
        are; drawing an outline as well made one row look like two states.
        """
        reason = event.reason()
        self._keyboard_focus = reason in (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        )
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802 - Qt name
        self._keyboard_focus = False
        self.update()
        super().focusOutEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt name
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt name
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        metrics = sidebar_metrics()
        icon_rect, text_box = sidebar_item_layout(self.width(), self.height())

        checked = self.isChecked()
        painter.fillRect(self.rect(), QColor(SIDEBAR_BG))
        if checked or self._hover:
            pill = QRect(
                0,
                (self.height() - metrics.height) // 2,
                self.width(),
                metrics.height,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(SIDEBAR_ACTIVE_BG if checked else SIDEBAR_HOVER_BG))
            painter.drawRoundedRect(pill, metrics.radius, metrics.radius)

        if checked:
            icon_color = QColor(SIDEBAR_ACTIVE_TEXT)
            text_color = QColor(SIDEBAR_ACTIVE_TEXT)
            weight = QFont.Weight.Bold
        elif self._hover:
            icon_color = QColor(SIDEBAR_TEXT_HOVER)
            text_color = QColor(SIDEBAR_TEXT_HOVER)
            weight = QFont.Weight.DemiBold
        else:
            icon_color = QColor(SIDEBAR_TEXT)
            text_color = QColor(SIDEBAR_TEXT)
            weight = QFont.Weight.DemiBold

        pixmap = render_icon_pixmap(
            self._icon_name,
            weight="Fill" if checked else "Bold",
            logical_size=metrics.icon_size,
            color=icon_color,
            device_pixel_ratio=self.devicePixelRatioF(),
        )
        painter.drawPixmap(icon_rect, pixmap)

        font = QFont(self._text_font)
        font.setWeight(weight)
        painter.setFont(font)
        painter.setPen(QPen(text_color))
        painter.drawText(
            text_box.adjusted(0, 0, 0, 0),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.text(),
        )

        if self._keyboard_focus and not checked:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(SIDEBAR_TEXT_HOVER), 2))
            painter.drawRoundedRect(
                self.rect().adjusted(1, 1, -2, -2), metrics.radius, metrics.radius
            )
        painter.end()
