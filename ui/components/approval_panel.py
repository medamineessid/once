"""Desktop approval panel — the one approval surface for desktop automations.

An automation that contains desktop-mutating steps can only start a run
through this panel: it lists exactly the mutating steps (via the
engine/desktop.py gate helpers), Approve works only while the list is
shown, and Approve calls the existing explicit gate
`approve_desktop_workflow`. The panel never executes anything itself; it
only produces a `DesktopApproval` for the run flow. Read-only automations
show no panel: `show_for` reports False and the run flow continues without
approval.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from engine.desktop import (
    approve_desktop_workflow,
    mutating_kind_names,
    requires_desktop_approval,
)
from engine.errors import OnceError
from engine.replay import MUTATING_DESKTOP_KINDS
from engine.workflow import StepKind, Workflow
from ui.strings import (
    DESKTOP_APPROVAL_APPROVE,
    DESKTOP_APPROVAL_BINDING_NOTE,
    DESKTOP_APPROVAL_CANCEL,
    DESKTOP_APPROVAL_KIND_CLICK_UI_ELEMENT,
    DESKTOP_APPROVAL_KIND_CLOSE_APPLICATION,
    DESKTOP_APPROVAL_KIND_FALLBACK,
    DESKTOP_APPROVAL_KIND_INTERACT_PAGE_ELEMENT,
    DESKTOP_APPROVAL_KIND_LAUNCH_APPLICATION,
    DESKTOP_APPROVAL_KIND_LAUNCH_BROWSER,
    DESKTOP_APPROVAL_KIND_NAVIGATE_BROWSER,
    DESKTOP_APPROVAL_KIND_PRESS_SHORTCUT,
    DESKTOP_APPROVAL_KIND_TYPE_TEXT,
    DESKTOP_APPROVAL_LEAD,
    DESKTOP_APPROVAL_REJECTED_TITLE,
    DESKTOP_APPROVAL_STEP_TEMPLATE,
    DESKTOP_APPROVAL_STEPS_HEADING,
    DESKTOP_APPROVAL_TITLE,
)
from ui.styles import SPACING_LG, SPACING_SM

_KIND_NAMES: dict[StepKind, str] = {
    StepKind.LAUNCH_APPLICATION: DESKTOP_APPROVAL_KIND_LAUNCH_APPLICATION,
    StepKind.CLOSE_APPLICATION: DESKTOP_APPROVAL_KIND_CLOSE_APPLICATION,
    StepKind.CLICK_UI_ELEMENT: DESKTOP_APPROVAL_KIND_CLICK_UI_ELEMENT,
    StepKind.TYPE_TEXT: DESKTOP_APPROVAL_KIND_TYPE_TEXT,
    StepKind.PRESS_SHORTCUT: DESKTOP_APPROVAL_KIND_PRESS_SHORTCUT,
    StepKind.LAUNCH_BROWSER: DESKTOP_APPROVAL_KIND_LAUNCH_BROWSER,
    StepKind.NAVIGATE_BROWSER: DESKTOP_APPROVAL_KIND_NAVIGATE_BROWSER,
    StepKind.INTERACT_PAGE_ELEMENT: DESKTOP_APPROVAL_KIND_INTERACT_PAGE_ELEMENT,
}


class DesktopApprovalPanel(QWidget):
    """Show the concrete mutating actions an automation may perform.

    `approved` carries a real `DesktopApproval` produced by the existing
    engine gate; `cancelled` is a bound, local decision to run nothing.
    The panel stays on the page using the calling code's layout.
    """

    approved = Signal(object)
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workflow: Workflow | None = None
        frame = QFrame(self)
        frame.setObjectName("approvalPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(frame)
        panel_layout = QVBoxLayout(frame)
        panel_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        panel_layout.setSpacing(SPACING_SM)

        self._title_label = QLabel(DESKTOP_APPROVAL_TITLE, frame)
        self._title_label.setObjectName("approvalPanelTitle")
        panel_layout.addWidget(self._title_label)

        self._lead_label = QLabel(DESKTOP_APPROVAL_LEAD, frame)
        self._lead_label.setWordWrap(True)
        panel_layout.addWidget(self._lead_label)

        self._steps_heading = QLabel(DESKTOP_APPROVAL_STEPS_HEADING, frame)
        self._steps_heading.setObjectName("approvalPanelStepsHeading")
        panel_layout.addWidget(self._steps_heading)

        self._step_list = QListWidget(frame)
        self._step_list.setObjectName("approvalStepList")
        self._step_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        panel_layout.addWidget(self._step_list)

        self._binding_note = QLabel(DESKTOP_APPROVAL_BINDING_NOTE, frame)
        self._binding_note.setObjectName("approvalPanelBindingNote")
        self._binding_note.setWordWrap(True)
        panel_layout.addWidget(self._binding_note)

        self._rejection_label = QLabel("", frame)
        self._rejection_label.setObjectName("approvalRejectionLabel")
        self._rejection_label.setWordWrap(True)
        self._rejection_label.hide()
        panel_layout.addWidget(self._rejection_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACING_SM)
        self._approve_button = QPushButton(DESKTOP_APPROVAL_APPROVE, frame)
        self._approve_button.setObjectName("primaryActionButton")
        self._approve_button.setMinimumHeight(38)
        self._approve_button.clicked.connect(self._on_approve_clicked)
        buttons.addWidget(self._approve_button)
        self._cancel_button = QPushButton(DESKTOP_APPROVAL_CANCEL, frame)
        self._cancel_button.setObjectName("secondaryActionButton")
        self._cancel_button.setMinimumHeight(38)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        buttons.addWidget(self._cancel_button)
        buttons.addStretch(1)
        panel_layout.addLayout(buttons)

        self.reset()

    # ------------------------------------------------------------- public API

    def show_for(self, workflow: Workflow) -> bool:
        """Show the panel for one automation; False keeps it hidden.

        Read-only automations need no approval, so calling code may run them
        without the panel. Mutating automations get one row per mutating
        step, in workflow order.
        """
        self.reset()
        if not requires_desktop_approval(workflow):
            return False
        self._workflow = workflow
        for step in workflow.steps:
            if not (isinstance(step.kind, StepKind) and step.kind in MUTATING_DESKTOP_KINDS):
                continue
            # Listed by the same membership the engine's gate helpers use, so
            # the list is always exactly the mutating steps; a step kind the
            # UI mapping does not know yet still gets one honest generic row.
            self._step_list.addItem(
                DESKTOP_APPROVAL_STEP_TEMPLATE.format(
                    action=_KIND_NAMES.get(step.kind, DESKTOP_APPROVAL_KIND_FALLBACK),
                    step_name=step.name,
                )
            )
        self.setVisible(True)
        if self._step_list.count() > 0:
            self._approve_button.setEnabled(True)
        return True

    def reset(self) -> None:
        """Discard the shown automation: nothing can be approved any more."""
        self._workflow = None
        self._step_list.clear()
        self._rejection_label.setText("")
        self._rejection_label.hide()
        self._approve_button.setEnabled(False)
        self.setVisible(False)

    def listed_kind_names(self) -> tuple[str, ...]:
        """The mutating step kinds listed for approval, in workflow order."""
        if self.isVisible() and self._workflow is not None:
            return mutating_kind_names(self._workflow)
        return ()

    # --------------------------------------------------------------- slots

    def _on_approve_clicked(self) -> None:
        """Approve works only while the list is shown, through the real gate.

        The gate can also refuse an automation (for example a step kind the
        desktop interaction policy does not allow at all); the refusal is
        shown inline, it never raises into the Qt event loop, and no
        approval is emitted.
        """
        if self._workflow is None or self._step_list.count() == 0:
            return
        workflow = self._workflow
        if self.isVisible():
            self.reset()
        try:
            approval = approve_desktop_workflow(workflow)
        except OnceError as error:
            self.reset()
            self._show_rejection(str(error))
            return
        self.approved.emit(approval)

    def _show_rejection(self, message: str) -> None:
        """Surface a gate refusal in the panel instead of a crash or modal."""
        self.setVisible(True)
        self._rejection_label.setText(f"{DESKTOP_APPROVAL_REJECTED_TITLE}: {message}")
        self._rejection_label.show()

    def _on_cancel_clicked(self) -> None:
        """A decline approval-runs nothing; the panel is simply discarded."""
        self.reset()
        self.cancelled.emit()
