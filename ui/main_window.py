"""Main window for saved workflow execution and history inspection."""

from __future__ import annotations

import time
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ai.approval import ApprovedProposal, WorkflowPreview, approve_proposal, preview_proposal
from ai.interview import InterviewSession, InterviewState
from ai.models import AnalysisRequest, ProviderDraft
from ai.provider import deterministic_demo_provider
from controller.recording import RecordingService
from controller.service import WorkflowService
from controller.verifier_config import VerifierConfig
from engine.errors import AIProviderError, WorkflowValidationError
from engine.replay import ReplayPreview
from engine.workflow import StepKind, Workflow, WorkflowRun, WorkflowStep
from recorder.drafts import build_raw_draft
from ui.review_view import ProposalReviewPanel
from ui.workers import WorkflowWorker

WINDOW_TITLE = "Once"
STARTUP_MESSAGE = "Choose a saved workflow or run the local demo."


class MainWindow(QMainWindow):
    """Top-level view that delegates workflow operations to the controller."""

    def __init__(
        self,
        service: WorkflowService | None = None,
        recording_service: RecordingService | None = None,
        verifier_config: VerifierConfig | None = None,
        verifier_note: str | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self._service = service or WorkflowService()
        self._recording_service = recording_service
        self._current_workflow: Workflow | None = None
        self._authorized_root: Path | None = None
        self._replay_preview: ReplayPreview | None = None
        self._status_label = QLabel(STARTUP_MESSAGE, self)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._workflow_list = QListWidget(self)
        self._history_list = QListWidget(self)
        self._result_list = QListWidget(self)
        self._draft_list = QListWidget(self)
        self._recording_list = QListWidget(self)
        self._recording_events = QListWidget(self)
        self._proposal_list = QListWidget(self)
        self._run_button = QPushButton("Preview selected replay", self)
        self._run_button.setObjectName("replayPreviewButton")
        self._choose_root_button = QPushButton("Choose authorized folder", self)
        self._choose_root_button.setObjectName("chooseAuthorizedFolderButton")
        self._execute_replay_button = QPushButton("Execute approved replay", self)
        self._execute_replay_button.setObjectName("executeApprovedReplayButton")
        self._execute_replay_button.setEnabled(False)
        self._authorized_root_label = QLabel("Authorized folder: none selected", self)
        self._demo_button = QPushButton("Run local demo", self)
        self._cancel_button = QPushButton("Cancel run", self)
        self._record_button = QPushButton("Record", self)
        self._stop_record_button = QPushButton("Stop recording", self)
        self._stop_record_button.setEnabled(False)
        self._cancel_button.setEnabled(False)
        self._open_button = QPushButton("Open workflow JSON", self)
        self._save_button = QPushButton("Save current workflow", self)
        self._create_button = QPushButton("Create workflow from form", self)
        self._add_step_button = QPushButton("Add step to draft", self)
        self._move_up_button = QPushButton("Move step up", self)
        self._move_down_button = QPushButton("Move step down", self)
        self._remove_step_button = QPushButton("Remove step", self)
        self._analyze_button = QPushButton("Analyze selected recording (offline)", self)
        self._delete_recording_button = QPushButton("Delete selected recording", self)
        self._answer_button = QPushButton("Submit answer", self)
        self._approve_button = QPushButton("Approve and save proposal", self)
        self._answer_input = QLineEdit(self)
        self._question_label = QLabel("No interview question is active.", self)
        self._proposal_goal = QLabel("No proposal is loaded.", self)
        self._workflow_name = QLineEdit(self)
        self._step_name = QLineEdit(self)
        self._step_message = QLineEdit(self)
        self._step_kind = QComboBox(self)
        self._step_kind.addItems([StepKind.REPORT.value, StepKind.FAIL.value])
        self._draft_steps: list[WorkflowStep] = []
        self._thread: QThread | None = None
        self._worker: WorkflowWorker | None = None

        self._workflow_list.currentItemChanged.connect(self._select_workflow)
        self._run_button.clicked.connect(self._preview_selected_replay)
        self._choose_root_button.clicked.connect(self._choose_authorized_root)
        self._execute_replay_button.clicked.connect(self._execute_replay)
        self._demo_button.clicked.connect(self._run_demo)
        self._cancel_button.clicked.connect(self._cancel_run)
        self._record_button.clicked.connect(self._start_recording)
        self._stop_record_button.clicked.connect(self._stop_recording)
        self._open_button.clicked.connect(self._open_workflow)
        self._save_button.clicked.connect(self._save_current)
        self._create_button.clicked.connect(self._create_from_form)
        self._add_step_button.clicked.connect(self._add_step)
        self._move_up_button.clicked.connect(lambda: self._move_draft_step(-1))
        self._move_down_button.clicked.connect(lambda: self._move_draft_step(1))
        self._remove_step_button.clicked.connect(self._remove_draft_step)
        self._history_list.currentRowChanged.connect(self._show_history_details)
        self._recording_list.currentRowChanged.connect(self._show_recording)
        self._analyze_button.clicked.connect(self._analyze_recording)
        self._delete_recording_button.clicked.connect(self._delete_recording)
        self._answer_button.clicked.connect(self._answer_interview)
        self._approve_button.clicked.connect(self._approve_proposal)
        self._answer_button.setEnabled(False)
        self._approve_button.setEnabled(False)
        self._interview: InterviewSession | None = None
        self._proposal: ProviderDraft | None = None

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
            self._record_button,
            self._stop_record_button,
            self._open_button,
            self._save_button,
        ):
            actions.addWidget(button)
        layout = QVBoxLayout()
        layout.addWidget(self._status_label)
        layout.addLayout(form)
        layout.addWidget(self._add_step_button)
        layout.addWidget(self._draft_list)
        draft_actions = QHBoxLayout()
        for button in (self._move_up_button, self._move_down_button, self._remove_step_button):
            draft_actions.addWidget(button)
        layout.addLayout(draft_actions)
        layout.addWidget(self._create_button)
        layout.addWidget(QLabel("Saved recordings (local, observed and redacted)", self))
        layout.addWidget(self._recording_list)
        layout.addWidget(QLabel("Observed event timeline (not executable input)", self))
        layout.addWidget(self._recording_events)
        layout.addWidget(self._analyze_button)
        layout.addWidget(self._delete_recording_button)
        layout.addWidget(self._question_label)
        layout.addWidget(self._answer_input)
        layout.addWidget(self._answer_button)
        layout.addWidget(self._proposal_goal)
        layout.addWidget(
            QLabel("Proposed steps are AI inferences; permission status is shown.", self)
        )
        layout.addWidget(self._proposal_list)
        layout.addWidget(self._approve_button)
        layout.addWidget(QLabel("Saved workflows (approved proposals remain policy-gated)", self))
        layout.addWidget(self._workflow_list)
        replay_actions = QHBoxLayout()
        replay_actions.addWidget(self._run_button)
        replay_actions.addWidget(self._choose_root_button)
        replay_actions.addWidget(self._execute_replay_button)
        layout.addLayout(replay_actions)
        layout.addWidget(self._authorized_root_label)
        layout.addWidget(self._demo_button)
        layout.addWidget(self._cancel_button)
        layout.addWidget(self._open_button)
        layout.addWidget(self._save_button)
        layout.addWidget(QLabel("Execution history", self))
        layout.addWidget(self._history_list)
        layout.addWidget(QLabel("Latest step results", self))
        layout.addWidget(self._result_list)
        central = QWidget(self)
        central.setLayout(layout)
        self._review_panel = ProposalReviewPanel(
            self._service, verifier_config=verifier_config, verifier_note=verifier_note
        )
        tabs = QTabWidget(self)
        tabs.addTab(central, "Workflows")
        tabs.addTab(self._review_panel, "Agent proposals")
        self.setCentralWidget(tabs)
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
        self._recording_list.clear()
        if self._recording_service is not None:
            self._recording_list.addItems(self._recording_service.list_recordings())

    def _select_workflow(self, current: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        if current is None:
            self._current_workflow = None
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        try:
            self._current_workflow = self._service.load(Path(path))
            self._replay_preview = None
            self._execute_replay_button.setEnabled(False)
            self._status_label.setText(f"Loaded: {self._current_workflow.name}")
        except WorkflowValidationError as error:
            self._current_workflow = None
            self._show_error(str(error))

    def _run_selected(self) -> None:
        self._preview_selected_replay()

    def _preview_selected_replay(self) -> None:
        if self._current_workflow is None:
            self._show_error("Select a saved workflow before previewing it.")
            return
        try:
            self._replay_preview = self._service.preview_replay(self._current_workflow)
        except WorkflowValidationError as error:
            self._show_error(str(error))
            return
        self._result_list.clear()
        self._result_list.addItems(self._replay_preview.steps)
        if self._replay_preview.executable:
            self._status_label.setText(
                "Replay preview ready. Choose a folder, then confirm execution."
            )
        else:
            self._status_label.setText(
                "Replay preview contains unsupported actions. It cannot be executed."
            )
        self._update_execute_replay_enabled()

    def _choose_authorized_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose authorized folder")
        if not directory:
            return
        self._authorized_root = Path(directory)
        self._authorized_root_label.setText(f"Authorized folder: {self._authorized_root}")
        self._update_execute_replay_enabled()

    def _update_execute_replay_enabled(self) -> None:
        self._execute_replay_button.setEnabled(
            self._replay_preview is not None
            and self._replay_preview.executable
            and self._authorized_root is not None
        )

    def _execute_replay(self) -> None:
        if self._current_workflow is None or self._authorized_root is None:
            self._show_error("Preview a supported workflow and choose an authorized folder first.")
            return
        if (
            QMessageBox.question(
                self,
                "Confirm replay",
                "Execute the approved read-only replay in the selected folder?",
            )
            is not QMessageBox.StandardButton.Yes
        ):
            return
        self._start_run(
            self._current_workflow,
            replay=True,
            allowed_root=self._authorized_root,
        )

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
            self._draft_list.clear()
            self._refresh()
        except WorkflowValidationError as error:
            self._show_error(str(error))

    def _run_demo(self) -> None:
        self._start_run(self._service.demo_workflow())

    def _start_run(
        self,
        workflow: Workflow,
        *,
        replay: bool = False,
        allowed_root: Path | None = None,
    ) -> None:
        if self._thread is not None:
            self._show_error("A workflow is already running.")
            return
        self._set_running(True)
        self._thread = QThread(self)
        self._worker = WorkflowWorker(
            self._service,
            workflow,
            replay=replay,
            allowed_root=allowed_root,
        )
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

    def _thread_finished(self) -> None:
        self._worker = None
        self._thread = None
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        for button in (
            self._run_button,
            self._choose_root_button,
            self._execute_replay_button,
            self._demo_button,
            self._open_button,
            self._save_button,
            self._create_button,
            self._add_step_button,
            self._move_up_button,
            self._move_down_button,
            self._remove_step_button,
            self._record_button,
        ):
            button.setEnabled(not running)
        self._cancel_button.setEnabled(running)
        self._stop_record_button.setEnabled(
            False
            if running
            else self._recording_service is not None and self._recording_service.recording
        )

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

    def _show_recording(self, row: int) -> None:
        if self._recording_service is None or row < 0:
            return
        try:
            recording = self._recording_service.load(self._recording_list.item(row).text())
        except WorkflowValidationError as error:
            self._show_error(str(error))
            return
        self._recording_events.clear()
        for event in recording.events:
            element = event.element
            metadata = (
                f" element={element.control_type or 'unknown'}:{element.name or 'unnamed'}"
                if element
                else ""
            )
            redaction = " [password data omitted]" if element and element.is_password else ""
            self._recording_events.addItem(
                f"#{event.sequence} {event.kind.value} at {event.timestamp_ns}{metadata}{redaction}"
            )

    def _analyze_recording(self) -> None:
        if self._recording_service is None or self._recording_list.currentRow() < 0:
            self._show_error("Select a saved recording before analyzing it.")
            return
        try:
            recording = self._recording_service.load(self._recording_list.currentItem().text())
        except WorkflowValidationError as error:
            self._show_error(str(error))
            return
        self._interview = InterviewSession(
            deterministic_demo_provider(),
            AnalysisRequest(build_raw_draft(recording)),
        )
        self._proposal = None
        self._proposal_list.clear()
        self._proposal_goal.setText("Offline analysis is active. No cloud data was sent.")
        self._show_interview_state(self._interview.start())

    def _delete_recording(self) -> None:
        if self._recording_service is None or self._recording_list.currentRow() < 0:
            self._show_error("Select a saved recording before deleting it.")
            return
        recording_id = self._recording_list.currentItem().text()
        try:
            self._recording_service.delete(recording_id)
        except WorkflowValidationError as error:
            self._show_error(str(error))
            return
        self._recording_events.clear()
        self._status_label.setText(f"Recording deleted: {recording_id}")
        self._refresh()

    def _answer_interview(self) -> None:
        if self._interview is None:
            return
        try:
            state = self._interview.answer(self._answer_input.text())
        except AIProviderError as error:
            self._show_error(str(error))
            return
        self._answer_input.clear()
        self._show_interview_state(state)

    def _show_interview_state(self, state: InterviewState) -> None:
        self._question_label.setText(state.question or "Interview complete. Review the proposal.")
        self._answer_button.setEnabled(not state.complete)
        self._proposal = state.draft
        self._approve_button.setEnabled(state.draft is not None)
        if state.draft is not None:
            preview = preview_proposal(state.draft)
            self._show_preview(preview)

    def _show_preview(self, preview: WorkflowPreview) -> None:
        self._proposal_goal.setText(f"Goal: {preview.goal}")
        self._proposal_list.clear()
        self._proposal_list.addItems(preview.steps)

    def _approve_proposal(self) -> None:
        if self._proposal is None:
            self._show_error("No proposal is ready for approval.")
            return
        try:
            approved: ApprovedProposal = approve_proposal(self._proposal)
            path = self._service.save_approved(approved)
        except WorkflowValidationError as error:
            self._show_error(str(error))
            return
        self._status_label.setText(f"Approved workflow saved: {path.name}")
        self._refresh()
        self._refresh()

    def _add_step(self) -> None:
        step_name = self._step_name.text().strip()
        message = self._step_message.text().strip()
        kind = StepKind(self._step_kind.currentText())
        self._draft_steps.append(
            WorkflowStep(f"step-{len(self._draft_steps) + 1}", step_name, kind, message)
        )
        self._render_draft()
        self._status_label.setText(f"Draft contains {len(self._draft_steps)} step(s).")

    def _render_draft(self) -> None:
        self._draft_list.clear()
        for step in self._draft_steps:
            self._draft_list.addItem(f"{step.step_id}: {step.name} ({step.kind.value})")

    def _move_draft_step(self, offset: int) -> None:
        index = self._draft_list.currentRow()
        target = index + offset
        if index < 0 or target < 0 or target >= len(self._draft_steps):
            return
        self._draft_steps[index], self._draft_steps[target] = (
            self._draft_steps[target],
            self._draft_steps[index],
        )
        self._render_draft()
        self._draft_list.setCurrentRow(target)

    def _remove_draft_step(self) -> None:
        index = self._draft_list.currentRow()
        if index < 0:
            return
        self._draft_steps.pop(index)
        self._draft_steps = [
            WorkflowStep(f"step-{position}", step.name, step.kind, step.message, step.target)
            for position, step in enumerate(self._draft_steps, start=1)
        ]
        self._render_draft()

    def _show_history_details(self, row: int) -> None:
        runs = self._service.history()
        if row < 0 or row >= len(runs):
            return
        run = runs[row]
        self._result_list.clear()
        for result in run.results:
            self._show_step_result(result)

    @staticmethod
    def _history_text(run: WorkflowRun) -> str:
        return f"{run.workflow_id} — {run.status.value} — {len(run.results)} steps"

    def _show_error(self, message: str) -> None:
        self._status_label.setText(f"Error: {message}")
        QMessageBox.warning(self, "Workflow error", message)

    def _start_recording(self) -> None:
        if self._recording_service is None:
            self._show_error("Recording is not configured for this application instance.")
            return
        try:
            self._recording_service.start(f"recording-{time.time_ns()}")
        except RuntimeError as error:
            self._show_error(str(error))
            return
        self._record_button.setEnabled(False)
        self._stop_record_button.setEnabled(True)
        self._status_label.setText("Recording is active. Press Stop recording when finished.")

    def _stop_recording(self) -> None:
        if self._recording_service is None:
            return
        try:
            recording = self._recording_service.stop()
        except RuntimeError as error:
            self._show_error(str(error))
            return
        self._record_button.setEnabled(True)
        self._stop_record_button.setEnabled(False)
        self._status_label.setText(
            f"Recording saved: {recording.recording_id} ({len(recording.events)} events)"
        )
        self._refresh()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._recording_service is not None and self._recording_service.recording:
            self._recording_service.stop()
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
        self._service.close()
        event.accept()
