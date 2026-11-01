"""Closable right-hand inspector panel for the visual editor (A2a).

The inspector is a read-only summary of the selected step, or of the whole
automation when nothing is selected. It never mutates the workflow: editing
happens only through controller operations (A2b). Mutating kinds say that
approval is needed at run time; the engine's approval gate stays untouched.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from engine.replay import MUTATING_DESKTOP_KINDS
from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.strings import (
    EDITOR_INSPECTOR_KIND_MUTATING,
    EDITOR_INSPECTOR_KIND_READ_ONLY,
    EDITOR_INSPECTOR_MUTATING_NOTE,
    EDITOR_INSPECTOR_NO_TARGET,
    EDITOR_INSPECTOR_TARGET_UNREADABLE,
)
from ui.styles import SPACING_MD, SPACING_SM


def _target_text(step: WorkflowStep) -> str:
    """Render a step target in plain language (no raw JSON noise)."""
    if not step.target:
        return EDITOR_INSPECTOR_NO_TARGET
    if step.kind in (StepKind.INSPECT_PATH, StepKind.VERIFY_PATH_EXISTS):
        return step.target
    try:
        parsed = json.loads(step.target)
    except json.JSONDecodeError, TypeError:
        return EDITOR_INSPECTOR_TARGET_UNREADABLE
    if isinstance(parsed, dict):
        pairs = ", ".join(f"{key}={value}" for key, value in sorted(parsed.items()))
        return pairs or EDITOR_INSPECTOR_NO_TARGET
    return EDITOR_INSPECTOR_TARGET_UNREADABLE


class InspectorPanel(QScrollArea):
    """Closable summary panel that describes the current selection."""

    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setFixedWidth(240)
        # Enter on a selected node focuses this panel (page wiring), so it
        # must accept keyboard focus.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._content = QWidget(self)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        self._content_layout.setSpacing(SPACING_SM)
        self._summary_label = QLabel("Select a step to see its details.", self._content)
        self._summary_label.setObjectName("inspectorSummary")
        self._summary_label.setWordWrap(True)
        self._content_layout.addWidget(self._summary_label)
        self._content_layout.addStretch(1)
        self._close_button = QPushButton("Close", self._content)
        self._close_button.setObjectName("inspectorClose")
        self._close_button.clicked.connect(self._on_close)
        self._content_layout.addWidget(self._close_button)
        self.setWidget(self._content)

    # ------------------------------------------------------------ content

    @property
    def summary_text(self) -> str:
        """Everything currently shown in the panel (for tests and review)."""
        return self._summary_label.text()

    def show_step(self, step: WorkflowStep) -> None:
        """Populate the panel with a read-only summary of one step."""
        self.show()
        is_mutating = step.kind in MUTATING_DESKTOP_KINDS
        kind_note = (
            EDITOR_INSPECTOR_KIND_MUTATING if is_mutating else EDITOR_INSPECTOR_KIND_READ_ONLY
        )
        lines = [
            f"Name: {step.name} ({step.step_id})",
            f"Kind: {step.kind.value} \u2014 {kind_note}",
            f"Target: {_target_text(step)}",
            f"Timeout: {step.timeout_seconds:g} seconds",
        ]
        if is_mutating:
            lines.append(EDITOR_INSPECTOR_MUTATING_NOTE)
        self._summary_label.setText("\n".join(lines))

    def show_automation(self, workflow: Workflow) -> None:
        """Populate the panel with a summary of the whole automation."""
        self.show()
        step_count = len(workflow.steps)
        self._summary_label.setText(
            f"{workflow.name} \u2014 {step_count} step{'s' if step_count != 1 else ''}."
            " Select a step on the canvas to see its details."
        )

    # ------------------------------------------------------------ closing

    def _on_close(self) -> None:
        self.hide()
        self.close_requested.emit()
