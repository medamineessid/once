"""Sidebar footer status driven by real controller state (P2)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ui.strings import (
    FOOTER_ATTENTION,
    FOOTER_READY,
    FOOTER_RUNNING,
    STOP_RUN_ACTION,
    STOP_RUN_HINT,
)
from ui.styles import ACCENT, STATUS_ERROR, STATUS_OK

READY = FOOTER_READY
RUNNING = FOOTER_RUNNING
NEEDS_ATTENTION = FOOTER_ATTENTION

_STATE_COLORS = {
    READY: STATUS_OK,
    RUNNING: ACCENT,
    NEEDS_ATTENTION: STATUS_ERROR,
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
    """One fixed label, plus the Stop control that exists only during a run."""

    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusFooter")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._dot = StatusDot(self)
        self._text = QLabel(READY, self)
        self._text.setObjectName("statusFooterText")
        self.stop_button = QPushButton(STOP_RUN_ACTION, self)
        self.stop_button.setObjectName("destructiveActionButton")
        self.stop_button.setToolTip(STOP_RUN_HINT)
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.stop_button.setVisible(False)
        layout.addWidget(self._dot)
        layout.addWidget(self._text)
        layout.addStretch(1)
        layout.addWidget(self.stop_button)
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
        # Stop exists only while something is running; there is nothing to
        # stop on a ready or failed footer.
        self.stop_button.setVisible(state == RUNNING)

    @property
    def text(self) -> str:
        """Footer text, for tests."""
        return self._text.text()
