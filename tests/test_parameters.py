"""Values asked at run time: {name} in a step, answered by the person running it."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.components.parameter_dialog import ParameterDialog
from ui.components.parameters import (
    apply_parameter_values,
    missing_values,
    parameter_names,
)


def _workflow() -> Workflow:
    return Workflow(
        "rename-note",
        "Save a note called {name}",
        (
            WorkflowStep(
                "type",
                "Type the note",
                StepKind.TYPE_TEXT,
                "Type once test into the note {name}.",
                target='{"text": "{name}", "element": {"name": "Document"}}',
            ),
        ),
    )


def test_parameter_names_are_unique_and_ordered() -> None:
    assert parameter_names(_workflow()) == ("name",)
    assert parameter_names(
        Workflow(
            "two",
            "Two",
            (
                WorkflowStep("a", "A {first}", StepKind.REPORT, "for {second}"),
                WorkflowStep("b", "B {first}", StepKind.REPORT, "again"),
            ),
        )
    ) == ("first", "second")


def test_values_are_substituted_everywhere_before_the_run() -> None:
    filled = apply_parameter_values(_workflow(), {"name": "today"})

    assert "{name}" not in filled.steps[0].target
    assert '"text": "today"' in filled.steps[0].target
    assert filled.steps[0].message == "Type once test into the note today."
    assert filled.name == "Save a note called today"


def test_a_blank_or_nested_value_is_refused() -> None:
    workflow = _workflow()
    assert missing_values(workflow, {"name": "   "}) == ("name",)
    assert missing_values(workflow, {"name": "{other}"}) == ("name",)
    assert missing_values(workflow, {"name": "today"}) == ()


def test_the_dialog_asks_one_field_per_value_and_refuses_blank_answers(qtbot) -> None:
    QApplication.instance() or QApplication([])
    dialog = ParameterDialog(("name", "folder"), parent=None)
    qtbot.addWidget(dialog)

    assert set(dialog._fields) == {"name", "folder"}

    QTest_type(dialog._fields["name"], "today")
    dialog.accept()
    # folder was left empty, so the answers are not usable.
    assert dialog.values() == {"name": "today", "folder": ""}


def QTest_type(field, text: str) -> None:
    """Type into a QLineEdit the way a person would."""
    field.setText(text)
    field.setFocus(Qt.FocusReason.OtherFocusReason)
