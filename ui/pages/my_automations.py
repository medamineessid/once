"""My Automations page — manage saved workflows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from engine.errors import WorkflowValidationError
from engine.workflow import Workflow
from ui.workers import WorkflowWorker


class MyAutomationsPage(QWidget):
    """List saved workflows with name, last status, and actions."""

    opened_workflow = Signal(Path)
    workflow_selected = Signal()
    preview_requested = Signal()
    run_requested = Signal(Path)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._workflow_list: QListWidget | None = None
        self._worker: WorkflowWorker | None = None
        self._thread: QThread | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("My automations", self)
        self._title_label.setObjectName("pageTitle")
        self._title_label.setStyleSheet("font-size: 26px; font-weight: 600; color: #1d1d1d;")
        layout.addWidget(self._title_label)
        self._subtitle_label = QLabel(
            "Open and manage your saved workflows.",
            self,
        )
        self._subtitle_label.setObjectName("pageSubtitle")
        self._subtitle_label.setStyleSheet("font-size: 15px; color: #525252; margin-top: 2px;")
        layout.addWidget(self._subtitle_label)
        layout.addSpacing(16)
        self._workflow_list = QListWidget(self)
        self._workflow_list.setObjectName("workflowList")
        self._workflow_list.setAlternatingRowColors(True)
        self._workflow_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._workflow_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._workflow_list, alignment=Qt.AlignHCenter)
        layout.addSpacing(12)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)
        self._open_button = QPushButton("Open", self)
        self._open_button.setObjectName("secondaryActionButton")
        self._open_button.setMinimumHeight(38)
        self._open_button.clicked.connect(self._open_selected)
        self._preview_button = QPushButton("Preview", self)
        self._preview_button.setObjectName("secondaryActionButton")
        self._preview_button.setMinimumHeight(38)
        self._preview_button.clicked.connect(self._preview_selected)
        self._run_button = QPushButton("Run", self)
        self._run_button.setObjectName("primaryActionButton")
        self._run_button.setMinimumHeight(38)
        self._run_button.clicked.connect(self._run_selected)
        actions_row.addWidget(self._open_button)
        actions_row.addWidget(self._preview_button)
        actions_row.addWidget(self._run_button)
        actions_row.setStretchFactor(self._open_button, 1)
        actions_row.setStretchFactor(self._preview_button, 1)
        actions_row.setStretchFactor(self._run_button, 2)
        actions_container = QFrame(self)
        actions_container.setObjectName("actionsContainer")
        actions_container_layout = QVBoxLayout(actions_container)
        actions_container_layout.setContentsMargins(0, 0, 0, 0)
        actions_container_layout.setSpacing(8)
        actions_container_layout.addLayout(actions_row)
        layout.addWidget(actions_container, alignment=Qt.AlignHCenter)
        layout.addSpacing(8)
        self._details_label = QLabel("No saved automations yet. Create one from Home.", self)
        self._details_label.setObjectName("automationDetailsLabel")
        self._details_label.setStyleSheet(
            "font-size: 13px; color: #6b6b6b;border-top: 1px solid #e5e7eb; padding-top: 8px;"
        )
        self._details_label.setWordWrap(True)
        layout.addWidget(self._details_label, alignment=Qt.AlignHCenter)
        self._refresh()

    # ------------------------------------------------------------------ state

    def _set_running(self, running: bool) -> None:
        self._open_button.setEnabled(not running)
        self._preview_button.setEnabled(not running)
        self._run_button.setEnabled(not running)

    def _thread_finished(self) -> None:
        self._worker = None
        self._thread = None
        self._set_running(False)

    # ------------------------------------------------------------ read paths

    def _show_workflow_details(self, workflow: Workflow) -> None:
        lines = [f"{workflow.name} ({workflow.workflow_id})"]
        lines.extend(f"{step.kind.value} - {step.name}: {step.message}" for step in workflow.steps)
        self._details_label.setText("\n".join(lines))

    def _on_selection_changed(self) -> None:
        self.workflow_selected.emit()
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            self._details_label.setText("Select an automation to see its details.")
            return
        row_path = item.data(Qt.UserRole)
        if row_path is None:
            return
        try:
            workflow = self._service.load(Path(row_path))
        except WorkflowValidationError as error:
            # Row navigation stays modal-free; the message is shown inline.
            self._details_label.setText(f"Could not show '{item.text()}': {error}")
            return
        self._show_workflow_details(workflow)

    def _open_selected(self) -> None:
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            return
        saved_path = Path(item.data(Qt.UserRole))
        try:
            workflow = self._service.load(saved_path)
        except WorkflowValidationError as error:
            self._show_page_error(str(error))
            return
        self._show_workflow_details(workflow)
        self.opened_workflow.emit(saved_path)

    def _preview_selected(self) -> None:
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            return
        saved_path = Path(item.data(Qt.UserRole))
        try:
            workflow = self._service.load(saved_path)
        except WorkflowValidationError as error:
            self._show_page_error(str(error))
            return
        try:
            preview = self._service.preview_replay(workflow)
        except WorkflowValidationError as error:
            self._show_page_error(str(error))
            return
        lines = [f"Preview (read-only): {workflow.name} ({preview.workflow_id})"]
        lines.extend(f" - {step}" for step in preview.steps)
        if preview.executable:
            lines.append("Status: this replay can be executed.")
        else:
            lines.append("Status: this replay contains unsupported actions and cannot be executed.")
        self._details_label.setText("\n".join(lines))
        self.preview_requested.emit()

    # ----------------------------------------------------------- run (mutating)

    def _run_selected(self) -> None:
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            return
        saved_path = Path(item.data(Qt.UserRole))
        try:
            workflow = self._service.load(saved_path)
        except WorkflowValidationError as error:
            self._show_page_error(str(error))
            return
        answer = QMessageBox.question(
            self,
            "Confirm run",
            f"Run '{workflow.name}' now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        self.run_requested.emit(saved_path)
        self._start_run(workflow)

    def _start_run(self, workflow: Workflow) -> None:
        if self._thread is not None:
            return
        self._details_label.setText(f"Running '{workflow.name}'...")
        self._set_running(True)
        self._thread = QThread(self)
        self._worker = WorkflowWorker(self._service, workflow)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_run_progress)
        self._worker.finished.connect(self._on_run_finished)
        self._worker.finished.connect(self._quit_run_thread)
        self._worker.failed.connect(self._on_run_failed)
        self._worker.failed.connect(self._quit_run_thread)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _quit_run_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()

    def _on_run_progress(self, step_result: object) -> None:
        evidence = (
            f" [{'; '.join(step_result.evidence)}]" if step_result.evidence else ""  # type: ignore[attr-defined]
        )
        line = (
            f"{step_result.step_id}: {step_result.status.value}"  # type: ignore[attr-defined]
            f" - {step_result.message}{evidence}"  # type: ignore[attr-defined]
        )
        self._details_label.setText(f"{self._details_label.text()}\n{line}")

    def _on_run_finished(self, run: object) -> None:
        self._details_label.setText(
            f"Run {run.status.value}: {len(run.results)} steps recorded."  # type: ignore[attr-defined]
        )

    def _on_run_failed(self, message: str) -> None:
        self._details_label.setText(f"Error: {message}")
        QMessageBox.warning(self, "Workflow error", message)

    def _show_page_error(self, message: str) -> None:
        self._details_label.setText(f"Error: {message}")
        QMessageBox.warning(self, "Workflow error", message)

    # ---------------------------------------------------------------- refresh

    def refresh(self) -> None:
        """Reload the saved workflow list shown on this page."""
        self._refresh()

    def _refresh(self) -> None:
        self._workflow_list.clear()
        if self._service is None:
            self._details_label.setText("No saved automations yet. Create one from Home.")
            return
        saved_paths = tuple(self._service.list_saved())
        for path in saved_paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, path)
            self._workflow_list.addItem(item)
        if not saved_paths:
            self._details_label.setText("No saved automations yet. Create one from Home.")
            return
        self._details_label.setText("Select an automation to see its details.")

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh()
