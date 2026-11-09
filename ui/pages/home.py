"""Home page — the first screen new users see: choose a clear starting path."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from ui.components.cards import Card, EmptyState
from ui.components.formatting import human_timestamp, status_display
from ui.components.pageheader import PageHeader
from ui.strings import (
    HOME_CARD_CREATE_ACTION,
    HOME_CARD_CREATE_BODY,
    HOME_CARD_CREATE_TITLE,
    HOME_CARD_RECORD_ACTION,
    HOME_CARD_RECORD_BODY,
    HOME_CARD_RECORD_TITLE,
    HOME_RECENT_EMPTY,
    HOME_RECENT_LIST_TITLE,
    HOME_SUBTITLE,
    HOME_TITLE,
)
from ui.styles import SPACING_LG, SPACING_SM, SPACING_XL

_RECENT_RUN_COUNT = 5  # rows the welcome screen shows; the full feed lives on Activity


class HomePage(QWidget):
    """Welcome screen with two distinct, working automation entry points."""

    manual_requested = Signal()
    record_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._activity_panel: QWidget | None = None
        self._create_automation_button: QWidget | None = None
        self._record_button: QWidget | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop)
        self._header = PageHeader(HOME_TITLE, HOME_SUBTITLE, parent=self)
        # Tests read the page title through the same attributes as before.
        self._title_label = self._header.title_label
        self._subtitle_label = self._header.description_label
        layout.addWidget(self._header)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(SPACING_LG)
        create_card = Card(
            HOME_CARD_CREATE_TITLE,
            HOME_CARD_CREATE_BODY,
            HOME_CARD_CREATE_ACTION,
            parent=self,
        )
        create_card.action_button.setObjectName("primaryActionButton")
        self._create_automation_button = create_card.action_button
        create_card.action_requested.connect(self.manual_requested.emit)
        cards_row.addWidget(create_card)
        record_card = Card(
            HOME_CARD_RECORD_TITLE,
            HOME_CARD_RECORD_BODY,
            HOME_CARD_RECORD_ACTION,
            parent=self,
        )
        record_card.action_button.setObjectName("primaryActionButton")
        self._record_button = record_card.action_button
        record_card.action_requested.connect(self.record_requested.emit)
        cards_row.addWidget(record_card)
        cards_row.addStretch(1)
        cards_holder = QWidget(self)
        cards_holder.setLayout(cards_row)
        cards_holder.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cards_holder)

        self._activity_panel = QWidget(self)
        self._activity_panel.setObjectName("activityPanel")
        self._activity_panel.setMaximumWidth(744)
        self._activity_layout = QVBoxLayout(self._activity_panel)
        self._activity_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_layout.setSpacing(SPACING_SM)
        self._activity_label = QLabel(HOME_RECENT_LIST_TITLE, self._activity_panel)
        self._activity_label.setObjectName("activityLabel")
        self._activity_layout.addWidget(self._activity_label)
        self._activity_empty = EmptyState(
            "No activity yet",
            HOME_RECENT_EMPTY,
            parent=self,
        )
        self._activity_layout.addWidget(self._activity_empty)
        self._activity_rows: list[QWidget] = []
        layout.addWidget(self._activity_panel)
        layout.addStretch(1)
        self._refresh_activity()

    def refresh(self) -> None:
        """Reload the recent runs shown on this read-only list."""
        self._refresh_activity()

    def _recent_rows(self) -> tuple[tuple[str, str, str], ...]:
        """Friendly (name, status label, timestamp) triples, newest first."""
        if self._service is None:
            return ()
        rows: list[tuple[str, str, str]] = []
        for run in self._service.history()[:_RECENT_RUN_COUNT]:
            workflow_id = getattr(run, "workflow_id", "?")
            if workflow_id == "demo-local-workflow":
                continue
            name = self._service.workflow_name(workflow_id) or workflow_id
            status_value = getattr(getattr(run, "status", None), "value", "Unknown")
            results = getattr(run, "results", None)
            if status_value == "PARTIALLY_PERFORMED" and results is not None:
                label, _ = status_display(status_value, results)
                status_value = label
            rows.append((name, status_value, human_timestamp(getattr(run, "finished_at", None))))
        return tuple(rows)

    def _refresh_activity(self) -> None:
        runs = self._recent_rows()
        for stale in self._activity_rows:
            stale.setParent(None)
            stale.deleteLater()
        self._activity_rows.clear()
        if not runs:
            self._activity_empty.setVisible(True)
            return
        self._activity_empty.setVisible(False)
        for name, status_value, when in runs:
            label, _ = status_display(status_value)
            row = QWidget(self._activity_panel)
            row.setStyleSheet("background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 10, 14, 10)
            row_layout.setSpacing(SPACING_SM)
            title = QLabel(name, row)
            title.setObjectName("rowTitle")
            caption = QLabel(label + (f" — {when}" if when else ""), row)
            caption.setObjectName("rowCaption")
            row_layout.addWidget(title)
            row_layout.addStretch(1)
            row_layout.addWidget(caption)
            self._activity_layout.addWidget(row)
            self._activity_rows.append(row)

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh_activity()
