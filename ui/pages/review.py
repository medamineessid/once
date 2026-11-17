"""Review screen — present a proposed automation for approval."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai.approval import approve_proposal, preview_proposal
from ai.models import ProviderDraft
from controller.approvals import ApplicationIdentity
from controller.service import WorkflowService, classify_workflow_steps
from engine.errors import OnceError, WorkflowValidationError
from engine.workflow import Workflow
from ui.components.banner import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_SUCCESS, Banner
from ui.components.cards import Chip
from ui.components.delete_confirm import DeleteConfirmDialog, automation_delete_message
from ui.components.formatting import friendly_step_display
from ui.components.hero import MicroLabel
from ui.components.icons import draw_automations_glyph, icon_pixmap
from ui.editor.canvas import CanvasView
from ui.strings import (
    DELETE_ACTION,
    REVIEW_APPROVE,
    REVIEW_APPROVED_BODY,
    REVIEW_APPROVED_TITLE,
    REVIEW_DELETE_ERROR_TITLE,
    REVIEW_EDIT,
    REVIEW_PREVIEW_PROBLEM_TITLE,
    REVIEW_SAVE_ERROR_TITLE,
    REVIEW_TITLE_DRAFT,
    REVIEW_TITLE_SAVED,
)
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL, SPACING_XS


class ReviewPage(QWidget):
    """Clean review of a proposed workflow or details of a saved automation."""

    approved = Signal(object)
    cancelled = Signal()
    edit_requested = Signal(object)
    run_requested = Signal(object)
    automation_deleted = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._proposal: ProviderDraft | None = None
        self._saved_workflow: Workflow | None = None
        self._steps_list: QListWidget | None = None
        self._pending_identities: tuple[ApplicationIdentity, ...] = ()
        self._init_ui()

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("detailsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, SPACING_SM, 0)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop)

        self._micro_label = MicroLabel("0 steps", content)
        layout.addWidget(self._micro_label)
        self._title_label = QLabel(REVIEW_TITLE_DRAFT, content)
        self._title_label.setObjectName("pageTitle")
        layout.addWidget(self._title_label)

        self._banner = Banner(content)
        layout.addWidget(self._banner)

        self._goal_label = QLabel("No proposal loaded.", content)
        self._goal_label.setObjectName("goalLabel")
        self._goal_label.setWordWrap(True)
        layout.addWidget(self._goal_label)

        self._applications_container = QFrame(content)
        self._applications_container.setObjectName("approvalPanel")
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
        layout.addWidget(self._applications_container)

        self._steps_list = QListWidget(content)
        self._steps_list.setObjectName("stepsList")
        self._steps_list.setWordWrap(True)
        self._steps_list.setAlternatingRowColors(False)
        self._steps_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._steps_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._steps_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._steps_list.addItems(self._empty_steps())
        self._resize_steps_list()
        layout.addWidget(self._steps_list)

        self._canvas = CanvasView(content)
        self._canvas.set_minimap_visible(False)
        self._canvas.setMinimumHeight(260)
        layout.addWidget(self._canvas)

        layout.addSpacing(SPACING_MD)
        self._actions_container = QFrame(content)
        actions_layout = QVBoxLayout(self._actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(SPACING_SM)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(SPACING_SM)

        self._cancel_button = QPushButton("Back", content)
        self._cancel_button.setObjectName("secondaryActionButton")
        self._cancel_button.setMinimumHeight(38)
        self._cancel_button.clicked.connect(self._cancel_review)

        self._run_button = QPushButton("Run", content)
        self._run_button.setObjectName("secondaryActionButton")
        self._run_button.setMinimumHeight(38)
        self._run_button.clicked.connect(self._run_saved_workflow)
        self._run_button.hide()

        self._delete_button = QPushButton(DELETE_ACTION, content)
        self._delete_button.setObjectName("secondaryActionButton")
        self._delete_button.setMinimumHeight(38)
        self._delete_button.clicked.connect(self._delete_saved_workflow)
        self._delete_button.hide()

        self._edit_button = QPushButton(REVIEW_EDIT, content)
        self._edit_button.setObjectName("primaryActionButton")
        self._edit_button.setMinimumHeight(38)
        self._edit_button.clicked.connect(self._edit_saved_workflow)
        # An unhandled editor hand-off (lane B task B7) keeps the control
        # invisible per the honest-controls rule.
        self._edit_button.hide()

        self._approve_button = QPushButton(REVIEW_APPROVE, content)
        self._approve_button.setObjectName("primaryActionButton")
        self._approve_button.setMinimumHeight(38)
        self._approve_button.clicked.connect(self._approve)
        self._approve_button.hide()

        buttons_row.addWidget(self._cancel_button)
        buttons_row.addWidget(self._delete_button)
        buttons_row.addStretch(1)
        buttons_row.addWidget(self._run_button)
        buttons_row.addWidget(self._edit_button)
        buttons_row.addWidget(self._approve_button)
        actions_layout.addLayout(buttons_row)
        layout.addWidget(self._actions_container)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _empty_steps(self) -> list[str]:
        return ["No step details to review."]

    def _resize_steps_list(self) -> None:
        """Size _steps_list to show all rows without an inner vertical scrollbar."""
        total = 16
        for i in range(self._steps_list.count()):
            hint = self._steps_list.sizeHintForRow(i)
            total += max(hint, 40) + 4
        self._steps_list.setMinimumHeight(total)
        self._steps_list.setMaximumHeight(total)

    def _add_step_row(
        self,
        index: int,
        step: object,
        *,
        tag: str | None = None,
    ) -> None:
        title, action_label, clean_desc = friendly_step_display(step)
        summary = f"{index}. {action_label}: {title}"
        if clean_desc and clean_desc != title:
            summary += f" — {clean_desc}"
        item = QListWidgetItem(summary)
        self._steps_list.addItem(item)

        row = QFrame(self._steps_list)
        row.setObjectName("reviewStepRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        row_layout.setSpacing(SPACING_SM)

        num_label = QLabel(f"{index}.", row)
        num_label.setObjectName("rowCaption")
        num_label.setFixedWidth(24)

        icon_label = QLabel(row)
        icon_label.setPixmap(icon_pixmap(draw_automations_glyph, 16))
        icon_label.setFixedSize(20, 20)

        kind_chip = Chip(action_label, kind="neutral", parent=row)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(SPACING_XS)

        name_edit = QLineEdit(title, row)
        name_edit.setObjectName("inlineStepEdit")
        name_edit.setPlaceholderText("Step description")
        name_edit.editingFinished.connect(
            lambda idx=index - 1, ed=name_edit: self._on_step_title_edited(idx, ed.text())
        )
        text_col.addWidget(name_edit)

        if clean_desc and clean_desc != title:
            desc_label = QLabel(clean_desc, row)
            desc_label.setObjectName("rowCaption")
            desc_label.setWordWrap(True)
            text_col.addWidget(desc_label)

        row_layout.addWidget(num_label, alignment=Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(kind_chip, alignment=Qt.AlignmentFlag.AlignTop)
        row_layout.addLayout(text_col, stretch=1)
        if tag:
            tag_kind = "ok" if tag == "Replayable" else "neutral"
            row_layout.addWidget(
                Chip(tag, kind=tag_kind, parent=row),
                alignment=Qt.AlignmentFlag.AlignTop,
            )

        item.setSizeHint(row.sizeHint())
        self._steps_list.setItemWidget(item, row)

    def _on_step_title_edited(self, step_index: int, new_title: str) -> None:
        cleaned = new_title.strip()
        if not cleaned:
            return
        if self._saved_workflow is not None and 0 <= step_index < len(self._saved_workflow.steps):
            steps = list(self._saved_workflow.steps)
            steps[step_index] = replace(steps[step_index], name=cleaned[:80])
            updated = replace(self._saved_workflow, steps=tuple(steps))
            self._saved_workflow = updated
            self._canvas.set_workflow(updated)
            if self._service is not None:
                try:
                    self._service.save(updated)
                except WorkflowValidationError as error:
                    self._banner.show_message(SEVERITY_ERROR, REVIEW_SAVE_ERROR_TITLE, str(error))
        elif self._proposal is not None and 0 <= step_index < len(self._proposal.workflow.steps):
            steps = list(self._proposal.workflow.steps)
            steps[step_index] = replace(steps[step_index], name=cleaned[:80])
            updated_wf = replace(self._proposal.workflow, steps=tuple(steps))
            self._proposal = replace(self._proposal, workflow=updated_wf)
            self._canvas.set_workflow(updated_wf)

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

    def _run_saved_workflow(self) -> None:
        if self._saved_workflow is not None:
            self.run_requested.emit(self._saved_workflow)

    def _delete_saved_workflow(self) -> None:
        """Delete this saved automation, naming its runs in the dialog."""
        if self._service is None or self._saved_workflow is None:
            return
        workflow = self._saved_workflow
        run_count = sum(
            1
            for run in self._service.history()
            if getattr(run, "workflow_id", None) == workflow.workflow_id
        )
        choice = DeleteConfirmDialog(
            automation_delete_message(workflow.name, run_count),
            runs_count=run_count,
            parent=self,
        ).ask()
        if not choice.confirmed:
            return
        try:
            self._service.delete_automation(workflow.workflow_id, delete_runs=choice.delete_runs)
        except OnceError as error:
            self._banner.show_message(SEVERITY_ERROR, REVIEW_DELETE_ERROR_TITLE, str(error))
            return
        self.show_workflow(None)
        self.automation_deleted.emit()

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
        """Show an opened saved workflow for review and quick editing/running."""
        self._proposal = None
        self._saved_workflow = workflow
        self._pending_identities = ()
        self._title_label.setText(REVIEW_TITLE_SAVED)
        self._edit_button.setVisible(workflow is not None)
        self._run_button.setVisible(workflow is not None)
        self._delete_button.setVisible(workflow is not None)
        self._approve_button.hide()
        self._goal_label.setText(workflow.name if workflow else "No automation loaded.")
        step_count = len(workflow.steps) if workflow else 0
        self._micro_label.setText(f"{step_count} STEP{'S' if step_count != 1 else ''}")
        self._steps_list.clear()
        self._banner.clear()
        self._canvas.set_workflow(workflow)
        if workflow:
            for index, step in enumerate(workflow.steps, start=1):
                self._add_step_row(index, step)
        else:
            self._steps_list.addItems(self._empty_steps())
        self._resize_steps_list()
        self._update_action_visibility()

    def load_proposal(self, proposal: ProviderDraft | None) -> None:
        self._saved_workflow = None
        self._pending_identities = ()
        self._edit_button.hide()
        self._run_button.hide()
        self._delete_button.hide()
        self._title_label.setText(REVIEW_TITLE_DRAFT)
        self._canvas.set_workflow(None)
        self._banner.clear()
        self._steps_list.clear()
        if proposal is None:
            self._proposal = None
            self._micro_label.setText("0 STEPS")
            self._goal_label.setText("No proposal loaded.")
            self._steps_list.addItems(self._empty_steps())
            self._resize_steps_list()
            self._update_action_visibility()
            return
        step_count = len(proposal.workflow.steps)
        self._micro_label.setText(f"{step_count} STEP{'S' if step_count != 1 else ''}")
        self._goal_label.setText(f"Goal: {proposal.goal}")
        try:
            preview_proposal(proposal)
        except WorkflowValidationError as error:
            self._proposal = None
            self._steps_list.addItems(self._empty_steps())
            self._resize_steps_list()
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
        for index, step in enumerate(proposal.workflow.steps, start=1):
            info = labels.get(step.step_id)
            tag = "Replayable" if (info is not None and info.replayable) else "Note only"
            self._add_step_row(index, step, tag=tag)
        self._resize_steps_list()
        if observation_only:
            self._banner.show_message(
                SEVERITY_INFO,
                "Some steps are notes only",
                "Steps marked Note only are kept for context and do not run actions.",
            )
        self._update_action_visibility()

    def set_service(self, service: WorkflowService | None) -> None:
        """Inject the controller service; the shell calls this (task B7)."""
        self._service = service
        self._update_action_visibility()
