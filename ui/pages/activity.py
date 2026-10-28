"""Activity page — recent runs and recordings."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from engine.workflow import WorkflowRun
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL


class ActivityPage(QWidget):
    """Readable activity feed drawn from execution history."""

    run_selected = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._runs: tuple[WorkflowRun, ...] = ()
        self._history_list: QListWidget | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("Activity", self)
        self._title_label.setObjectName("pageTitle")
        layout.addWidget(self._title_label)
        self._subtitle_label = QLabel(
            "Recent runs and their outcomes.",
            self,
        )
        self._subtitle_label.setObjectName("pageSubtitle")
        layout.addWidget(self._subtitle_label)
        layout.addSpacing(SPACING_LG)
        self._history_list = QListWidget(self)
        self._history_list.setObjectName("activitiesList")
        self._history_list.setAlternatingRowColors(True)
        self._history_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._history_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._history_list, alignment=Qt.AlignHCenter)
        layout.addSpacing(SPACING_MD)
        self._details_container = QFrame(self)
        self._details_container.setObjectName("detailsContainer")
        details_layout = QVBoxLayout(self._details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(SPACING_SM)
        self._details_label = QLabel("Select a run to see details.", self._details_container)
        self._details_label.setObjectName("activityDetailsLabel")
        details_layout.addWidget(self._details_label)
        layout.addWidget(self._details_container, alignment=Qt.AlignHCenter)
        self._refresh()

    def _on_selection_changed(self) -> None:
        self.run_selected.emit()
        row = self._history_list.currentRow()
        if row < 0 or row >= len(self._runs):
            self._details_label.setText("Select a run to see details.")
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
        for idx, run in enumerate(self._runs):
            item = QListWidgetItem(f"{idx + 1}. {run.workflow_id}")
            item.setData(Qt.UserRole, run.workflow_id)
            item.setToolTip(f"{run.workflow_id} — {run.status.value} — {len(run.results)} steps")
            self._history_list.addItem(item)
        self._details_label.setText("Select a run to see details.")

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh()
