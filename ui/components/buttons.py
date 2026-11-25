"""One button system, with the design's hover and press motion.

Primary is a lemon fill with navy text, secondary is an outlined navy control,
destructive is an outlined red control, hero is the outlined white control used
only on the sky hero band. There is no other button colour in the app.

Hover shifts the trailing arrow four pixels toward the edge and changes the fill
and border through the stylesheet; press darkens through ``:pressed`` and moves
the arrow one pixel back inside. Nothing is ever painted outside the widget
rectangle: an earlier version scaled the painted button about its centre, which
was clipped by the widget and cut the border on hover and press. The shift
animates over 120ms and is applied instantly when Windows animations are off.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from ui.components.phosphor_icons import render_icon_pixmap
from ui.motion import animations_enabled
from ui.styles import (
    ARROW_SHIFT_PX,
    DURATION_HOVER_MS,
    NAVY,
    SPACING_SM,
    STATUS_ERROR,
    WHITE,
)

_VARIANT_OBJECT_NAMES = {
    "primary": "primaryActionButton",
    "secondary": "secondaryActionButton",
    "destructive": "dangerButton",
    # Outlined white control for the sky hero band only: navy-on-sky is below
    # 4.5:1, so the hero uses the white outline instead.
    "hero": "heroSecondaryButton",
    "link": "linkActionButton",
    "ghost": "ghostButton",
}

_ARROW_INSET = SPACING_SM + 2
_ARROW_LOGICAL_SIZE = 16
#: How far the arrow moves inward while the button is pressed.
_PRESS_INSET_PX = 1


class ActionButton(QPushButton):
    """A themed button with an optional shifted arrow and no geometric scaling."""

    def __init__(
        self,
        text: str,
        *,
        variant: str = "primary",
        with_arrow: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._variant = variant if variant in _VARIANT_OBJECT_NAMES else "primary"
        self.setObjectName(_VARIANT_OBJECT_NAMES[self._variant])
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._arrow_animation: QPropertyAnimation | None = None
        self._arrow_label: QLabel | None = None
        self._pressed = False
        if with_arrow:
            self._arrow_label = QLabel(self)
            self._arrow_label.setObjectName("buttonArrow")
            self._arrow_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            pixmap = render_icon_pixmap(
                "arrow-right",
                weight="Bold",
                logical_size=_ARROW_LOGICAL_SIZE,
                color=self._arrow_colour(),
                device_pixel_ratio=self.devicePixelRatioF(),
            )
            self._arrow_label.setPixmap(pixmap)
            self._arrow_label.setFixedSize(QSize(_ARROW_LOGICAL_SIZE, _ARROW_LOGICAL_SIZE))

    # ----------------------------------------------------------------- arrow
    def _arrow_colour(self) -> QColor:
        if self._variant == "destructive":
            return QColor(STATUS_ERROR)
        if self._variant == "hero":
            return QColor(WHITE)
        return QColor(NAVY)

    def arrow_position(self, *, shifted: bool, pressed: bool = False) -> QPoint:
        """Where the trailing arrow sits, always inside the button rectangle."""
        offset = ARROW_SHIFT_PX if shifted else 0
        if pressed:
            offset -= _PRESS_INSET_PX
        x = self.width() - _ARROW_LOGICAL_SIZE - _ARROW_INSET + offset
        y = (self.height() - _ARROW_LOGICAL_SIZE) // 2
        right_limit = max(0, self.width() - _ARROW_LOGICAL_SIZE)
        return QPoint(min(max(0, x), right_limit), max(0, y))

    def _place_arrow(self, *, shifted: bool) -> None:
        if self._arrow_label is None:
            return
        self._arrow_label.move(self.arrow_position(shifted=shifted, pressed=self._pressed))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt name
        super().resizeEvent(event)
        self._place_arrow(shifted=self.underMouse())

    # ----------------------------------------------------------------- motion
    def _shift_arrow(self, shifted: bool) -> None:
        if self._arrow_label is None:
            return
        target = self.arrow_position(shifted=shifted, pressed=self._pressed)
        if not animations_enabled() or not self.isVisible():
            self._arrow_label.move(target)
            return
        animation = QPropertyAnimation(self._arrow_label, b"pos", self)
        animation.setDuration(DURATION_HOVER_MS)
        animation.setStartValue(self._arrow_label.pos())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._arrow_animation = animation
        animation.start()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt name
        if self.isEnabled():
            self._shift_arrow(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt name
        self._shift_arrow(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt name
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._shift_arrow(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt name
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self._shift_arrow(self.underMouse())
        super().mouseReleaseEvent(event)


def action_button(text: str, variant: str = "primary", *, with_arrow: bool = False) -> ActionButton:
    """Small factory so pages do not repeat the variant names."""
    return ActionButton(text, variant=variant, with_arrow=with_arrow)
