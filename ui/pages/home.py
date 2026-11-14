"""Home page — the first screen new users see: choose a clear starting path."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from ui.components.cards import Card, Chip, EmptyState
from ui.components.formatting import (
    failure_reason,
    friendly_run_name,
    human_timestamp,
    status_display,
)
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
from ui.styles import SPACING_LG, SPACING_SM, SPACING_XL, SPACING_XS

_RECENT_RUN_COUNT = 5  # rows the welcome screen shows; the full feed lives on Activity
_HOME_MAX_WIDTH = 920


class HomePage(QWidget):
    """Welcome screen with two distinct, working automation entry points."""

    manual_requested = Signal()
    record_requested = Signal()
    view_run_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._activity_panel: QWidget | None = None
        self._create_automation_button: QWidget | None = None
        self._record_button: QWidget | None = None
        self._loading = False
        self._init_ui()

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        outer.setSpacing(SPACING_LG)
        outer.setAlignment(Qt.AlignTop)

        content = QWidget(self)
        content.setMaximumWidth(_HOME_MAX_WIDTH)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_LG)

        self._header = PageHeader(HOME_TITLE, HOME_SUBTITLE, parent=content)
        # Tests read the page title through the same attributes as before.
        self._title_label = self._header.title_label
        self._subtitle_label = self._header.description_label
        layout.addWidget(self._header)

        cards_row = QHBoxLayout()
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(SPACING_LG)
        create_card = Card(
            HOME_CARD_CREATE_TITLE,
            HOME_CARD_CREATE_BODY,
            HOME_CARD_CREATE_ACTION,
            parent=content,
        )
        create_card.action_button.setObjectName("primaryActionButton")
        self._create_automation_button = create_card.action_button
        create_card.action_requested.connect(self.manual_requested.emit)
        cards_row.addWidget(create_card, stretch=1)

        record_card = Card(
            HOME_CARD_RECORD_TITLE,
            HOME_CARD_RECORD_BODY,
            HOME_CARD_RECORD_ACTION,
            parent=content,
        )
        record_card.action_button.setObjectName("primaryActionButton")
        self._record_button = record_card.action_button
        record_card.action_requested.connect(self.record_requested.emit)
        cards_row.addWidget(record_card, stretch=1)

        cards_holder = QWidget(content)
        cards_holder.setLayout(cards_row)
        cards_holder.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cards_holder)

        self._activity_panel = QWidget(content)
        self._activity_panel.setObjectName("activityPanel")
        self._activity_layout = QVBoxLayout(self._activity_panel)
        self._activity_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_layout.setSpacing(SPACING_SM)
        self._activity_label = QLabel(HOME_RECENT_LIST_TITLE, self._activity_panel)
        self._activity_label.setObjectName("activityLabel")
        self._activity_layout.addWidget(self._activity_label)

        self._loading_label = QLabel("Loading recent activity…", self._activity_panel)
        self._loading_label.setObjectName("rowCaption")
        self._loading_label.setVisible(False)
        self._activity_layout.addWidget(self._loading_label)

        self._activity_empty = EmptyState(
            "No runs yet",
            HOME_RECENT_EMPTY,
            parent=self._activity_panel,
        )
        self._activity_layout.addWidget(self._activity_empty)
        self._activity_rows: list[QWidget] = []
        layout.addWidget(self._activity_panel)

        outer.addWidget(content)
        outer.addStretch(1)
        self._refresh_activity()

    def set_loading(self, loading: bool) -> None:
        """Toggle loading state for recent runs."""
        self._loading = loading
        self._refresh_activity()

    def refresh(self) -> None:
        """Reload the recent runs shown on this read-only list."""
        self._refresh_activity()

    def _recent_rows(
        self,
    ) -> tuple[tuple[str, str, str, str, str, str], ...]:
        """Return (run_id, name, status label, chip kind, when, failure_reason) tuples."""
        if self._service is None:
            return ()
        rows: list[tuple[str, str, str, str, str, str]] = []
        for run in self._service.history()[:_RECENT_RUN_COUNT]:
            workflow_id = getattr(run, "workflow_id", "?")
            if workflow_id == "demo-local-workflow":
                continue
            run_id = getattr(run, "run_id", "")
            name = friendly_run_name(self._service, workflow_id)
            status_value = getattr(getattr(run, "status", None), "value", "Unknown")
            results = getattr(run, "results", None)
            label, chip_kind = status_display(status_value, results)
            when = human_timestamp(getattr(run, "finished_at", None))
            reason = failure_reason(results) if status_value == "FAILED" else ""
            rows.append((run_id, name, label, chip_kind, when, reason))
        return tuple(rows)

    def _refresh_activity(self) -> None:
        for stale in self._activity_rows:
            stale.setParent(None)
            stale.deleteLater()
        self._activity_rows.clear()

        if self._loading:
            self._loading_label.setVisible(True)
            self._activity_empty.setVisible(False)
            return

        self._loading_label.setVisible(False)
        runs = self._recent_rows()
        if not runs:
            self._activity_empty.setVisible(True)
            return
        self._activity_empty.setVisible(False)

        for run_id, name, label, chip_kind, when, reason in runs:
            row = QFrame(self._activity_panel)
            row.setObjectName("homeRunRow")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(
                SPACING_LG,
                SPACING_SM + SPACING_XS,
                SPACING_LG,
                SPACING_SM + SPACING_XS,
            )
            row_layout.setSpacing(SPACING_XS)

            top = QHBoxLayout()
            top.setContentsMargins(0, 0, 0, 0)
            top.setSpacing(SPACING_SM)
            title = QLabel(name, row)
            title.setObjectName("rowTitle")
            chip = Chip(label, kind=chip_kind, parent=row)
            when_label = QLabel(when, row)
            when_label.setObjectName("rowCaption")
            top.addWidget(title)
            top.addStretch(1)
            top.addWidget(chip)
            if when:
                top.addWidget(when_label)
            row_layout.addLayout(top)

            if reason:
                bottom = QHBoxLayout()
                bottom.setContentsMargins(0, 0, 0, 0)
                bottom.setSpacing(SPACING_SM)
                reason_label = QLabel(reason, row)
                reason_label.setObjectName("rowErrorReason")
                reason_label.setWordWrap(True)
                details_btn = QPushButton("View details", row)
                details_btn.setObjectName("linkActionButton")
                details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                details_btn.clicked.connect(
                    lambda _=False, rid=run_id: self.view_run_requested.emit(rid)
                )
                bottom.addWidget(reason_label, stretch=1)
                bottom.addWidget(details_btn)
                row_layout.addLayout(bottom)

            self._activity_layout.addWidget(row)
            self._activity_rows.append(row)

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh_activity()
