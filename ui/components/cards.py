"""Card, chip, and empty-state presentation building blocks."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.components.phosphor_icons import (
    EMPTY_STATE_ICON_LOGICAL_SIZE,
    render_icon_pixmap,
)
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, TEXT_BODY


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
        self.setMinimumWidth(260)
        self.setMaximumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self._title = QLabel(title, self)
        self._title.setObjectName("cardTitle")
        self._body = QLabel(body, self)
        self._body.setObjectName("cardBody")
        self._body.setWordWrap(True)
        self._body.setMinimumHeight(54)
        self._action = QPushButton(action_label, self)
        self._action.setObjectName("secondaryActionButton")
        self._action.setMinimumHeight(38)
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
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

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


class SectionCard(QFrame):
    """A titled settings-style card with a content column.

    Replaces the old white GroupBox panel: one card per section, flush with the
    page grid, so Settings reads like every other page.
    """

    def __init__(
        self,
        title: str,
        body: str = "",
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sectionCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        outer.setSpacing(SPACING_SM)
        self._title = QLabel(title, self)
        self._title.setObjectName("sectionCardTitle")
        outer.addWidget(self._title)
        self._body = QLabel(body, self)
        self._body.setObjectName("sectionCardBody")
        self._body.setWordWrap(True)
        if body:
            outer.addWidget(self._body)
        self.content = QVBoxLayout()
        self.content.setContentsMargins(0, 0, 0, 0)
        self.content.setSpacing(SPACING_SM)
        outer.addLayout(self.content)

    @property
    def title_label(self) -> QLabel:
        """Card title, for tests."""
        return self._title

    @property
    def body_label(self) -> QLabel:
        """Card body, for tests."""
        return self._body


class StatBlock(QFrame):
    """A large Anton numeral with a caption; always a real, live count."""

    def __init__(
        self,
        caption: str,
        value: str = "0",
        *,
        accent: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statBlock")
        self.setProperty("accent", "true" if accent else "false")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.setSpacing(0)
        self._value = QLabel(value, self)
        self._value.setObjectName("statNumber")
        self._caption = QLabel(caption, self)
        self._caption.setObjectName("statCaption")
        layout.addWidget(self._value)
        layout.addWidget(self._caption)

    def set_value(self, value: str) -> None:
        """Update the numeral (a real count, never a placeholder)."""
        self._value.setText(value)

    def set_caption(self, caption: str) -> None:
        """Update the caption under the numeral."""
        self._caption.setText(caption)

    @property
    def value_text(self) -> str:
        """Current numeral, for tests."""
        return self._value.text()


class EmptyState(QWidget):
    """A centered empty-state block: icon, one heading, one body, one action."""

    def __init__(
        self,
        heading: str,
        body: str,
        *,
        icon_name: str | None = None,
        action_label: str | None = None,
        on_action: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_SM)
        self._icon: QLabel | None = None
        if icon_name is not None:
            self._icon = QLabel(self)
            self._icon.setObjectName("emptyIcon")
            self._icon.setPixmap(
                render_icon_pixmap(
                    icon_name,
                    weight="Bold",
                    logical_size=EMPTY_STATE_ICON_LOGICAL_SIZE,
                    color=TEXT_BODY,
                )
            )
            side = EMPTY_STATE_ICON_LOGICAL_SIZE
            self._icon.setFixedSize(QSize(side, side))
            self._icon.setScaledContents(True)
            layout.addWidget(self._icon)
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
