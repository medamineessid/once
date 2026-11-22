"""Small, meaning-only motion for the Once shell.

Qt style sheets cannot animate, so the few transitions that carry meaning are
driven by QPropertyAnimation. Every duration and offset comes from ui.styles;
Windows' "show animations" preference is honoured.
"""

from __future__ import annotations

import sys
from ctypes import ArgumentError, byref, c_int
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from ui.styles import (
    DIALOG_SCALE,
    DURATION_DIALOG_MS,
    DURATION_PAGE_MS,
    DURATION_RUNNING_PULSE_MS,
    DURATION_STAGGER_MS,
    PAGE_SLIDE_PX,
    STAGGER_LIMIT,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QDialog

_SPI_GETCLIENTAREAANIMATION = 0x1042


def animations_enabled() -> bool:
    """Return the Windows animation preference, defaulting to enabled."""
    if sys.platform != "win32":
        return True
    try:
        from ctypes import windll

        enabled = c_int(1)
        ok = windll.user32.SystemParametersInfoW(_SPI_GETCLIENTAREAANIMATION, 0, byref(enabled), 0)
        return bool(enabled.value) if ok else True
    except (AttributeError, OSError, ArgumentError):
        return True


def _out_curve() -> QEasingCurve:
    """A gentle deceleration close to cubic-bezier(0.2, 0, 0, 1)."""
    return QEasingCurve(QEasingCurve.Type.OutCubic)


def _opacity_effect(widget: QWidget) -> QGraphicsOpacityEffect:
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    return effect


def _remember(widget: QWidget, animation: QVariantAnimation) -> None:
    # Keeping a Python reference prevents Qt from collecting a running
    # animation before it reaches its end state.
    widget._once_motion_animation = animation


def fade_slide(
    widget: QWidget,
    *,
    offset: int = PAGE_SLIDE_PX,
    duration: int = DURATION_PAGE_MS,
) -> None:
    """Fade a page in while moving it up by a few pixels."""
    if not animations_enabled() or not widget.isVisible():
        return
    existing = widget.graphicsEffect()
    if existing is not None:
        return
    effect = _opacity_effect(widget)
    start = widget.pos()
    widget.move(start.x(), start.y() + offset)
    group = QParallelAnimationGroup(widget)
    opacity = QPropertyAnimation(effect, b"opacity", group)
    opacity.setDuration(duration)
    opacity.setStartValue(0.0)
    opacity.setEndValue(1.0)
    opacity.setEasingCurve(_out_curve())
    slide = QPropertyAnimation(widget, b"pos", group)
    slide.setDuration(duration)
    slide.setStartValue(QPoint(start.x(), start.y() + offset))
    slide.setEndValue(start)
    slide.setEasingCurve(_out_curve())

    def _finish() -> None:
        widget.move(start)
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)

    group.finished.connect(_finish)
    group.addAnimation(opacity)
    group.addAnimation(slide)
    _remember(widget, group)
    group.start()


def fade_item(widget: QWidget, index: int) -> None:
    """Reveal one list row with a short, capped stagger."""
    if not animations_enabled():
        return
    delay = min(max(index, 0), STAGGER_LIMIT) * DURATION_STAGGER_MS
    QTimer.singleShot(delay, lambda: fade_slide(widget, offset=4, duration=180))


def reveal_lines(
    labels: list[QWidget],
    *,
    offset: int = 16,
    duration: int = 280,
    stagger: int = DURATION_STAGGER_MS,
) -> None:
    """Reveal display lines one after another: 16px slide-up, 280ms, 60ms apart.

    Returns instantly, touching nothing, when animations are disabled.
    """
    if not animations_enabled():
        return
    for index, label in enumerate(labels):
        delay = index * stagger

        def _start(target: QWidget = label) -> None:
            fade_slide(target, offset=offset, duration=duration)

        QTimer.singleShot(delay, _start)


def fade_dialog(dialog: QDialog) -> None:
    """Fade and slightly scale a dialog without delaying input."""
    if not animations_enabled():
        return
    original = dialog.geometry()
    if original.width() <= 0 or original.height() <= 0:
        return
    shrink = int(original.width() * DIALOG_SCALE)
    shrink_y = int(original.height() * DIALOG_SCALE)
    small = original.adjusted(shrink, shrink_y, -shrink, -shrink)
    dialog.setWindowOpacity(0.0)
    dialog.setGeometry(small)
    group = QParallelAnimationGroup(dialog)
    opacity = QPropertyAnimation(dialog, b"windowOpacity", group)
    opacity.setDuration(DURATION_DIALOG_MS)
    opacity.setStartValue(0.0)
    opacity.setEndValue(1.0)
    opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
    grow = QPropertyAnimation(dialog, b"geometry", group)
    grow.setDuration(DURATION_DIALOG_MS)
    grow.setStartValue(small)
    grow.setEndValue(original)
    grow.setEasingCurve(_out_curve())
    group.addAnimation(opacity)
    group.addAnimation(grow)
    _remember(dialog, group)
    group.start()


def pulse(widget: QWidget) -> QPropertyAnimation | None:
    """Start the one permitted continuous animation: a running indicator."""
    if not animations_enabled():
        return None
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.45)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(DURATION_RUNNING_PULSE_MS)
    animation.setStartValue(0.45)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.InOutSine)
    animation.setLoopCount(-1)
    animation.start()
    return animation
