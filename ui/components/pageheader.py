"""Standard page header: title, one-line description, one top-right action."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.styles import SPACING_XS, SPACING_XXL


class PageHeader(QWidget):
    """Shared page template header used by every page (prompt page template)."""

    action_requested = Signal()

    def __init__(
        self,
        title: str,
        description: str,
        *,
        primary_label: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pageHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACING_XXL)
        layout.setSpacing(SPACING_XS)
        text_column = QVBoxLayout()
        text_column.setSpacing(SPACING_XS)
        self._title = QLabel(title, self)
        self._title.setObjectName("pageTitle")
        self._title.setWordWrap(False)
        self._description = QLabel(description, self)
        self._description.setObjectName("pageDescription")
        self._description.setWordWrap(True)
        text_column.addWidget(self._title)
        text_column.addWidget(self._description)
        layout.addLayout(text_column, stretch=1)
        self._primary: QPushButton | None = None
        if primary_label is not None:
            self._primary = QPushButton(primary_label, self)
            self._primary.setObjectName("primaryActionButton")
            self._primary.setMinimumHeight(38)
            # The header has no logic of its own: pages connect to
            # `action_requested` and give the click a real handler.
            self._primary.clicked.connect(self.action_requested.emit)
            layout.addWidget(self._primary, alignment=Qt.AlignTop)

    @property
    def title_label(self) -> QLabel:
        """The page title, for tests."""
        return self._title

    @property
    def description_label(self) -> QLabel:
        """The one-line description, for tests."""
        return self._description

    @property
    def primary_button(self) -> QPushButton | None:
        """The single primary action, or None for read-only pages."""
        return self._primary
