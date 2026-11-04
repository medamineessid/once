"""Closable right-hand inspector panel for the visual editor.

The inspector emits typed edits; the controller owns mutation and validation.
Mutating kinds say that approval is needed at run time; the engine's approval
gate stays untouched.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, Signal
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

PREVIEW_DEBOUNCE_MS = 500
PREVIEW_OK_TEXT = "The step as typed is valid. Apply to save it."

# Qt stores combo data as strings, so StrEnum members need a typed read-back.
_COMBO_VALUE_TYPES: Mapping[str, type] = {
    "inspectorField_kind": StepKind,
    "inspectorField_postcondition": PostconditionKind,
}


@dataclass(frozen=True)
class PreviewCandidate:
    """One inspector edit-in-flight, emitted only for validation (never executed)."""

    step_id: str
    values: dict[str, object]


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

    # Typed payloads travel as objects: Qt's dict marshalling would flatten
    # StrEnum items into plain strings.
    close_requested = Signal()
    changes_applied = Signal(object)
    preview_requested = Signal(object)  # a PreviewCandidate, for validation only

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
        self._preview_label = QLabel(self._content)
        self._preview_label.setObjectName("inspectorPreview")
        self._preview_label.setWordWrap(True)
        self._content_layout.addWidget(self._preview_label)
        self._preview_label.hide()
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
        # Live preview state: one debounced candidate per quiet editing pause.
        self._shown_step: WorkflowStep | None = None
        self._populating = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._fire_preview)

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

    @property
    def preview_verdict(self) -> str:
        """The last preview verdict, or an empty string while none is shown."""
        if self._preview_label.isHidden():
            return ""
        return self._preview_label.text()

    def show_step(self, step: WorkflowStep, result: object | None = None) -> None:
        """Populate the panel with validator-backed controls for one step."""
        self.show()
        self._stop_preview()
        with self._loading():
            self._shown_step = step
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
            self._add_kind_field(step.kind)
            self._add_fields_for_kind(step.kind)
        self._apply_button.show()

    def show_automation(self, workflow: Workflow) -> None:
        """Populate the panel with a summary of the whole automation."""
        self.show()
        self._stop_preview()
        self._clear_fields()
        with self._loading():
            self._shown_step = None
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
        self._stop_preview()
        self._clear_fields()
        with self._loading():
            self._shown_step = None
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
                # takeAt releases ownership; deleteLater then destroys the
                # widget and its signal connections, so retired fields can
                # never fire a preview.
                widget.deleteLater()

    @contextmanager
    def _loading(self) -> Iterator[None]:
        """Mark a programmatic populate/rebuild so it never schedules a preview."""
        self._populating = True
        try:
            yield
        finally:
            self._populating = False

    # ------------------------------------------------------------ live preview

    def _schedule_preview(self) -> None:
        """Debounce one user edit into a single candidate preview."""
        if self._populating or self._shown_step is None:
            return
        self._preview_timer.start(PREVIEW_DEBOUNCE_MS)

    def _stop_preview(self) -> None:
        """Drop any pending candidate; used for loads and while running."""
        self._preview_timer.stop()
        self._preview_label.hide()

    def stop_preview(self) -> None:
        """Public entry point so the page can cancel previews while running."""
        self._stop_preview()

    def show_preview(self, ok: bool, text: str) -> None:
        """Show the engine validator's verdict for the current draft values."""
        self._preview_label.setText(PREVIEW_OK_TEXT if ok else text)
        self._preview_label.show()

    def _fire_preview(self) -> None:
        step = self._shown_step
        if self._populating or step is None:
            return
        values: dict[str, object] = {}
        for name in tuple(self._fields):
            values[name] = self._field_value(name)
        self.preview_requested.emit(PreviewCandidate(step.step_id, values))

    def _on_kind_changed(self) -> None:
        """Rebuild retargeted fields, then preview the draft once."""
        if self._populating or self._shown_step is None:
            return
        kind_field = self._fields.get("kind")
        if not isinstance(kind_field, QComboBox):
            return
        kind = self._read_combo(kind_field)
        if not isinstance(kind, StepKind) or kind is self._shown_step.kind:
            return
        preserved = {name: self._field_value(name) for name in tuple(self._fields)}
        with self._loading():
            self._clear_fields()
            self._add_kind_field(kind)
            self._add_fields_for_kind(kind, preserved)
        self._schedule_preview()

    @staticmethod
    def _read_combo(field: QComboBox) -> object:
        """Read combo data with its declared engine type (strings from Qt aside)."""
        data = field.currentData()
        target_class = _COMBO_VALUE_TYPES.get(field.objectName())
        if isinstance(data, str) and target_class is not None:
            try:
                return target_class(data)
            except ValueError:
                return data
        return data

    def _field_value(self, name: str) -> object:
        field = self._fields[name]
        if isinstance(field, QLineEdit):
            return field.text()
        if isinstance(field, (QSpinBox, QDoubleSpinBox)):
            return field.value()
        if isinstance(field, QComboBox):
            return self._read_combo(field)
        return None

    # ------------------------------------------------------------ fields

    def _add_fields_for_kind(
        self, kind: StepKind, preserved: dict[str, object] | None = None
    ) -> None:
        """Build the editing controls the step kind allows, wiring user edits."""
        step = self._shown_step
        if step is None:
            return
        saved = preserved or {}
        name = str(saved.get("name", step.name))
        message = str(saved.get("message", step.message))
        attempts = int(saved.get("max_attempts", step.max_attempts))
        self._add_text_field("name", "Name", name)
        self._add_text_field("message", "Message", message)
        if _has_target(kind):
            target = str(saved["target"]) if "target" in saved else step.target or ""
            self._add_text_field("target", "Target", target)
        self._add_attempts_field(attempts)
        if kind in (StepKind.WAIT_WINDOW, StepKind.WAIT_PAGE):
            timeout = saved.get("timeout_seconds", step.timeout_seconds)
            self._add_timeout_field(float(timeout))
        if kind in (StepKind.INSPECT_PATH, StepKind.VERIFY_PATH_EXISTS):
            postcondition = saved.get("postcondition", step.postcondition)
            self._add_postcondition_field(
                postcondition if isinstance(postcondition, PostconditionKind) else None
            )

    def _add_kind_field(self, kind: StepKind) -> None:
        field = QComboBox(self._form)
        field.setObjectName("inspectorField_kind")
        for member in StepKind:
            field.addItem(member.value, member)
        index = field.findData(kind)
        field.setCurrentIndex(index if index >= 0 else 0)
        field.currentIndexChanged.connect(self._on_kind_changed)
        self._fields["kind"] = field
        self._form_layout.addRow("Kind", field)

    def _add_text_field(self, name: str, label: str, value: str) -> None:
        field = QLineEdit(self._form)
        field.setObjectName(f"inspectorField_{name}")
        field.setText(value)
        # textEdited fires for user edits only: programmatic loads/rebuilds
        # and setText() calls never schedule a preview.
        field.textEdited.connect(self._schedule_preview)
        self._fields[name] = field
        self._form_layout.addRow(label, field)

    def _add_attempts_field(self, value: int) -> None:
        field = QSpinBox(self._form)
        field.setObjectName("inspectorField_max_attempts")
        field.setRange(1, 3)
        field.setValue(value)
        field.valueChanged.connect(self._schedule_preview)
        self._fields["max_attempts"] = field
        self._form_layout.addRow("Attempts", field)

    def _add_timeout_field(self, value: float) -> None:
        field = QDoubleSpinBox(self._form)
        field.setObjectName("inspectorField_timeout_seconds")
        field.setRange(0.5, 60.0)
        field.setSingleStep(0.5)
        field.setDecimals(1)
        field.setValue(value)
        field.valueChanged.connect(self._schedule_preview)
        self._fields["timeout_seconds"] = field
        self._form_layout.addRow("Timeout (seconds)", field)

    def _add_postcondition_field(self, value: PostconditionKind | None) -> None:
        field = QComboBox(self._form)
        field.setObjectName("inspectorField_postcondition")
        field.addItem("None", None)
        field.addItem("Path exists", PostconditionKind.PATH_EXISTS)
        if value is not None:
            index = field.findData(value)
            field.setCurrentIndex(index if index >= 0 else 0)
        field.currentIndexChanged.connect(self._schedule_preview)
        self._fields["postcondition"] = field
        self._form_layout.addRow("Postcondition", field)

    def _on_apply(self) -> None:
        changes: dict[str, object] = {}
        for name in tuple(self._fields):
            changes[name] = self._field_value(name)
        self.changes_applied.emit(changes)

    # ------------------------------------------------------------ closing

    def _on_close(self) -> None:
        self.hide()
        self.close_requested.emit()


def _has_target(kind: StepKind) -> bool:
    return kind not in (StepKind.REPORT, StepKind.FAIL)
