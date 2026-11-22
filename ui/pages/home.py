"""Home — the first screen: a bold hero, three real counts, real recent runs.

The hero carries the two actions (a 128px lemon Record circle and an outlined
Build control). Nothing on this page is decorative: the micro label, the three
stat blocks and the recent-run list all read live controller data.
"""

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
from ui.components.cards import Chip, EmptyState, StatBlock
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
    HOME_RECENT_EMPTY,
    HOME_RECENT_LIST_TITLE,
    HOME_SUBTITLE,
)
from ui.styles import (
    CONTROL_HEIGHT_SMALL,
    SPACING_LG,
    SPACING_SM,
    SPACING_XL,
    SPACING_XS,
)

_RECENT_RUN_COUNT = 5  # rows the welcome screen shows; the full feed lives on Activity


class HomePage(QWidget):
    """Welcome screen with the two real automation entry points."""

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
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_LG)

        saved = len(self._service.list_saved()) if self._service is not None else 0
        self._hero = Hero(
            f"{saved} saved automation{'s' if saved != 1 else ''} ready",
            (("Automate", False), ("anything.", True)),
            subtitle=HOME_SUBTITLE,
            parent=content,
        )
        self._create_automation_button = self._hero.build_button
        self._record_button = self._hero.record_button
        self._hero.build_requested.connect(self.manual_requested.emit)
        self._hero.record_requested.connect(self.record_requested.emit)
        layout.addWidget(self._hero)
        # Tests and the page template read the display line and guiding line
        # through these attributes.
        self._title_label = self._hero.line_labels[0]
        self._subtitle_label = QLabel(HOME_SUBTITLE, content)
        self._subtitle_label.setObjectName("pageSubtitle")
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setVisible(False)  # the hero already shows it

        self._stats = QHBoxLayout()
        self._stats.setContentsMargins(0, 0, 0, 0)
        self._stats.setSpacing(SPACING_LG)
        self._automations_stat = StatBlock("AUTOMATIONS SAVED", accent=True, parent=content)
        self._runs_stat = StatBlock("RUNS RECORDED", parent=content)
        self._succeeded_stat = StatBlock("SUCCEEDED RUNS", parent=content)
        for block in (self._automations_stat, self._runs_stat, self._succeeded_stat):
            self._stats.addWidget(block, stretch=1)
        stats_holder = QWidget(content)
        stats_holder.setLayout(self._stats)
        layout.addWidget(stats_holder)

        self._activity_panel = QWidget(content)
        self._activity_panel.setObjectName("activityPanel")
        self._activity_layout = QVBoxLayout(self._activity_panel)
        self._activity_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_layout.setSpacing(SPACING_SM)
        self._activity_label = QLabel(HOME_RECENT_LIST_TITLE.upper(), self._activity_panel)
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
            icon_name="clock",
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
        """Reload the live counts and the recent runs."""
        self._refresh_stats()
        self._refresh_activity()

    def reveal(self) -> None:
        """Play the hero line reveal; instant when animations are disabled."""
        reveal_lines(self._hero.line_labels)

    def _refresh_stats(self) -> None:
        """Update the three stat blocks from real history and saved files."""
        if self._service is None:
            self._automations_stat.set_value("0")
            self._runs_stat.set_value("0")
            self._succeeded_stat.set_value("0")
            return
        saved = len(self._service.list_saved())
        history = tuple(self._service.history())
        done_statuses = {"SUCCEEDED", "OBSERVATION_ONLY"}
        succeeded = sum(
            1
            for run in history
            if getattr(getattr(run, "status", None), "value", "") in done_statuses
        )
        self._automations_stat.set_value(str(saved))
        self._runs_stat.set_value(str(len(history)))
        self._succeeded_stat.set_value(str(succeeded))
        self._hero.set_micro(f"{saved} saved automation{'s' if saved != 1 else ''} ready")

    def _recent_rows(self) -> tuple[tuple[str, str, str, str, str, str, bool], ...]:
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
            delete_btn.setObjectName("linkActionButton")
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setMinimumHeight(CONTROL_HEIGHT_SMALL)
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
        self._refresh_stats()
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
        self.refresh()
