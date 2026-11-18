"""One button system, with the design's hover and press motion.

Primary is a lemon fill with navy text, secondary is an outlined navy control,
destructive is an outlined red control, hero is the outlined white control used
only on the sky hero band. There is no other button colour in the app.

Hover shifts the trailing arrow by four pixels and grows the button by 3%;
press shrinks it to 97%. Both are applied instantly (no animation) when Windows
animations are off. The scale is painted, never applied to the geometry, so a
hovering button cannot reflow the layout around it.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QWidget,
)

from ui.components.phosphor_icons import render_icon_pixmap
from ui.motion import animations_enabled
from ui.styles import (
    ARROW_SHIFT_PX,
    DURATION_HOVER_MS,
    HOVER_SCALE,
    NAVY,
    PRESS_SCALE,
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


class ActionButton(QPushButton):
    """A themed button with an optional shifted arrow and painted scale."""

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
        self._scale = 1.0
        self._scale_animation: QVariantAnimation | None = None
        self._arrow_animation: QPropertyAnimation | None = None
        self._arrow_label: QLabel | None = None
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

    def arrow_position(self, *, shifted: bool) -> QPoint:
        """Where the trailing arrow sits, resting or hovered."""
        offset = ARROW_SHIFT_PX if shifted else 0
        x = self.width() - _ARROW_LOGICAL_SIZE - _ARROW_INSET + offset
        y = (self.height() - _ARROW_LOGICAL_SIZE) // 2
        return QPoint(max(0, x), max(0, y))

    def _place_arrow(self, *, shifted: bool) -> None:
        if self._arrow_label is None:
            return
        self._arrow_label.move(self.arrow_position(shifted=shifted))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt name
        super().resizeEvent(event)
        self._place_arrow(shifted=self.underMouse())

    # ----------------------------------------------------------------- motion
    @property
    def scale(self) -> float:
        """The painted scale (1.0 at rest)."""
        return self._scale

    def _set_scale(self, value: float) -> None:
        self._scale = float(value)
        self.update()

    def animate_scale(self, target: float) -> None:
        """Move the painted scale to ``target``, instantly when motion is off."""
        if self._scale_animation is not None:
            self._scale_animation.stop()
            self._scale_animation = None
        if not animations_enabled() or not self.isVisible():
            self._set_scale(target)
            return
        animation = QVariantAnimation(self)
        animation.setDuration(DURATION_HOVER_MS)
        animation.setStartValue(self._scale)
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(self._on_scale_value)
        self._scale_animation = animation
        animation.start()

    def _on_scale_value(self, value: object) -> None:
        try:
            self._set_scale(float(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return

    def _shift_arrow(self, shifted: bool) -> None:
        if self._arrow_label is None:
            return
        target = self.arrow_position(shifted=shifted)
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
            self.animate_scale(HOVER_SCALE)
            self._shift_arrow(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt name
        self.animate_scale(1.0)
        self._shift_arrow(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt name
        if event.button() == Qt.MouseButton.LeftButton:
            self.animate_scale(PRESS_SCALE)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt name
        if event.button() == Qt.MouseButton.LeftButton:
            self.animate_scale(HOVER_SCALE if self.underMouse() else 1.0)
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt name
        if abs(self._scale - 1.0) < 0.001:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        centre = self.rect().center()
        painter.translate(centre)
        painter.scale(self._scale, self._scale)
        painter.translate(-centre)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, self)
        painter.end()


def action_button(text: str, variant: str = "primary", *, with_arrow: bool = False) -> ActionButton:
    """Small factory so pages do not repeat the variant names."""
    return ActionButton(text, variant=variant, with_arrow=with_arrow)
