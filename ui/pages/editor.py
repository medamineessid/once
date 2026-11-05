"""Visual editor page for creating and updating linear automations."""

from __future__ import annotations

from dataclasses import replace
from typing import override
from uuid import uuid4

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.editor import WorkflowEditorSession
from controller.service import WorkflowService
from engine.desktop import (
    approve_desktop_workflow,
    mutating_kind_names,
    requires_desktop_approval,
)
from engine.errors import WorkflowValidationError
from engine.workflow import Workflow, WorkflowRunner
from ui.components.banner import Banner
from ui.editor.canvas import CanvasView
from ui.editor.inspector import InspectorPanel, PreviewCandidate
from ui.strings import (
    EDITOR_CANCEL_RUN,
    EDITOR_DISCARD,
    EDITOR_EDIT_ERROR_TITLE,
    EDITOR_RENAME_EMPTY_MESSAGE,
    EDITOR_RENAME_ERROR_TITLE,
    EDITOR_RUN,
    EDITOR_RUN_SAVE_FIRST_BODY,
    EDITOR_RUN_SAVE_FIRST_TITLE,
    EDITOR_SAVE,
    EDITOR_STAY,
    EDITOR_UNSAVED_BODY,
    EDITOR_UNSAVED_TITLE,
)
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL


class EditorPage(QWidget):
    """Edit a validated workflow through controller operations only."""

    saved = Signal()
    cancelled = Signal()
    cancel_run_requested = Signal()
    run_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._session: WorkflowEditorSession | None = None
        self._step_results: dict[str, object] = {}
        self._running = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        self._title = QLabel("Create automation", self)
        self._title.setObjectName("pageTitle")
        layout.addWidget(self._title)
        self._banner = Banner(self)
        layout.addWidget(self._banner)
        self._dirty_panel = QWidget(self)
        dirty_layout = QHBoxLayout(self._dirty_panel)
        dirty_layout.setContentsMargins(0, 0, 0, 0)
        dirty_layout.addWidget(QLabel(f"{EDITOR_UNSAVED_TITLE}: {EDITOR_UNSAVED_BODY}"))
        dirty_layout.addStretch(1)
        dirty_save = QPushButton(EDITOR_SAVE, self._dirty_panel)
        dirty_save.setObjectName("primaryActionButton")
        dirty_discard = QPushButton(EDITOR_DISCARD, self._dirty_panel)
        dirty_discard.setObjectName("secondaryActionButton")
        dirty_stay = QPushButton(EDITOR_STAY, self._dirty_panel)
        dirty_stay.setObjectName("secondaryActionButton")
        dirty_layout.addWidget(dirty_save)
        dirty_layout.addWidget(dirty_discard)
        dirty_layout.addWidget(dirty_stay)
        dirty_save.clicked.connect(self._save)
        dirty_discard.clicked.connect(self._discard)
        dirty_stay.clicked.connect(self._stay)
        layout.addWidget(self._dirty_panel)
        self._dirty_panel.hide()
        self._name_input = QLineEdit(self)
        self._name_input.installEventFilter(self)
        self._name_input.setPlaceholderText("Automation name")
        self._name_input.setText("New automation")
        # The name is edited inline and committed as ONE undoable controller
        # operation when the user presses Enter or leaves the field (A1).
        self._name_input.editingFinished.connect(self._commit_name)
        layout.addWidget(self._name_input)
        self._approval_panel = QFrame(self)
        self._approval_panel.setObjectName("approvalPanel")
        approval_layout = QVBoxLayout(self._approval_panel)
        approval_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        self._approval_title = QLabel("This automation needs your approval", self._approval_panel)
        self._approval_title.setObjectName("approvalTitle")
        self._approval_details = QLabel(self._approval_panel)
        self._approval_details.setWordWrap(True)
        self._approval_details.setObjectName("approvalDetails")
        approval_actions = QHBoxLayout()
        self._approve_run_button = QPushButton("Approve and run", self._approval_panel)
        self._approve_run_button.setObjectName("primaryActionButton")
        self._approve_run_button.clicked.connect(self._approve_and_run)
        self._cancel_approval_button = QPushButton("Not now", self._approval_panel)
        self._cancel_approval_button.setObjectName("secondaryActionButton")
        self._cancel_approval_button.clicked.connect(self._approval_panel.hide)
        approval_actions.addWidget(self._approve_run_button)
        approval_actions.addWidget(self._cancel_approval_button)
        approval_layout.addWidget(self._approval_title)
        approval_layout.addWidget(self._approval_details)
        approval_layout.addLayout(approval_actions)
        layout.addWidget(self._approval_panel)
        self._approval_panel.hide()
        self._canvas = CanvasView(self)
        self._canvas.setMinimumHeight(220)
        self._canvas.installEventFilter(self)
        self._canvas.node_selected.connect(self._on_node_selected)
        self._canvas.node_moved.connect(self._on_node_moved)
        self._canvas.step_activated.connect(self._focus_inspector)
        self._canvas.setMinimumHeight(220)
        self._inspector = InspectorPanel(self)
        self._inspector.installEventFilter(self)
        self._inspector.changes_applied.connect(self._apply_inspector_changes)
        self._inspector.preview_requested.connect(self._on_preview_candidate)
        canvas_and_inspector = QHBoxLayout()
        canvas_and_inspector.addWidget(self._canvas, 1)
        canvas_and_inspector.addWidget(self._inspector)
        layout.addLayout(canvas_and_inspector)
        self._steps_list = QListWidget(self)
        self._steps_list.setObjectName("editorStepsList")
        layout.addWidget(self._steps_list)
        actions = QHBoxLayout()
        self._add_button = QPushButton("Add step", self)
        self._add_button.setObjectName("primaryActionButton")
        self._add_button.clicked.connect(self._add_step)
        self._undo_button = QPushButton("Undo", self)
        self._undo_button.setObjectName("secondaryActionButton")
        self._undo_button.clicked.connect(self._undo)
        self._redo_button = QPushButton("Redo", self)
        self._redo_button.setObjectName("secondaryActionButton")
        self._redo_button.clicked.connect(self._redo)
        self._save_button = QPushButton("Save automation", self)
        self._save_button.setObjectName("primaryActionButton")
        self._save_button.clicked.connect(self._save)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("secondaryActionButton")
        self._cancel_button.clicked.connect(self._cancel_clicked)
        self._run_button = QPushButton(EDITOR_RUN, self)
        self._run_button.setObjectName("primaryActionButton")
        self._run_button.clicked.connect(self._run)
        for button in (
            self._add_button,
            self._undo_button,
            self._redo_button,
            self._save_button,
            self._run_button,
            self._cancel_button,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service

    def _commit_name(self) -> None:
        """Apply the typed name through the controller session; failures stay inline."""
        if self._session is None:
            return
        name = self._name_input.text().strip()
        current_name = self._session.workflow().name
        if not name:
            self._name_input.setText(current_name)
            self._banner.show_message(
                "error", EDITOR_RENAME_ERROR_TITLE, EDITOR_RENAME_EMPTY_MESSAGE
            )
            return
        if name == current_name:
            return
        try:
            self._session.rename_workflow(name)
        except WorkflowValidationError as error:
            self._name_input.setText(current_name)
            self._banner.show_message("error", EDITOR_RENAME_ERROR_TITLE, str(error))
            return
        self._refresh()

    def start_new(self) -> None:
        self._step_results.clear()
        self._session = WorkflowEditorSession(
            Workflow(f"automation-{uuid4().hex}", "New automation", ())
        )
        self._name_input.setText("New automation")
        self._banner.hide()
        self._refresh()

    def open_workflow(self, workflow: Workflow) -> None:
        """Open an existing workflow and restore its presentation metadata."""
        self._session = WorkflowEditorSession(workflow)
        self._step_results.clear()
        if self._service is not None and self._service.layout_storage_configured:
            loaded = self._service.load_layout(workflow.workflow_id)
            if loaded.record is not None:
                self._session.restore_layout(
                    loaded.record.node_positions,
                    loaded.record.notes,
                )
            if loaded.warning:
                self._banner.show_message("warning", "Layout reset", loaded.warning)
        self._name_input.setText(workflow.name)
        self._refresh()

    def _add_step(self) -> None:
        if self._session is None:
            return
        self._session.add_step_after(
            self._session.workflow().steps[-1].step_id if self._session.workflow().steps else None
        )
        self._refresh()

    def _undo(self) -> None:
        if self._session is not None and self._session.can_undo:
            self._session.undo()
            self._sync_name_input()
            self._refresh()

    def _redo(self) -> None:
        if self._session is not None and self._session.can_redo:
            self._session.redo()
            self._sync_name_input()
            self._refresh()

    @override
    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:
        if (
            event.type() is QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and not isinstance(watched, (QLineEdit, QComboBox, QAbstractSpinBox))
        ):
            handlers = {
                Qt.Key.Key_Z: self._undo,
                Qt.Key.Key_Y: self._redo,
                Qt.Key.Key_S: self._save,
            }
            handler = handlers.get(event.key())
            if handler is not None:
                handler()
                return True
        return super().eventFilter(watched, event)

    @staticmethod
    def _text_input_has_focus() -> bool:
        focused = QApplication.focusWidget()
        return isinstance(focused, (QLineEdit, QComboBox, QAbstractSpinBox))

    def _sync_name_input(self) -> None:
        if self._session is not None:
            self._name_input.setText(self._session.workflow().name)

    def _save(self) -> None:
        if self._service is None or self._session is None:
            return
        try:
            self._session.rename_workflow(self._name_input.text().strip())
            self._session.save(self._service)
            if self._service.layout_storage_configured:
                self._service.save_layout(
                    self._session.workflow().workflow_id,
                    self._session.node_positions,
                    self._session.notes,
                    {step.step_id for step in self._session.workflow().steps},
                )
        except (OSError, WorkflowValidationError) as error:
            self._banner.show_message("error", "Could not save automation", str(error))
            return
        self._dirty_panel.hide()
        self.saved.emit()

    def _run(self) -> None:
        if self._session is None:
            return
        if self._session.is_dirty():
            self._banner.show_message(
                "info", EDITOR_RUN_SAVE_FIRST_TITLE, EDITOR_RUN_SAVE_FIRST_BODY
            )
            return
        workflow = self._session.workflow()
        self._step_results.clear()
        self._canvas.clear_step_statuses()
        if requires_desktop_approval(workflow):
            kinds = ", ".join(mutating_kind_names(workflow))
            self._approval_details.setText(
                f"This will control your computer: {kinds}. "
                "Review the steps before allowing them to run."
            )
            self._approval_panel.show()
            return
        self.run_requested.emit(workflow)

    def _approve_and_run(self) -> None:
        if self._session is None:
            return
        try:
            approval = approve_desktop_workflow(self._session.workflow())
        except WorkflowValidationError as error:
            self._banner.show_message("error", "Approval could not be completed", str(error))
            return
        self._approval_panel.hide()
        self.run_requested.emit(approval)

    def show_run_message(self, severity: str, title: str, body: str) -> None:
        self._banner.show_message(severity, title, body)

    def _cancel_clicked(self) -> None:
        if self._running:
            self.cancel_run_requested.emit()
        else:
            self.cancelled.emit()

    def show_step_result(self, result: object) -> None:
        """Render one worker progress result on the canvas and inspector.

        Outcome labels (OBSERVED, OBSERVATION_ONLY) are defined once in
        ui/components/formatting.status_display (docs/contracts/run-outcomes.md)
        and rendered by the inspector's summary line; the canvas keeps the raw
        status so its neutral color decides how an observation looks.
        """
        step_id = getattr(result, "step_id", None)
        if not isinstance(step_id, str) or self._session is None:
            return
        status = getattr(getattr(result, "status", None), "value", "UNKNOWN")
        self._step_results[step_id] = result
        self._canvas.set_step_status(step_id, status)
        if self._canvas.selected_id == step_id:
            self._show_inspector_for(step_id, self._session.workflow())

    def set_running(self, running: bool) -> None:
        """Lock definition controls while the saved definition is executing."""
        self._running = running
        self._cancel_button.setText(EDITOR_CANCEL_RUN if running else "Cancel")
        for button in (
            self._add_button,
            self._undo_button,
            self._redo_button,
            self._save_button,
            self._run_button,
        ):
            button.setEnabled(not running)
        self._canvas.setEnabled(not running)
        self._inspector.setEnabled(not running)
        if running:
            self._inspector.stop_preview()

    def _discard(self) -> None:
        if self._session is None:
            return
        self._session.discard()
        self._banner.clear()
        self._refresh()
        self._dirty_panel.hide()

    def _stay(self) -> None:
        self._dirty_panel.hide()

    def _refresh(self) -> None:
        if self._session is None:
            return
        workflow = self._session.workflow()
        self._steps_list.clear()
        for index, step in enumerate(workflow.steps, start=1):
            self._steps_list.addItem(f"{index}. {step.name} — {step.message}")
        self._canvas.set_workflow(workflow)
        self._show_inspector_for(self._canvas.selected_id, workflow)
        for field_name in self._inspector.field_names:
            self._inspector.field(field_name).installEventFilter(self)
        self._undo_button.setEnabled(self._session.can_undo)
        self._redo_button.setEnabled(self._session.can_redo)
        self._sync_name_input()
        self._dirty_panel.setVisible(self._session.is_dirty())

    # --------------------------------------------------------- inspector (A2a)

    def _on_node_selected(self, node_id: object) -> None:
        """Show the selected step's summary, or the automation summary."""
        if self._session is None:
            return
        if isinstance(node_id, str) and self._canvas.is_terminal(node_id):
            self._inspector.show_terminal("Start" if node_id == "__start__" else "Finish")
            return
        self._show_inspector_for(node_id, self._session.workflow())

    def _apply_inspector_changes(self, changes: dict[str, object]) -> None:
        if self._session is None or self._canvas.selected_id is None:
            return
        try:
            self._session.update_step(self._canvas.selected_id, **changes)
        except WorkflowValidationError as error:
            self._banner.show_message("error", EDITOR_EDIT_ERROR_TITLE, str(error))
            return
        self._banner.clear()
        self._refresh()

    def _on_preview_candidate(self, candidate: object) -> None:
        """Validate one in-flight edit with the engine validator only.

        The candidate is untrusted data: it never mutates the session and it
        is never executed. Results for steps that are no longer selected are
        dropped, and nothing is shown while a run is active.
        """
        if self._running or self._session is None:
            return
        if not isinstance(candidate, PreviewCandidate):
            return
        if self._canvas.selected_id != candidate.step_id:
            return  # the selection changed; this draft is stale
        step_id = candidate.step_id
        step = next((s for s in self._session.workflow().steps if s.step_id == step_id), None)
        if step is None:
            return
        try:
            steps = tuple(
                replace(step_payload, **candidate.values)
                if step_payload.step_id == step_id
                else step_payload
                for step_payload in self._session.workflow().steps
            )
            WorkflowRunner.validate(replace(self._session.workflow(), steps=steps))
        except (WorkflowValidationError, TypeError) as error:
            self._inspector.show_preview(False, str(error))
        else:
            self._inspector.show_preview(True, "")

    def _on_node_moved(self, node_id: object, x: float, y: float) -> None:
        if self._session is None or not isinstance(node_id, str):
            return
        if node_id.startswith("__"):
            return
        try:
            self._session.move_node(node_id, x, y)
        except WorkflowValidationError as error:
            self._banner.show_message("error", EDITOR_EDIT_ERROR_TITLE, str(error))

    def _focus_inspector(self, _node_id: object) -> None:
        """Enter on a selected node moves keyboard focus to the inspector."""
        self._inspector.setFocus()

    def _show_inspector_for(self, node_id: object, workflow) -> None:
        step = None
        if isinstance(node_id, str):
            for candidate in workflow.steps:
                if candidate.step_id == node_id:
                    step = candidate
                    break
        if step is None:
            self._inspector.show_automation(workflow)
        else:
            self._inspector.show_step(step, self._step_results.get(step.step_id))
