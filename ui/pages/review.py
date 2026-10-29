"""Review screen — present a proposed automation for approval."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai.approval import approve_proposal
from ai.models import ProviderDraft
from controller.service import WorkflowService
from engine.errors import WorkflowValidationError
from engine.workflow import Workflow
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL


class ReviewPage(QWidget):
    """Clean review of a proposed workflow before approval."""

    approved = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._proposal: ProviderDraft | None = None
        self._steps_list: QListWidget | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("Review automation", self)
        self._title_label.setObjectName("pageTitle")
        layout.addWidget(self._title_label, alignment=Qt.AlignHCenter)
        self._goal_label = QLabel("No proposal loaded.", self)
        self._goal_label.setObjectName("goalLabel")
        layout.addWidget(self._goal_label, alignment=Qt.AlignHCenter)
        self._steps_list = QListWidget(self)
        self._steps_list.setObjectName("stepsList")
        self._steps_list.setAlternatingRowColors(True)
        self._steps_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._steps_list.addItems(self._empty_steps())
        layout.addWidget(self._steps_list, alignment=Qt.AlignHCenter)
        layout.addSpacing(SPACING_MD)
        self._actions_container = QFrame(self)
        actions_layout = QVBoxLayout(self._actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(SPACING_SM)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(SPACING_SM)
        self._edit_button = QPushButton("Edit", self)
        self._edit_button.setObjectName("secondaryActionButton")
        self._edit_button.setMinimumHeight(38)
        # No handler yet: J6 wires Edit through the approval path. An unfinished
        # feature is hidden, so the button stays unconnected and invisible until
        # then (the honest-controls test rejects pass-only handlers).
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("secondaryActionButton")
        self._cancel_button.setMinimumHeight(38)
        self._cancel_button.clicked.connect(self._cancel_review)
        self._approve_button = QPushButton("Approve and run", self)
        self._approve_button.setObjectName("primaryActionButton")
        self._approve_button.setMinimumHeight(38)
        self._approve_button.clicked.connect(self._approve)
        # Honest-controls rule (2026-10-29): Edit has no real handler and Approve
        # does nothing until this page receives a service and a proposal (J6).
        # An unfinished feature is hidden, not shown inert.
        self._edit_button.hide()
        self._approve_button.hide()
        buttons_row.addWidget(self._edit_button)
        buttons_row.addWidget(self._cancel_button)
        buttons_row.addWidget(self._approve_button)
        actions_layout.addLayout(buttons_row)
        layout.addWidget(self._actions_container, alignment=Qt.AlignHCenter)

    def _empty_steps(self) -> list[str]:
        return ["No step details to review."]

    def _cancel_review(self) -> None:
        self.cancelled.emit()

    def _approve(self) -> None:
        if self._service is None or self._proposal is None:
            return
        try:
            approved = approve_proposal(self._proposal)
            self._service.save_approved(approved)
            self.approved.emit()
        except WorkflowValidationError as error:
            QMessageBox.warning(self, "Approval error", str(error))

    def show_workflow(self, workflow: Workflow | None) -> None:
        """Show an opened saved workflow for read-only review, like the old window."""
        self._proposal = None
        self._goal_label.setText(f"Goal: {workflow.name}" if workflow else "No workflow loaded.")
        self._steps_list.clear()
        if workflow:
            for index, step in enumerate(workflow.steps, start=1):
                self._steps_list.addItem(
                    f"{index}. {step.kind.value} - {step.name}: {step.message}"
                )
        else:
            self._steps_list.addItems(self._empty_steps())

    def load_proposal(self, proposal: ProviderDraft | None) -> None:
        self._proposal = proposal
        self._goal_label.setText(f"Goal: {proposal.goal}" if proposal else "No proposal loaded.")
        self._steps_list.clear()
        if proposal:
            for idx, step_text in enumerate(proposal.steps, start=1):
                self._steps_list.addItem(f"{idx}. {step_text}")
        else:
            self._steps_list.addItems(self._empty_steps())

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
