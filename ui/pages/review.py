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
from controller.approvals import ApplicationIdentity
from controller.service import WorkflowService, classify_workflow_steps
from engine.errors import WorkflowValidationError
from engine.workflow import Workflow
from ui.components.banner import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_SUCCESS, Banner
from ui.editor.canvas import CanvasView
from ui.strings import (
    REVIEW_APPROVE,
    REVIEW_APPROVED_BODY,
    REVIEW_APPROVED_TITLE,
    REVIEW_EDIT,
    REVIEW_PREVIEW_PROBLEM_TITLE,
    REVIEW_SAVE_ERROR_TITLE,
    REVIEW_TITLE_DRAFT,
    REVIEW_TITLE_SAVED,
)
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL


class ReviewPage(QWidget):
    """Clean review of a proposed workflow before approval."""

    approved = Signal(object)
    cancelled = Signal()
    edit_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._proposal: ProviderDraft | None = None
        self._saved_workflow: Workflow | None = None
        self._steps_list: QListWidget | None = None
        self._pending_identities: tuple[ApplicationIdentity, ...] = ()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel(REVIEW_TITLE_DRAFT, self)
        self._title_label.setObjectName("pageTitle")
        layout.addWidget(self._title_label, alignment=Qt.AlignHCenter)
        self._banner = Banner(self)
        self._banner.setMinimumWidth(640)
        layout.addWidget(self._banner, alignment=Qt.AlignHCenter)
        self._goal_label = QLabel("No proposal loaded.", self)
        self._goal_label.setObjectName("goalLabel")
        self._goal_label.setWordWrap(True)
        self._goal_label.setMinimumWidth(640)
        self._goal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._goal_label, alignment=Qt.AlignHCenter)
        self._applications_container = QFrame(self)
        self._applications_container.setObjectName("approvalPanel")
        self._applications_container.setMinimumWidth(640)
        applications_layout = QVBoxLayout(self._applications_container)
        applications_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        applications_layout.setSpacing(SPACING_SM)
        self._applications_label = QLabel("This task opens:", self._applications_container)
        self._applications_label.setObjectName("approvalDetails")
        self._applications_label.setWordWrap(True)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(SPACING_SM)
        self._approve_applications = QPushButton(
            "Approve to open it with Once (one-time)", self._applications_container
        )
        self._approve_applications.setObjectName("secondaryActionButton")
        self._approve_applications.setMinimumHeight(34)
        self._approve_applications.clicked.connect(self._approve_applications_once)
        actions_row.addStretch(1)
        actions_row.addWidget(self._approve_applications)
        applications_layout.addWidget(self._applications_label)
        applications_layout.addLayout(actions_row)
        self._applications_container.hide()
        layout.addWidget(self._applications_container, alignment=Qt.AlignHCenter)
        self._steps_list = QListWidget(self)
        self._steps_list.setObjectName("stepsList")
        self._steps_list.setMinimumWidth(640)
        self._steps_list.setWordWrap(True)
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
        self._edit_button = QPushButton(REVIEW_EDIT, self)
        self._edit_button.setObjectName("secondaryActionButton")
        self._edit_button.setMinimumHeight(38)
        self._edit_button.clicked.connect(self._edit_saved_workflow)
        # An unhandled editor hand-off (lane B task B7) keeps the control
        # invisible per the honest-controls rule.
        self._edit_button.hide()
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("secondaryActionButton")
        self._cancel_button.setMinimumHeight(38)
        self._cancel_button.clicked.connect(self._cancel_review)
        self._approve_button = QPushButton(REVIEW_APPROVE, self)
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
        self._approve_button.setVisible(ready and not self._pending_identities)
        self._applications_container.setVisible(ready and bool(self._pending_identities))

    def set_application_identities(self, pending: tuple[ApplicationIdentity, ...]) -> None:
        """Show which recorded applications still need a one-time approval."""
        self._pending_identities = tuple(pending)
        entries = []
        for identity in self._pending_identities:
            path = identity.executable_path or "unknown path"
            entries.append(f"{identity.display_name}  —  {path}")
        listed = "\n".join(entries) if entries else "unknown application"
        self._applications_label.setText(f"This task opens:\n{listed}")
        self._update_action_visibility()

    def application_summary(self, pending: tuple[ApplicationIdentity, ...]) -> str:
        """One-line plain-language summary of the apps the recording opened.

        Used by the shell and tests to render "This task opens <name>, <path>"
        from the recorded identity, never from a hardcoded app-name table.
        """
        if not pending:
            return "This task opens: (already approved)"
        parts = []
        for identity in pending:
            name = identity.display_name
            path = identity.executable_path or "unknown path"
            parts.append(f"{name}, {path}")
        joined = "; ".join(parts)
        return f"This task opens {joined}."

    def set_application_summary(self, summary: str) -> None:
        """Update the applications label with a pre-rendered summary line."""
        self._applications_label.setText(summary)
        self._update_action_visibility()

    def _approve_applications_once(self) -> None:
        if self._service is None or not self._pending_identities:
            return
        for identity in self._pending_identities:
            self._service.approve_application(identity)
        self._pending_identities = ()
        self._applications_label.setText(self.application_summary(()))
        self._update_action_visibility()

    def _cancel_review(self) -> None:
        self.cancelled.emit()

    def _edit_saved_workflow(self) -> None:
        if self._saved_workflow is not None:
            self.edit_requested.emit(self._saved_workflow)

    def _approve(self) -> None:
        if self._service is None or self._proposal is None:
            return
        unapproved = tuple(
            identity
            for identity in self._pending_identities
            if not self._service.is_application_approved(identity)
        )
        if self._pending_identities or unapproved:
            self._banner.show_message(
                SEVERITY_ERROR,
                "One-time approval needed",
                "Approve the application this task opens before saving it.",
            )
            self._update_action_visibility()
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
        self.approved.emit(approved.workflow)

    def show_workflow(self, workflow: Workflow | None) -> None:
        """Show an opened saved workflow for read-only review, like the old window."""
        self._proposal = None
        self._saved_workflow = workflow
        self._pending_identities = ()
        # The opened-workflow mode is "Automation details", not a review: the
        # user is looking at a saved automation (UX audit D14).
        self._title_label.setText(REVIEW_TITLE_SAVED)
        self._edit_button.setVisible(workflow is not None)
        self._approve_button.hide()
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
        self._saved_workflow = None
        self._pending_identities = ()
        self._edit_button.hide()
        self._title_label.setText(REVIEW_TITLE_DRAFT)
        self._canvas.set_workflow(None)
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
        self._canvas.set_workflow(proposal.workflow)
        replayability = classify_workflow_steps(proposal.workflow)
        labels = {item.step_id: item for item in replayability}
        observation_only = [item for item in replayability if not item.replayable]
        for index, step_text in enumerate(preview.steps, start=1):
            step = proposal.workflow.steps[index - 1]
            info = labels.get(step.step_id)
            tag = "Replayable" if (info is not None and info.replayable) else "Observation only"
            reason = info.reason if info else ""
            self._steps_list.addItem(f"{index}. {step_text}  [{tag}: {reason}]")
        if observation_only:
            self._banner.show_message(
                SEVERITY_INFO,
                "Some steps are observation only",
                "Steps marked Observation only will be shown but not performed when the task runs.",
            )
        self._update_action_visibility()

    def set_service(self, service: WorkflowService | None) -> None:
        """Inject the controller service; the shell calls this (task B7)."""
        self._service = service
        self._update_action_visibility()
