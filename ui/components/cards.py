"""Card, chip, and empty-state presentation building blocks."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class Card(QFrame):
    """A white rounded tile with a heading and a body plus one action."""

    action_requested = Signal()

    def __init__(
        self,
        title: str,
        body: str,
        action_label: str,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cardTile")
        self.setMinimumWidth(240)
        self.setMaximumWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        self._title = QLabel(title, self)
        self._title.setObjectName("cardTitle")
        self._body = QLabel(body, self)
        self._body.setObjectName("cardBody")
        self._body.setWordWrap(True)
        self._action = QPushButton(action_label, self)
        self._action.setObjectName("secondaryActionButton")
        self._action.clicked.connect(self.action_requested.emit)
        layout.addWidget(self._title)
        layout.addWidget(self._body)
        layout.addWidget(self._action)
        layout.addStretch(1)

    @property
    def title_label(self) -> QLabel:
        """Title label, for tests."""
        return self._title

    @property
    def action_button(self) -> QPushButton:
        """Action button, for tests."""
        return self._action


class Chip(QLabel):
    """A small tagged label (kind names, mutating markers, statuses)."""

    def __init__(self, text: str = "", kind: str = "neutral", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("chip")
        self.setProperty("chipKind", kind)

    @staticmethod
    def row(*chips: str, kind: str = "neutral", parent: QWidget | None = None) -> QWidget:
        """Build a horizontal row of chips."""
        row = QWidget(parent)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for text in chips:
            layout.addWidget(Chip(text, kind=kind))
        layout.addStretch(1)
        return row


class EmptyState(QWidget):
    """A centered empty-state block: one heading, one body, at most one action."""

    def __init__(
        self,
        heading: str,
        body: str,
        *,
        action_label: str | None = None,
        on_action: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._heading = QLabel(heading, self)
        self._heading.setObjectName("emptyHeading")
        self._body = QLabel(body, self)
        self._body.setObjectName("emptyBody")
        self._body.setWordWrap(True)
        layout.addWidget(self._heading)
        layout.addWidget(self._body)
        self._action: QPushButton | None = None
        if action_label is not None and on_action is not None:
            self._action = QPushButton(action_label, self)
            self._action.setObjectName("secondaryActionButton")
            self._action.clicked.connect(on_action)
            layout.addWidget(self._action)

    @property
    def heading_label(self) -> QLabel:
        """Heading, for tests."""
        return self._heading

    @property
    def action_button(self) -> QPushButton | None:
        """The single action button, or None."""
        return self._action
