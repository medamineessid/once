"""Activity page — recent runs and their outcomes, in readable language."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from engine.errors import OnceError
from ui.components.cards import Chip, EmptyState
from ui.components.delete_confirm import (
    DeleteConfirmDialog,
    clear_runs_message,
    run_delete_message,
)
from ui.components.formatting import (
    clean_step_message,
    friendly_run_name,
    friendly_step_status,
    human_timestamp,
    status_display,
)
from ui.components.pageheader import PageHeader
from ui.strings import (
    ACTIVITY_CLEAR_ALL,
    ACTIVITY_DETAILS_EMPTY,
    ACTIVITY_EMPTY_BODY,
    ACTIVITY_EMPTY_HEADING,
    ACTIVITY_SUBTITLE,
    ACTIVITY_TITLE,
    DELETE_ACTION,
)
from ui.styles import SPACING_LG, SPACING_SM, SPACING_XL


class RunRow(QWidget):
    """One executed run: what ran, how it ended, and when."""

    def __init__(
        self,
        title: str,
        status_text: str,
        chip_kind: str,
        when: str,
        *,
        delete_enabled: bool = True,
        on_delete: Callable[[], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("runRow")
        row = QVBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(SPACING_SM)
        self._name_label = QLabel(title, self)
        self._name_label.setObjectName("rowTitle")
        chip = Chip(status_text, kind=chip_kind, parent=self)
        self.delete_button = QPushButton(DELETE_ACTION, self)
        self.delete_button.setObjectName("linkActionButton")
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setEnabled(delete_enabled)
        if on_delete is not None:
            self.delete_button.clicked.connect(lambda: on_delete())
        top.addWidget(self._name_label)
        top.addStretch(1)
        top.addWidget(chip, alignment=Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.delete_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(top)
        self._caption = QLabel(when, self)
        self._caption.setObjectName("rowCaption")
        row.addWidget(self._caption)


class ActivityPage(QWidget):
    """Readable activity feed drawn from execution history."""

    run_selected = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._runs: tuple[object, ...] = ()
        self._history_list: QListWidget | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop)
        self._header = PageHeader(ACTIVITY_TITLE, ACTIVITY_SUBTITLE, parent=self)
        self._title_label = self._header.title_label
        self._subtitle_label = self._header.description_label
        layout.addWidget(self._header)

        controls = QHBoxLayout()
        controls.setSpacing(SPACING_SM)
        controls.addStretch(1)
        self._clear_all_button = QPushButton(ACTIVITY_CLEAR_ALL, self)
        self._clear_all_button.setObjectName("secondaryActionButton")
        self._clear_all_button.setMinimumHeight(34)
        self._clear_all_button.clicked.connect(self._clear_all_runs)
        controls.addWidget(self._clear_all_button)
        layout.addLayout(controls)

        self._history_list = QListWidget(self)
        self._history_list.setObjectName("activitiesList")
        self._history_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._history_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._history_list, stretch=1)
        layout.addSpacing(SPACING_SM)
        self._details_container = QFrame(self)
        self._details_container.setObjectName("detailsContainer")
        details_layout = QVBoxLayout(self._details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(SPACING_SM)
        self._details_label = QLabel(ACTIVITY_DETAILS_EMPTY, self._details_container)
        self._details_label.setObjectName("activityDetailsLabel")
        self._details_label.setWordWrap(True)
        details_layout.addWidget(self._details_label)
        layout.addWidget(self._details_container)

        self._empty_state = EmptyState(
            ACTIVITY_EMPTY_HEADING,
            ACTIVITY_EMPTY_BODY,
            parent=self,
        )
        layout.addWidget(self._empty_state)
        self._refresh()

    def _row_facts(self, run: object) -> tuple[str, str, str, str, str, str]:
        """(name-or-id, id, status label, chip kind, when text, status value)."""
        workflow_id = getattr(run, "workflow_id", "?")
        name = friendly_run_name(self._service, workflow_id)
        status_value = getattr(getattr(run, "status", None), "value", "Unknown")
        label, kind = status_display(status_value, getattr(run, "results", None))
        when = human_timestamp(getattr(run, "finished_at", None))
        return name, workflow_id, label, kind, when, status_value

    def _on_selection_changed(self) -> None:
        self.run_selected.emit()
        row = self._history_list.currentRow()
        if row < 0 or row >= len(self._runs):
            self._details_label.setText(ACTIVITY_DETAILS_EMPTY)
            return
        run = self._runs[row]
        name = friendly_run_name(self._service, getattr(run, "workflow_id", ""))
        step_lines = "\n".join(
            f"Step {idx}: {friendly_step_status(getattr(result.status, 'value', ''))} — "
            f"{clean_step_message(result.message)}"
            for idx, result in enumerate(run.results, start=1)
        )
        label, _kind = status_display(getattr(run.status, "value", "Unknown"), run.results)
        count = len(run.results)
        step_word = "step" if count == 1 else "steps"
        self._details_label.setText(
            f"{name} — {label} ({count} {step_word})"
            + (f"\n{step_lines}" if step_lines else "")
        )
        self._details_label.adjustSize()
        self._details_container.updateGeometry()

    def refresh(self) -> None:
        """Reload the history shown on this read-only page."""
        self._refresh()

    def _apply_empty_state(self) -> None:
        """Show the empty state whenever no runs are left to show."""
        has_runs = bool(self._runs)
        self._history_list.setVisible(has_runs)
        self._details_container.setVisible(has_runs)
        self._empty_state.setVisible(not has_runs)
        running = any(
            getattr(getattr(run, "status", None), "value", "") == "RUNNING"
            for run in self._runs
        )
        self._clear_all_button.setEnabled(has_runs and not running)

    def _refresh(self) -> None:
        self._history_list.clear()
        if self._service is None:
            self._runs = ()
            self._apply_empty_state()
            return
        self._runs = self._service.history()
        for run in self._runs:
            name, workflow_id, label, kind, when, status_value = self._row_facts(run)
            run_id = getattr(run, "run_id", "")
            summary = f"{name} — {label}" + (f" — {when}" if when else "")
            item = QListWidgetItem(summary)
            item.setForeground(QColor(0, 0, 0, 0))
            item.setData(Qt.UserRole, workflow_id)
            item.setToolTip(summary)
            row = RunRow(
                name,
                label,
                kind,
                when,
                delete_enabled=status_value != "RUNNING",
                on_delete=lambda rid=run_id, run_name=name: self._delete_run(rid, run_name),
                parent=self._history_list,
            )
            hint = row.sizeHint()
            hint.setHeight(64)
            item.setSizeHint(hint)
            self._history_list.addItem(item)
            self._history_list.setItemWidget(item, row)
        self._details_label.setText(ACTIVITY_DETAILS_EMPTY)
        self._apply_empty_state()

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
            self._details_label.setText(str(error))
            return
        self._refresh()

    def _clear_all_runs(self) -> None:
        """Delete every finished run after naming the count in the dialog."""
        if self._service is None or not self._runs:
            return
        count = len(self._runs)
        choice = DeleteConfirmDialog(clear_runs_message(count), parent=self).ask()
        if not choice.confirmed:
            return
        try:
            self._service.clear_runs()
        except OnceError as error:
            self._details_label.setText(str(error))
            return
        self._refresh()

    def select_run(self, run_id: str) -> None:
        """Select a run by run_id after refreshing."""
        self._refresh()
        for index, run in enumerate(self._runs):
            if getattr(run, "run_id", None) == run_id:
                self._history_list.setCurrentRow(index)
                return

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh()
