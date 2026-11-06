"""Closable right-hand inspector panel for the visual editor.

The inspector emits typed edits; the controller owns mutation and validation.
Mutating kinds say that approval is needed at run time; the engine's approval
gate stays untouched.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from engine.replay import MUTATING_DESKTOP_KINDS
from engine.workflow import PostconditionKind, StepKind, Workflow, WorkflowStep
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
    """Closable summary and editing panel for the current selection."""

    close_requested = Signal()
    changes_applied = Signal(dict)

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
        self._form = QWidget(self._content)
        self._form_layout = QFormLayout(self._form)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(SPACING_SM)
        self._content_layout.addWidget(self._form)
        self._apply_button = QPushButton("Apply changes", self._content)
        self._apply_button.setObjectName("inspectorApply")
        self._apply_button.clicked.connect(self._on_apply)
        self._content_layout.addWidget(self._apply_button)
        self._content_layout.addStretch(1)
        self._close_button = QPushButton("Close", self._content)
        self._close_button.setObjectName("inspectorClose")
        self._close_button.clicked.connect(self._on_close)
        self._content_layout.addWidget(self._close_button)
        self.setWidget(self._content)
        self._fields: dict[str, QWidget] = {}
        self._apply_button.hide()

    # ------------------------------------------------------------ content

    @property
    def summary_text(self) -> str:
        """Everything currently shown in the panel (for tests and review)."""
        return self._summary_label.text()

    @property
    def apply_button(self) -> QPushButton:
        return self._apply_button

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(self._fields)

    def field(self, name: str) -> QWidget:
        return self._fields[name]

    def show_step(self, step: WorkflowStep, result: object | None = None) -> None:
        """Populate the panel with validator-backed controls for one step."""
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
        if result is not None:
            status = getattr(getattr(result, "status", None), "value", "UNKNOWN")
            lines.append(f"Run status: {status}")
            message = getattr(result, "message", "")
            if message:
                lines.append(f"Result: {message}")
            evidence = tuple(getattr(result, "evidence", ()))
            if evidence:
                lines.append("Evidence:\n" + "\n".join(evidence))
        self._summary_label.setText("\n".join(lines))
        self._clear_fields()
        self._add_text_field("name", "Name", step.name)
        self._add_text_field("message", "Message", step.message)
        if _has_target(step.kind):
            self._add_text_field("target", "Target", step.target or "")
        self._add_attempts_field(step.max_attempts)
        if step.kind in (StepKind.WAIT_WINDOW, StepKind.WAIT_PAGE):
            self._add_timeout_field(step.timeout_seconds)
        if step.kind in (StepKind.INSPECT_PATH, StepKind.VERIFY_PATH_EXISTS):
            self._add_postcondition_field(step.postcondition)
        self._apply_button.show()

    def show_automation(self, workflow: Workflow) -> None:
        """Populate the panel with a summary of the whole automation."""
        self.show()
        self._clear_fields()
        self._apply_button.hide()
        step_count = len(workflow.steps)
        self._summary_label.setText(
            f"{workflow.name} \u2014 {step_count} step{'s' if step_count != 1 else ''}."
            + (
                " Click Add step below to create your first step."
                if step_count == 0
                else " Select a step on the canvas to see its details."
            )
        )

    def show_terminal(self, terminal: str) -> None:
        """Explain that Start and Finish are fixed canvas markers."""
        self.show()
        self._clear_fields()
        self._apply_button.hide()
        self._summary_label.setText(
            f"{terminal} is a fixed marker. It is not an editable automation step."
        )

    def _clear_fields(self) -> None:
        self._fields.clear()
        while self._form_layout.count():
            item = self._form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_text_field(self, name: str, label: str, value: str) -> None:
        field = QLineEdit(self._form)
        field.setObjectName(f"inspectorField_{name}")
        field.setText(value)
        self._fields[name] = field
        self._form_layout.addRow(label, field)

    def _add_attempts_field(self, value: int) -> None:
        field = QSpinBox(self._form)
        field.setObjectName("inspectorField_max_attempts")
        field.setRange(1, 3)
        field.setValue(value)
        self._fields["max_attempts"] = field
        self._form_layout.addRow("Attempts", field)

    def _add_timeout_field(self, value: float) -> None:
        field = QDoubleSpinBox(self._form)
        field.setObjectName("inspectorField_timeout_seconds")
        field.setRange(0.5, 60.0)
        field.setSingleStep(0.5)
        field.setDecimals(1)
        field.setValue(value)
        self._fields["timeout_seconds"] = field
        self._form_layout.addRow("Timeout (seconds)", field)

    def _add_postcondition_field(self, value: PostconditionKind | None) -> None:
        field = QComboBox(self._form)
        field.setObjectName("inspectorField_postcondition")
        field.addItem("None", None)
        field.addItem("Path exists", PostconditionKind.PATH_EXISTS)
        if value is not None:
            field.setCurrentIndex(field.findData(value))
        self._fields["postcondition"] = field
        self._form_layout.addRow("Postcondition", field)

    def _on_apply(self) -> None:
        changes: dict[str, object] = {}
        for name, field in self._fields.items():
            if isinstance(field, QLineEdit):
                changes[name] = field.text()
            elif isinstance(field, (QSpinBox, QDoubleSpinBox)):
                changes[name] = field.value()
            elif isinstance(field, QComboBox):
                changes[name] = field.currentData()
        self.changes_applied.emit(changes)

    # ------------------------------------------------------------ closing

    def _on_close(self) -> None:
        self.hide()
        self.close_requested.emit()


def _has_target(kind: StepKind) -> bool:
    return kind not in (StepKind.REPORT, StepKind.FAIL)
