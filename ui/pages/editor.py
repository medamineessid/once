"""Visual editor page for creating and updating linear automations."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
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
from engine.errors import WorkflowValidationError
from engine.workflow import Workflow
from ui.components.banner import Banner
from ui.editor.canvas import CanvasView
from ui.styles import SPACING_LG, SPACING_XL


class EditorPage(QWidget):
    """Edit a validated workflow through controller operations only."""

    saved = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._session: WorkflowEditorSession | None = None
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
        self._name_input = QLineEdit(self)
        self._name_input.setPlaceholderText("Automation name")
        self._name_input.setText("New automation")
        layout.addWidget(self._name_input)
        self._canvas = CanvasView(self)
        self._canvas.setMinimumHeight(220)
        layout.addWidget(self._canvas)
        self._steps_list = QListWidget(self)
        self._steps_list.setObjectName("editorStepsList")
        layout.addWidget(self._steps_list)
        actions = QHBoxLayout()
        self._add_button = QPushButton("Add step", self)
        self._add_button.clicked.connect(self._add_step)
        self._undo_button = QPushButton("Undo", self)
        self._undo_button.clicked.connect(self._undo)
        self._redo_button = QPushButton("Redo", self)
        self._redo_button.clicked.connect(self._redo)
        self._save_button = QPushButton("Save automation", self)
        self._save_button.clicked.connect(self._save)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.clicked.connect(self.cancelled.emit)
        for button in (
            self._add_button,
            self._undo_button,
            self._redo_button,
            self._save_button,
            self._cancel_button,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service

    def start_new(self) -> None:
        self._session = WorkflowEditorSession(
            Workflow(f"automation-{uuid4().hex}", "New automation", ())
        )
        self._name_input.setText("New automation")
        self._banner.hide()
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
            self._refresh()

    def _redo(self) -> None:
        if self._session is not None and self._session.can_redo:
            self._session.redo()
            self._refresh()

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
        self.saved.emit()

    def _refresh(self) -> None:
        if self._session is None:
            return
        workflow = self._session.workflow()
        self._steps_list.clear()
        for index, step in enumerate(workflow.steps, start=1):
            self._steps_list.addItem(f"{index}. {step.name} — {step.message}")
        self._canvas.set_workflow(workflow)
        self._undo_button.setEnabled(self._session.can_undo)
        self._redo_button.setEnabled(self._session.can_redo)
