"""Step schema v4: intent fields, versioning and migration on save.

Written before the implementation; every test here fails until
``engine/workflow.py`` and ``storage/workflows.py`` gain the new fields and the
schema version bump.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.errors import WorkflowValidationError
from engine.workflow import (
    ExpectedKind,
    ExpectedOutcome,
    StepDescriptor,
    StepKind,
    WaitBudget,
    WaitCondition,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)
from storage.workflows import load_workflow, save_workflow, workflow_from_dict, workflow_to_dict

V3_FILE = {
    "schema_version": 3,
    "workflow_id": "legacy",
    "name": "Legacy workflow",
    "steps": [
        {
            "step_id": "check",
            "name": "Check output",
            "kind": "VERIFY_PATH_EXISTS",
            "message": "The output exists.",
            "target": "C:/work/out.txt",
            "max_attempts": 2,
            "postcondition": "PATH_EXISTS",
            "timeout_seconds": 12.0,
        }
    ],
}


def descriptor_step(**overrides: object) -> WorkflowStep:
    values: dict[str, object] = {
        "step_id": "edit",
        "name": "Edit invoice 1042",
        "kind": StepKind.CLICK_UI_ELEMENT,
        "message": "Open the invoice.",
        "target": '{"window": {"title": "Invoices"}, "element": {"name": "Edit"}}',
        "descriptor": StepDescriptor(
            surface=_desktop(),
            clues=(
                _clue("AUTOMATION_ID", "edit-1042", "id"),
                _clue("NAME", "Edit", "name"),
            ),
            position_hint=(120, 340),
        ),
        "expected": ExpectedOutcome(ExpectedKind.WINDOW_TITLE, "Invoice 1042"),
        "safety": _reversible(),
        "wait": WaitBudget(WaitCondition.ELEMENT_ENABLED, 8.0, 0.25),
    }
    values.update(overrides)
    return WorkflowStep(**values)  # type: ignore[arg-type]


def _desktop():  # type: ignore[no-untyped-def]
    from engine.resolve.models import Surface

    return Surface.DESKTOP


def _reversible():  # type: ignore[no-untyped-def]
    from engine.resolve.models import SafetyClass

    return SafetyClass.REVERSIBLE


def _clue(kind: str, value: str, group: str):  # type: ignore[no-untyped-def]
    from engine.resolve.models import Clue, ClueKind

    return Clue(ClueKind(kind), value, group)


# ----------------------------------------------------------------- old files


def test_schema_three_file_loads_without_the_new_fields(tmp_path: Path) -> None:
    path = tmp_path / "v3.json"
    path.write_text(json.dumps(V3_FILE), encoding="utf-8")

    workflow = load_workflow(path)

    step = workflow.steps[0]
    assert step.descriptor is None
    assert step.wait is None
    assert step.postcondition is not None
    assert step.expected is not None and step.expected.kind is ExpectedKind.PATH_EXISTS


LEGACY_STEP_BY_VERSION = {
    1: {"step_id": "note", "name": "Note", "kind": "REPORT", "message": "Recorded."},
    2: {
        "step_id": "note",
        "name": "Note",
        "kind": "REPORT",
        "message": "Recorded.",
        "target": None,
        "max_attempts": 1,
        "postcondition": None,
    },
    3: {
        "step_id": "note",
        "name": "Note",
        "kind": "REPORT",
        "message": "Recorded.",
        "target": None,
        "max_attempts": 1,
        "postcondition": None,
        "timeout_seconds": 30.0,
    },
}


@pytest.mark.parametrize("schema_version", [1, 2, 3])
def test_every_older_schema_still_loads(tmp_path: Path, schema_version: int) -> None:
    payload = {
        "schema_version": schema_version,
        "workflow_id": f"v{schema_version}",
        "name": f"Schema {schema_version}",
        "steps": [LEGACY_STEP_BY_VERSION[schema_version]],
    }
    path = tmp_path / f"v{schema_version}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    workflow = load_workflow(path)

    step = workflow.steps[0]
    assert step.step_id == "note"
    assert step.descriptor is None and step.wait is None and step.expected is None


def test_old_file_is_migrated_on_save_not_on_load(tmp_path: Path) -> None:
    path = tmp_path / "v3.json"
    path.write_text(json.dumps(V3_FILE), encoding="utf-8")

    loaded = load_workflow(path)
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 3

    save_workflow(loaded, path)
    migrated = json.loads(path.read_text(encoding="utf-8"))

    assert migrated["schema_version"] == 4
    assert "expected" in migrated["steps"][0]
    assert "safety" in migrated["steps"][0]
    assert "descriptor" in migrated["steps"][0]


# -------------------------------------------------------------- round trips


def test_a_step_with_every_new_field_round_trips_losslessly(tmp_path: Path) -> None:
    workflow = Workflow("smart", "Smart workflow", (descriptor_step(),))
    path = tmp_path / "smart.json"

    save_workflow(workflow, path)
    loaded = load_workflow(path)

    assert loaded == workflow
    assert workflow_to_dict(loaded) == workflow_to_dict(workflow)


#: Kinds that are valid without a target, so the round trip needs no fixture.
TARGETLESS_KINDS = (StepKind.REPORT, StepKind.FAIL)


@pytest.mark.parametrize("kind", TARGETLESS_KINDS)
def test_every_targetless_kind_round_trips_without_new_fields(kind: StepKind) -> None:
    workflow = Workflow("plain", "Plain", (WorkflowStep("s", "Step", kind, "Message"),))

    loaded = workflow_from_dict(workflow_to_dict(workflow))

    assert loaded == workflow


@pytest.mark.parametrize("kind", list(StepKind))
def test_every_step_kind_derives_a_safety_class(kind: StepKind) -> None:
    from engine.workflow import READ_ONLY_STEP_KINDS

    step = WorkflowStep("s", "Step", kind, "Message")

    assert step.safety is not None
    if kind in READ_ONLY_STEP_KINDS:
        assert step.safety.value == "READ_ONLY"
    else:
        assert step.safety.value == "DESTRUCTIVE"


@pytest.mark.parametrize("kind", list(ExpectedKind))
def test_every_expected_kind_round_trips(kind: ExpectedKind) -> None:
    from engine.workflow import VALUE_REQUIRED_EXPECTATIONS

    value = "expected text" if kind in VALUE_REQUIRED_EXPECTATIONS else ""
    path_kind = kind is ExpectedKind.PATH_EXISTS
    step = WorkflowStep(
        "s",
        "Step",
        StepKind.VERIFY_PATH_EXISTS if path_kind else StepKind.REPORT,
        "Message",
        "C:/work/out.txt" if path_kind else None,
        expected=ExpectedOutcome(kind, value),
    )

    loaded = workflow_from_dict(workflow_to_dict(Workflow("w", "W", (step,))))

    assert loaded.steps[0].expected == step.expected


# ----------------------------------------------------------- newer versions


def test_a_newer_schema_version_is_refused_with_a_clear_message() -> None:
    payload = dict(V3_FILE)
    payload["schema_version"] = 99

    with pytest.raises(WorkflowValidationError) as raised:
        workflow_from_dict(payload)

    message = str(raised.value)
    assert "newer version" in message
    assert "99" in message


# ------------------------------------------------------- strict descriptor


def test_a_descriptor_with_unknown_clue_fields_is_refused() -> None:
    payload = workflow_to_dict(Workflow("w", "W", (descriptor_step(),)))
    payload["steps"][0]["descriptor"]["clues"][0]["weight"] = 50

    with pytest.raises(WorkflowValidationError):
        workflow_from_dict(payload)


def test_a_descriptor_with_only_a_position_is_refused() -> None:
    """Coordinates must never be the only reason a target is identified."""
    with pytest.raises(WorkflowValidationError):
        WorkflowRunner.validate(
            Workflow(
                "w",
                "W",
                (
                    descriptor_step(
                        descriptor=StepDescriptor(
                            surface=_desktop(),
                            clues=(_clue("POSITION", "120,340", "position"),),
                            position_hint=(120, 340),
                        )
                    ),
                ),
            )
        )


def test_an_unknown_safety_class_is_refused() -> None:
    payload = workflow_to_dict(Workflow("w", "W", (descriptor_step(),)))
    payload["steps"][0]["safety"] = "PROBABLY_FINE"

    with pytest.raises(WorkflowValidationError):
        workflow_from_dict(payload)


def test_a_contradictory_postcondition_and_expected_outcome_is_refused() -> None:
    from engine.workflow import PostconditionKind

    step = descriptor_step(
        postcondition=PostconditionKind.PATH_EXISTS,
        expected=ExpectedOutcome(ExpectedKind.TEXT_APPEARS, "Saved"),
    )

    with pytest.raises(WorkflowValidationError):
        WorkflowRunner.validate(Workflow("w", "W", (step,)))


def test_descriptor_without_any_clue_is_refused() -> None:
    with pytest.raises(WorkflowValidationError):
        WorkflowRunner.validate(
            Workflow(
                "w",
                "W",
                (descriptor_step(descriptor=StepDescriptor(surface=_desktop(), clues=())),),
            )
        )


def test_wait_budget_bounds_are_enforced() -> None:
    with pytest.raises(WorkflowValidationError):
        WorkflowRunner.validate(
            Workflow(
                "w",
                "W",
                (descriptor_step(wait=WaitBudget(WaitCondition.ELEMENT_PRESENT, 0.1, 0.2)),),
            )
        )


# ------------------------------------------------------------ safety default


def test_an_undeclared_safety_class_is_never_treated_as_reversible() -> None:
    """A mutating step with no declared class must be confirmed, not trusted."""
    from engine.resolve.models import SafetyClass

    step = WorkflowStep("s", "Click", StepKind.CLICK_UI_ELEMENT, "Click it")

    assert step.safety is SafetyClass.DESTRUCTIVE


def test_a_read_only_step_derives_a_read_only_class() -> None:
    from engine.resolve.models import SafetyClass

    step = WorkflowStep("s", "Inspect", StepKind.INSPECT_PATH, "Look", "C:/work")

    assert step.safety is SafetyClass.READ_ONLY
