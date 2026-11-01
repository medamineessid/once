"""Review screen — present a proposed automation for approval."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai.approval import approve_proposal, preview_proposal
from ai.models import ProviderDraft
from controller.service import WorkflowService
from engine.errors import WorkflowValidationError
from engine.workflow import Workflow
from ui.components.banner import SEVERITY_ERROR, SEVERITY_SUCCESS, Banner
from ui.editor.canvas import CanvasView
from ui.strings import (
    REVIEW_APPROVED_BODY,
    REVIEW_APPROVED_TITLE,
    REVIEW_PREVIEW_PROBLEM_TITLE,
    REVIEW_SAVE_ERROR_TITLE,
)
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
        self._banner = Banner(self)
        layout.addWidget(self._banner, alignment=Qt.AlignHCenter)
        self._goal_label = QLabel("No proposal loaded.", self)
        self._goal_label.setObjectName("goalLabel")
        layout.addWidget(self._goal_label, alignment=Qt.AlignHCenter)
        self._steps_list = QListWidget(self)
        self._steps_list.setObjectName("stepsList")
        self._steps_list.setAlternatingRowColors(True)
        self._steps_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._steps_list.addItems(self._empty_steps())
        layout.addWidget(self._steps_list, alignment=Qt.AlignHCenter)
        self._canvas = CanvasView(self)
        self._canvas.setMinimumSize(640, 220)
        layout.addWidget(self._canvas)
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
        # Editing a proposal must go through the shell's editor flow; until the
        # shell wires that hand-off (lane B task B7), an unhandled control stays
        # invisible per the honest-controls rule.
        self._edit_button.hide()
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("secondaryActionButton")
        self._cancel_button.setMinimumHeight(38)
        self._cancel_button.clicked.connect(self._cancel_review)
        self._approve_button = QPushButton("Approve and run", self)
        self._approve_button.setObjectName("primaryActionButton")
        self._approve_button.setMinimumHeight(38)
        self._approve_button.clicked.connect(self._approve)
        # Approve is visible only when the page can actually review and save
        # something: a service is injected and a proposal passed the preview
        # step of the existing approval path (ai.approval.preview_proposal).
        self._approve_button.hide()
        buttons_row.addWidget(self._edit_button)
        buttons_row.addWidget(self._cancel_button)
        buttons_row.addWidget(self._approve_button)
        actions_layout.addLayout(buttons_row)
        layout.addWidget(self._actions_container, alignment=Qt.AlignHCenter)

    def _empty_steps(self) -> list[str]:
        return ["No step details to review."]

    def _update_action_visibility(self) -> None:
        ready = self._service is not None and self._proposal is not None
        self._approve_button.setVisible(ready)

    def _cancel_review(self) -> None:
        self.cancelled.emit()

    def _approve(self) -> None:
        if self._service is None or self._proposal is None:
            return
        try:
            approved = approve_proposal(self._proposal)
            saved_path = self._service.save_approved(approved)
        except WorkflowValidationError as error:
            self._banner.show_message(SEVERITY_ERROR, REVIEW_SAVE_ERROR_TITLE, str(error))
            return
        self._banner.show_message(
            SEVERITY_SUCCESS,
            REVIEW_APPROVED_TITLE,
            REVIEW_APPROVED_BODY.format(name=saved_path.name),
        )
        self.approved.emit()

    def show_workflow(self, workflow: Workflow | None) -> None:
        """Show an opened saved workflow for read-only review, like the old window."""
        self._proposal = None
        self._goal_label.setText(f"Goal: {workflow.name}" if workflow else "No workflow loaded.")
        self._steps_list.clear()
        self._banner.clear()
        # The canvas is read-only for now (P3): the chain renders from the pure
        # auto-layout plan; editing arrives with the editor page.
        self._canvas.set_workflow(workflow)
        if workflow:
            for index, step in enumerate(workflow.steps, start=1):
                self._steps_list.addItem(
                    f"{index}. {step.kind.value} - {step.name}: {step.message}"
                )
        else:
            self._steps_list.addItems(self._empty_steps())
        self._update_action_visibility()

    def load_proposal(self, proposal: ProviderDraft | None) -> None:
        self._banner.clear()
        self._steps_list.clear()
        if proposal is None:
            self._proposal = None
            self._goal_label.setText("No proposal loaded.")
            self._steps_list.addItems(self._empty_steps())
            self._update_action_visibility()
            return
        self._goal_label.setText(f"Goal: {proposal.goal}")
        try:
            preview = preview_proposal(proposal)
        except WorkflowValidationError as error:
            # An unusable draft is untrusted data: explain it in plain
            # language, keep the steps empty, and never offer approval.
            self._proposal = None
            self._steps_list.addItems(self._empty_steps())
            self._banner.show_message(
                SEVERITY_ERROR,
                REVIEW_PREVIEW_PROBLEM_TITLE,
                str(error),
            )
            self._update_action_visibility()
            return
        self._proposal = proposal
        for index, step_text in enumerate(preview.steps, start=1):
            self._steps_list.addItem(f"{index}. {step_text}")
        self._update_action_visibility()

    def set_service(self, service: WorkflowService | None) -> None:
        """Inject the controller service; the shell calls this (task B7)."""
        self._service = service
        self._update_action_visibility()
