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
from engine.errors import OnceError
from ui.components.cards import Card, Chip, EmptyState
from ui.components.delete_confirm import DeleteConfirmDialog, run_delete_message
from ui.components.formatting import (
    failure_reason,
    friendly_run_name,
    human_timestamp,
    status_display,
)
from ui.components.hero import Hero
from ui.motion import reveal_lines
from ui.strings import (
    DELETE_ACTION,
    HOME_CARD_CREATE_ACTION,
    HOME_CARD_CREATE_BODY,
    HOME_CARD_CREATE_TITLE,
    HOME_CARD_RECORD_ACTION,
    HOME_CARD_RECORD_BODY,
    HOME_CARD_RECORD_TITLE,
    HOME_RECENT_EMPTY,
    HOME_RECENT_LIST_TITLE,
    HOME_SUBTITLE,
)
from ui.styles import SPACING_LG, SPACING_SM, SPACING_XL, SPACING_XS

_RECENT_RUN_COUNT = 5  # rows the welcome screen shows; the full feed lives on Activity


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
        outer.setContentsMargins(SPACING_LG, SPACING_XL, SPACING_LG, SPACING_XL)
        outer.setSpacing(SPACING_LG)
        outer.setAlignment(Qt.AlignTop)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_LG)

        saved = len(self._service.list_saved()) if self._service is not None else 0
        self._hero = Hero(
            f"{saved} saved automation{'s' if saved != 1 else ''} ready",
            (("Automate", False), ("anything.", True)),
            parent=content,
        )
        layout.addWidget(self._hero)
        # Tests read the page title and subtitle through the same attributes.
        self._title_label = self._hero.line_labels[0]
        self._subtitle_label = QLabel(HOME_SUBTITLE, content)
        self._subtitle_label.setObjectName("pageSubtitle")
        self._subtitle_label.setWordWrap(True)
        layout.addWidget(self._subtitle_label)

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

        self._notice_label = QLabel("", self._activity_panel)
        self._notice_label.setObjectName("rowErrorReason")
        self._notice_label.setWordWrap(True)
        self._notice_label.setVisible(False)
        self._activity_layout.addWidget(self._notice_label)

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

    def reveal(self) -> None:
        """Play the hero line reveal; instant when animations are disabled."""
        reveal_lines(self._hero.line_labels)

    def _recent_rows(
        self,
    ) -> tuple[tuple[str, str, str, str, str, str, bool], ...]:
        """Return (run_id, name, label, chip kind, when, reason, running) tuples."""
        if self._service is None:
            return ()
        rows: list[tuple[str, str, str, str, str, str, bool]] = []
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
            rows.append((run_id, name, label, chip_kind, when, reason, status_value == "RUNNING"))
        return tuple(rows)

    def _refresh_activity(self) -> None:
        for stale in self._activity_rows:
            stale.setParent(None)
            stale.deleteLater()
        self._activity_rows.clear()
        self._notice_label.setVisible(False)

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

        for run_id, name, label, chip_kind, when, reason, running in runs:
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
            delete_btn = QPushButton(DELETE_ACTION, row)
            delete_btn.setObjectName("deleteRunButton")
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setEnabled(not running)
            delete_btn.clicked.connect(
                lambda _=False, rid=run_id, run_name=name: self._delete_run(rid, run_name)
            )
            top.addWidget(title)
            top.addStretch(1)
            top.addWidget(chip)
            if when:
                top.addWidget(when_label)
            top.addWidget(delete_btn)
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

    def _delete_run(self, run_id: str, name: str) -> None:
        """Delete one finished run after an explicitly confirmed dialog."""
        if self._service is None:
            return
        choice = DeleteConfirmDialog(run_delete_message(name), parent=self).ask()
        if not choice.confirmed:
            return
        try:
            self._service.delete_run(run_id)
        except OnceError as error:
            self._notice_label.setText(str(error))
            self._notice_label.setVisible(True)
            return
        self._refresh_activity()
