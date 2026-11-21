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
from ui.components.band import PageBand
from ui.components.buttons import ActionButton
from ui.components.cards import Chip, EmptyState
from ui.components.delete_confirm import (
    DeleteConfirmDialog,
    clear_runs_message,
    run_delete_message,
)
from ui.components.formatting import (
    clean_step_message,
    failure_reason,
    friendly_run_name,
    friendly_step_status,
    human_duration,
    human_timestamp,
    status_display,
)
from ui.strings import (
    ACTIVITY_CLEAR_ALL,
    ACTIVITY_DETAILS_EMPTY,
    ACTIVITY_EMPTY_BODY,
    ACTIVITY_EMPTY_HEADING,
    ACTIVITY_SUBTITLE,
    ACTIVITY_TITLE,
    DELETE_ACTION,
    RERUN_ACTION,
)
from ui.styles import ROW_HEIGHT, SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL, SPACING_XS


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
        rerun_enabled: bool = True,
        on_delete: Callable[[], None] | None = None,
        on_rerun: Callable[[], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("runRow")
        # A plain QWidget only paints its stylesheet background when asked.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QVBoxLayout(self)
        row.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        row.setSpacing(SPACING_XS)
        top = QHBoxLayout()
        top.setSpacing(SPACING_SM)
        self._name_label = QLabel(title, self)
        self._name_label.setObjectName("rowTitle")
        chip = Chip(status_text, kind=chip_kind, parent=self)
        self.rerun_button = QPushButton(RERUN_ACTION, self)
        self.rerun_button.setObjectName("linkActionButton")
        self.rerun_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rerun_button.setEnabled(rerun_enabled)
        if on_rerun is not None:
            self.rerun_button.clicked.connect(lambda: on_rerun())
        self.delete_button = QPushButton(DELETE_ACTION, self)
        self.delete_button.setObjectName("destructiveLinkButton")
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setEnabled(delete_enabled)
        if on_delete is not None:
            self.delete_button.clicked.connect(lambda: on_delete())
        top.addWidget(self._name_label)
        top.addStretch(1)
        top.addWidget(chip, alignment=Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.rerun_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.delete_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(top)
        self._caption = QLabel(when, self)
        self._caption.setObjectName("rowCaption")
        row.addWidget(self._caption)

    def set_caption(self, text: str) -> None:
        """Show the run's date, duration, and first failure in one line."""
        self._caption.setText(text)


class ActivityPage(QWidget):
    """Readable activity feed drawn from execution history."""

    run_selected = Signal()
    rerun_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._runs: tuple[object, ...] = ()
        self._history_list: QListWidget | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)
        # Colour-blocked header band: the title sits inside the band, cropped at
        # its edge, and the body below fills the width with no dead gaps.
        self._band = PageBand(
            ACTIVITY_TITLE,
            micro="0 runs recorded",
            description=ACTIVITY_SUBTITLE,
            parent=self,
        )
        self._micro_label = self._band.micro_label
        self._title_label = self._band.title_label
        self._subtitle_label = self._band.description_label
        layout.addWidget(self._band)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        body_layout.setSpacing(SPACING_MD)
        layout.addWidget(body, stretch=1)

        controls = QHBoxLayout()
        controls.setSpacing(SPACING_SM)
        controls.addStretch(1)
        self._clear_all_button = ActionButton(ACTIVITY_CLEAR_ALL, variant="secondary", parent=body)
        self._clear_all_button.clicked.connect(self._clear_all_runs)
        controls.addWidget(self._clear_all_button)
        body_layout.addLayout(controls)

        self._history_list = QListWidget(body)
        self._history_list.setObjectName("activitiesList")
        self._history_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._history_list.itemSelectionChanged.connect(self._on_selection_changed)
        # The list is exactly as tall as its rows: the details card belongs
        # right under the run you selected, not at the far end of the page.
        body_layout.addWidget(self._history_list)
        self._details_container = QFrame(body)
        self._details_container.setObjectName("detailsContainer")
        details_layout = QVBoxLayout(self._details_container)
        details_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        details_layout.setSpacing(SPACING_SM)
        self._details_label = QLabel(ACTIVITY_DETAILS_EMPTY, self._details_container)
        self._details_label.setObjectName("activityDetailsLabel")
        self._details_label.setWordWrap(True)
        details_layout.addWidget(self._details_label)
        body_layout.addWidget(self._details_container)

        self._empty_state = EmptyState(
            ACTIVITY_EMPTY_HEADING,
            ACTIVITY_EMPTY_BODY,
            icon_name="pulse",
            parent=body,
        )
        body_layout.addWidget(self._empty_state)
        body_layout.addStretch(1)
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
            f"{name} — {label} ({count} {step_word})" + (f"\n{step_lines}" if step_lines else "")
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
            getattr(getattr(run, "status", None), "value", "") == "RUNNING" for run in self._runs
        )
        self._clear_all_button.setEnabled(has_runs and not running)

    def _refresh(self) -> None:
        self._history_list.clear()
        if self._service is None:
            self._runs = ()
            self._band.set_micro("0 runs recorded")
            self._apply_empty_state()
            return
        self._runs = self._service.history()
        count = len(self._runs)
        self._band.set_micro(f"{count} run{'s' if count != 1 else ''} recorded")
        for run in self._runs:
            name, workflow_id, label, kind, when, status_value = self._row_facts(run)
            run_id = getattr(run, "run_id", "")
            caption = self._caption_for(run, when)
            item = QListWidgetItem(name)
            item.setForeground(QColor(0, 0, 0, 0))
            item.setData(Qt.UserRole, workflow_id)
            item.setToolTip(f"{name} — {label}" + (f" — {caption}" if caption else ""))
            row = RunRow(
                name,
                label,
                kind,
                caption,
                delete_enabled=status_value != "RUNNING",
                # A run cannot be repeated while this one is still going.
                rerun_enabled=status_value != "RUNNING",
                on_delete=lambda rid=run_id, run_name=name: self._delete_run(rid, run_name),
                on_rerun=lambda wid=workflow_id: self._rerun(wid),
                parent=self._history_list,
            )
            # The row's own hint keeps every row the same height, whatever
            # its caption length.
            item.setSizeHint(row.sizeHint())
            self._history_list.addItem(item)
            self._history_list.setItemWidget(item, row)
        self._history_list.setFixedHeight(
            max(ROW_HEIGHT, min(520, 12 + len(self._runs) * (ROW_HEIGHT + 12)))
        )
        self._details_label.setText(ACTIVITY_DETAILS_EMPTY)
        self._apply_empty_state()

    def _caption_for(self, run: object, when: str) -> str:
        """One line: when it ran, how long it took, and why it stopped."""
        duration = human_duration(
            getattr(run, "started_at", None), getattr(run, "finished_at", None)
        )
        parts = [part for part in (when, f"took {duration}" if duration else "") if part]
        reason = clean_step_message(failure_reason(getattr(run, "results", ())))
        if reason:
            parts.append(f"Stopped: {reason}")
        return " · ".join(parts)

    def _rerun(self, workflow_id: str) -> None:
        """Ask for one more run of the saved automation behind this history row."""
        self.rerun_requested.emit(workflow_id)

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
