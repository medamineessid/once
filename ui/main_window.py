"""Main window for saved workflow execution and history inspection."""

from __future__ import annotations

from pathlib import Path
from typing import override

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowRun, WorkflowStep
from ui.workers import WorkflowWorker

WINDOW_TITLE = "Once"
STARTUP_MESSAGE = "Choose a saved workflow or run the local demo."


class MainWindow(QMainWindow):
    """Top-level view that delegates workflow operations to the controller."""

    def __init__(self, service: WorkflowService | None = None) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self._service = service or WorkflowService()
        self._current_workflow: Workflow | None = None
        self._status_label = QLabel(STARTUP_MESSAGE, self)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._workflow_list = QListWidget(self)
        self._history_list = QListWidget(self)
        self._result_list = QListWidget(self)
        self._run_button = QPushButton("Run selected workflow", self)
        self._demo_button = QPushButton("Run local demo", self)
        self._cancel_button = QPushButton("Cancel run", self)
        self._cancel_button.setEnabled(False)
        self._open_button = QPushButton("Open workflow JSON", self)
        self._save_button = QPushButton("Save current workflow", self)
        self._create_button = QPushButton("Create workflow from form", self)
        self._add_step_button = QPushButton("Add step to draft", self)
        self._workflow_name = QLineEdit(self)
        self._step_name = QLineEdit(self)
        self._step_message = QLineEdit(self)
        self._step_kind = QComboBox(self)
        self._step_kind.addItems([StepKind.REPORT.value, StepKind.FAIL.value])
        self._draft_steps: list[WorkflowStep] = []
        self._thread: QThread | None = None
        self._worker: WorkflowWorker | None = None

        self._workflow_list.currentItemChanged.connect(self._select_workflow)
        self._run_button.clicked.connect(self._run_selected)
        self._demo_button.clicked.connect(self._run_demo)
        self._cancel_button.clicked.connect(self._cancel_run)
        self._open_button.clicked.connect(self._open_workflow)
        self._save_button.clicked.connect(self._save_current)
        self._create_button.clicked.connect(self._create_from_form)
        self._add_step_button.clicked.connect(self._add_step)

        form = QFormLayout()
        form.addRow("Workflow name", self._workflow_name)
        form.addRow("Step name", self._step_name)
        form.addRow("Step message", self._step_message)
        form.addRow("Step type", self._step_kind)
        actions = QHBoxLayout()
        for button in (
            self._run_button,
            self._demo_button,
            self._cancel_button,
            self._open_button,
            self._save_button,
        ):
            actions.addWidget(button)
        layout = QVBoxLayout()
        layout.addWidget(self._status_label)
        layout.addLayout(form)
        layout.addWidget(self._add_step_button)
        layout.addWidget(self._create_button)
        layout.addWidget(QLabel("Saved workflows", self))
        layout.addWidget(self._workflow_list)
        layout.addLayout(actions)
        layout.addWidget(QLabel("Execution history", self))
        layout.addWidget(self._history_list)
        layout.addWidget(QLabel("Latest step results", self))
        layout.addWidget(self._result_list)
        central = QWidget(self)
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.resize(800, 600)
        self._refresh()

    def _refresh(self) -> None:
        self._workflow_list.clear()
        for path in self._service.list_saved():
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._workflow_list.addItem(item)
        self._history_list.clear()
        for run in self._service.history():
            self._history_list.addItem(self._history_text(run))

    def _select_workflow(self, current: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        if current is None:
            self._current_workflow = None
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        try:
            self._current_workflow = self._service.load(Path(path))
            self._status_label.setText(f"Loaded: {self._current_workflow.name}")
        except WorkflowValidationError as error:
            self._current_workflow = None
            self._show_error(str(error))

    def _run_selected(self) -> None:
        if self._current_workflow is None:
            self._show_error("Select a saved workflow before running it.")
            return
        self._start_run(self._current_workflow)

    def _create_from_form(self) -> None:
        name = self._workflow_name.text().strip()
        step_name = self._step_name.text().strip()
        message = self._step_message.text().strip()
        workflow_id = "-".join(name.casefold().split())
        kind = StepKind(self._step_kind.currentText())
        steps = tuple(self._draft_steps) or (WorkflowStep("step-1", step_name, kind, message),)
        self._current_workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            steps=steps,
        )
        try:
            path = self._service.save(self._current_workflow)
            self._status_label.setText(f"Created and saved: {path.name}")
            self._draft_steps.clear()
            self._refresh()
        except WorkflowValidationError as error:
            self._show_error(str(error))

    def _run_demo(self) -> None:
        self._start_run(self._service.demo_workflow())

    def _start_run(self, workflow: Workflow) -> None:
        if self._thread is not None:
            self._show_error("A workflow is already running.")
            return
        self._set_running(True)
        self._thread = QThread(self)
        self._worker = WorkflowWorker(self._service, workflow)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._show_step_result)
        self._worker.finished.connect(self._show_run)
        self._worker.finished.connect(self._finish_run)
        self._worker.failed.connect(self._show_error)
        self._worker.failed.connect(self._finish_run)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self._thread.start()

    def _cancel_run(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._status_label.setText("Cancellation requested.")

    def _finish_run(self, _value: object) -> None:
        if self._thread is not None:
            self._thread.quit()
        self._set_running(False)

    def _thread_finished(self) -> None:
        self._worker = None
        self._thread = None

    def _set_running(self, running: bool) -> None:
        for button in (
            self._run_button,
            self._demo_button,
            self._open_button,
            self._save_button,
            self._create_button,
            self._add_step_button,
        ):
            button.setEnabled(not running)
        self._cancel_button.setEnabled(running)

    def _show_step_result(self, result: object) -> None:
        step_result = result
        evidence = f" [{'; '.join(step_result.evidence)}]" if step_result.evidence else ""
        self._result_list.addItem(
            f"{step_result.step_id}: {step_result.status.value} — {step_result.message}{evidence}"
        )

    def _open_workflow(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open workflow", "", "Workflow JSON (*.json)"
        )
        if not filename:
            return
        try:
            workflow = self._service.load(Path(filename))
            self._current_workflow = workflow
            self._service.save(workflow)
            self._status_label.setText(f"Opened: {workflow.name}")
            self._refresh()
        except WorkflowValidationError as error:
            self._show_error(str(error))

    def _save_current(self) -> None:
        if self._current_workflow is None:
            self._show_error("Load or select a workflow before saving it.")
            return
        try:
            path = self._service.save(self._current_workflow)
            self._status_label.setText(f"Saved: {path.name}")
            self._refresh()
        except WorkflowValidationError as error:
            self._show_error(str(error))

    def _show_run(self, run: WorkflowRun) -> None:
        self._status_label.setText(f"{run.status.value}: {len(run.results)} steps recorded")
        self._result_list.clear()
        for result in run.results:
            self._show_step_result(result)
        self._refresh()

    def _add_step(self) -> None:
        step_name = self._step_name.text().strip()
        message = self._step_message.text().strip()
        kind = StepKind(self._step_kind.currentText())
        self._draft_steps.append(
            WorkflowStep(f"step-{len(self._draft_steps) + 1}", step_name, kind, message)
        )
        self._status_label.setText(f"Draft contains {len(self._draft_steps)} step(s).")

    @staticmethod
    def _history_text(run: WorkflowRun) -> str:
        return f"{run.workflow_id} — {run.status.value} — {len(run.results)} steps"

    def _show_error(self, message: str) -> None:
        self._status_label.setText(f"Error: {message}")
        QMessageBox.warning(self, "Workflow error", message)

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
        self._service.close()
        event.accept()
