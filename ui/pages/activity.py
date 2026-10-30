"""Activity page — recent runs and their outcomes, in readable language."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from ui.components.cards import Chip
from ui.components.formatting import human_timestamp, status_display
from ui.components.pageheader import PageHeader
from ui.strings import ACTIVITY_DETAILS_EMPTY, ACTIVITY_SUBTITLE, ACTIVITY_TITLE
from ui.styles import SPACING_LG, SPACING_SM, SPACING_XL


class RunRow(QWidget):
    """One executed run: what ran, how it ended, and when."""

    def __init__(self, title: str, status_text: str, chip_kind: str, when: str, parent=None):
        super().__init__(parent)
        self.setObjectName("runRow")
        row = QVBoxLayout(self)
        row.setContentsMargins(6, 6, 6, 6)
        row.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(SPACING_SM)
        self._name_label = QLabel(title, self)
        self._name_label.setObjectName("rowTitle")
        chip = Chip(status_text, kind=chip_kind, parent=self)
        top.addWidget(self._name_label)
        top.addStretch(1)
        top.addWidget(chip)
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
        details_layout.addWidget(self._details_label)
        layout.addWidget(self._details_container)
        self._refresh()

    def _row_facts(self, run: object) -> tuple[str, str, str, str, str]:
        """(name-or-id, id, status label, chip kind, when text) for one run."""
        workflow_id = getattr(run, "workflow_id", "?")
        name = workflow_id
        if self._service is not None:
            name = self._service.workflow_name(workflow_id) or workflow_id
        status_value = getattr(getattr(run, "status", None), "value", "Unknown")
        label, kind = status_display(status_value)
        when = human_timestamp(getattr(run, "finished_at", None))
        return name, workflow_id, label, kind, when

    def _on_selection_changed(self) -> None:
        self.run_selected.emit()
        row = self._history_list.currentRow()
        if row < 0 or row >= len(self._runs):
            self._details_label.setText(ACTIVITY_DETAILS_EMPTY)
            return
        run = self._runs[row]
        step_lines = "\n".join(
            f"{result.step_id} — {result.status.value} — {result.message}" for result in run.results
        )
        self._details_label.setText(
            f"{run.workflow_id} — {run.status.value} — {len(run.results)} steps"
            + (f"\n{step_lines}" if step_lines else "")
        )

    def refresh(self) -> None:
        """Reload the history shown on this read-only page."""
        self._refresh()

    def _refresh(self) -> None:
        self._history_list.clear()
        if self._service is None:
            self._runs = ()
            return
        self._runs = self._service.history()
        for run in self._runs:
            name, workflow_id, label, kind, when = self._row_facts(run)
            summary = f"{name} — {label}" + (f" — {when}" if when else "")
            item = QListWidgetItem(summary)
            item.setData(Qt.UserRole, workflow_id)
            item.setToolTip(f"{workflow_id} — {label} — {when}")
            row = RunRow(name, label, kind, when, parent=self._history_list)
            hint = row.sizeHint()
            hint.setHeight(52)
            self._history_list.addItem(item)
            self._history_list.setItemWidget(item, row)
        self._details_label.setText(ACTIVITY_DETAILS_EMPTY)

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh()
