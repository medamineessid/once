"""Tiny original glyphs drawn with QPainter paths.

All icons for the shell and the visual editor come from here (prompt rule:
QPainter paths or authored SVG; no third-party icon sets, no icon fonts).
Every draw function takes a painter and the square area to draw into.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap


def _stroke_pen(width: float) -> QPen:
    pen = QPen(QColor("#4A5568"))
    pen.setWidthF(max(1.4, width))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def icon_pixmap(
    draw_fn,
    size: int = 20,
    color: QColor | None = None,
) -> QPixmap:
    """Render one glyph into a crisp square pixmap."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_fn(painter, QRectF(1.0, 1.0, size - 2.0, size - 2.0), color or QColor("#4A5568"))
    painter.end()
    return pixmap


def draw_home_glyph(painter: QPainter, rect: QRectF, color) -> None:
    """A simple house outline."""
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(color, max(1.4, rect.width() * 0.08)))
    path = QPainterPath()
    path.moveTo(QPointF(rect.left(), rect.center().y()))
    path.lineTo(QPointF(rect.center().x(), rect.top()))
    path.lineTo(QPointF(rect.right(), rect.center().y()))
    path.lineTo(QPointF(rect.right() - rect.width() * 0.08, rect.center().y()))
    path.lineTo(QPointF(rect.right() - rect.width() * 0.08, rect.bottom()))
    path.lineTo(QPointF(rect.left() + rect.width() * 0.08, rect.bottom()))
    path.lineTo(QPointF(rect.left() + rect.width() * 0.08, rect.center().y()))
    path.lineTo(QPointF(rect.left(), rect.center().y()))
    painter.drawPath(path)
    door = QRectF(
        rect.center().x() - rect.width() * 0.09,
        rect.bottom() - rect.height() * 0.3,
        rect.width() * 0.18,
        rect.height() * 0.3,
    )
    painter.drawRect(door)
    painter.restore()


def draw_automations_glyph(painter: QPainter, rect: QRectF, color) -> None:
    """Two stacked rounded rectangles with a small play triangle."""
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(color, max(1.4, rect.width() * 0.08)))
    upper = QRectF(rect.left(), rect.top(), rect.width() * 0.92, rect.height() * 0.34)
    lower = QRectF(
        rect.left() + rect.width() * 0.08,
        rect.top() + rect.height() * 0.42,
        rect.width() * 0.92,
        rect.height() * 0.5,
    )
    painter.drawRoundedRect(upper, 2, 2)
    painter.drawRoundedRect(lower, 2, 2)
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    tri_h = lower.height() * 0.44
    tri_w = tri_h * 0.9
    center = lower.center()
    triangle = QPainterPath()
    triangle.moveTo(center.x() - tri_w / 2, center.y() - tri_h / 2)
    triangle.lineTo(center.x() + tri_w / 2, center.y())
    triangle.lineTo(center.x() - tri_w / 2, center.y() + tri_h / 2)
    triangle.closeSubpath()
    painter.drawPath(triangle)
    painter.restore()


def draw_activity_glyph(painter: QPainter, rect: QRectF, color) -> None:
    """A pulse trace across the area."""
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(color, max(1.4, rect.width() * 0.09)))
    path = QPainterPath()
    left, right = rect.left(), rect.right()
    middle = rect.center().y()
    path.moveTo(left, middle)
    path.lineTo(left + rect.width() * 0.25, middle)
    path.lineTo(left + rect.width() * 0.36, rect.top() + rect.height() * 0.22)
    path.lineTo(left + rect.width() * 0.5, rect.bottom() - rect.height() * 0.18)
    path.lineTo(left + rect.width() * 0.64, middle)
    path.lineTo(right, middle)
    painter.drawPath(path)
    painter.restore()


def draw_settings_glyph(painter: QPainter, rect: QRectF, color) -> None:
    """Three horizontal sliders with knobs."""
    painter.save()
    line_pen = QPen(color, max(1.4, rect.width() * 0.08))
    painter.setPen(line_pen)
    rows = (0.2, 0.5, 0.8)
    insets = (0.28, 0.05, 0.2)  # knob offsets as a fraction of the width
    for fraction, inset in zip(rows, insets, strict=True):
        y = rect.top() + rect.height() * fraction
        painter.drawLine(
            QPointF(rect.left(), y),
            QPointF(rect.right(), y),
        )
        painter.setBrush(QColor("#FFFFFF"))
        knob = QRectF(0, 0, rect.height() * 0.2, rect.height() * 0.2)
        knob.moveCenter(QPointF(rect.left() + rect.width() * inset, y))
        painter.setPen(line_pen)
        painter.drawEllipse(knob)
    painter.restore()


def draw_info_circle(painter: QPainter, rect: QRectF, color) -> None:
    """A filled circle with an 'i' stem."""
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    diameter = min(rect.width(), rect.height())
    painter.drawEllipse(rect)
    stem_width = diameter * 0.14
    dot = QRectF(
        rect.center().x() - stem_width / 2,
        rect.top() + diameter * 0.2,
        stem_width,
        stem_width,
    )
    stem = QRectF(
        rect.center().x() - stem_width / 2,
        rect.top() + diameter * 0.42,
        stem_width,
        diameter * 0.38,
    )
    painter.setBrush(Qt.GlobalColor.white)
    painter.drawRoundedRect(dot, 1, 1)
    painter.drawRoundedRect(stem, 1, 1)
    painter.restore()


def draw_check_circle(painter: QPainter, rect: QRectF, color) -> None:
    """A filled circle with a check mark."""
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(rect)
    path = QPainterPath()
    w, h = rect.width(), rect.height()
    path.moveTo(rect.left() + w * 0.26, rect.top() + h * 0.54)
    path.lineTo(rect.left() + w * 0.44, rect.top() + h * 0.70)
    path.lineTo(rect.left() + w * 0.74, rect.top() + h * 0.32)
    pen = QPen(Qt.GlobalColor.white)
    pen.setWidthF(max(1.6, w * 0.10))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.restore()


def draw_alert_circle(painter: QPainter, rect: QRectF, color) -> None:
    """A filled circle with an exclamation mark."""
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    diameter = min(rect.width(), rect.height())
    painter.drawEllipse(rect)
    painter.setBrush(Qt.GlobalColor.white)
    bar_width = diameter * 0.14
    upper = QRectF(
        rect.center().x() - bar_width / 2,
        rect.top() + diameter * 0.22,
        bar_width,
        diameter * 0.34,
    )
    lower = QRectF(
        rect.center().x() - bar_width / 2,
        rect.top() + diameter * 0.66,
        bar_width,
        bar_width,
    )
    painter.drawRoundedRect(upper, 1, 1)
    painter.drawEllipse(
        QPointF(rect.center().x(), lower.center().y()), bar_width / 2, bar_width / 2
    )
    painter.restore()
