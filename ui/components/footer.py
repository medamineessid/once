"""Sidebar footer status driven by real controller state (P2)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ui.strings import FOOTER_ATTENTION, FOOTER_READY, FOOTER_RUNNING

READY = FOOTER_READY
RUNNING = FOOTER_RUNNING
NEEDS_ATTENTION = FOOTER_ATTENTION

_STATE_COLORS = {
    READY: "#16A34A",
    RUNNING: "#2563EB",
    NEEDS_ATTENTION: "#DC2626",
}


class StatusDot(QWidget):
    """A small painted status dot; color follows the current state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(QSize(10, 10))
        self._color = QColor(_STATE_COLORS[READY])

    def set_state(self, state: str) -> None:
        self._color = QColor(_STATE_COLORS.get(state, _STATE_COLORS[READY]))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(0, 0, 9, 9)
        painter.end()


class StatusFooter(QWidget):
    """One fixed label: Ready / Running… / Needs attention."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusFooter")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._dot = StatusDot(self)
        self._text = QLabel(READY, self)
        self._text.setObjectName("statusFooterText")
        layout.addWidget(self._dot)
        layout.addWidget(self._text)
        layout.addStretch(1)
        self._state = READY

    @property
    def state(self) -> str:
        """Current footer state string."""
        return self._state

    def set_state(self, state: str) -> None:
        """Switch the footer to Ready / Running… / Needs attention."""
        if state not in _STATE_COLORS:
            state = READY
        self._state = state
        self._dot.set_state(state)
        self._text.setText(state)

    @property
    def text(self) -> str:
        """Footer text, for tests."""
        return self._text.text()
