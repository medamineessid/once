"""Tests for the Qt-free workflow editor session."""

from __future__ import annotations

import random

import pytest

from controller.editor import WorkflowEditorSession
from controller.service import WorkflowService
from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowStep


def _workflow() -> Workflow:
    return Workflow(
        "editor-flow",
        "Editor flow",
        (
            WorkflowStep("first", "First", StepKind.REPORT, "one"),
            WorkflowStep("second", "Second", StepKind.FAIL, "two"),
        ),
    )


def test_editor_operations_are_atomic_and_undoable() -> None:
    session = WorkflowEditorSession(_workflow())

    session.rename_workflow("Renamed")
    session.rename_step("first", "Updated first")
    session.update_step("first", message="changed")
    session.move_step("second", -1)
    assert [step.step_id for step in session.workflow().steps] == ["second", "first"]
    assert session.workflow().name == "Renamed"
    assert session.can_undo

    before_invalid = session.workflow()
    with pytest.raises(WorkflowValidationError):
        session.update_step("first", max_attempts=0)
    assert session.workflow() == before_invalid

    while session.can_undo:
        session.undo()
    assert session.workflow() == _workflow()
    assert session.can_redo
    session.redo()
    assert session.workflow().name == "Renamed"


def test_insert_delete_duplicate_and_add_step_preserve_order() -> None:
    session = WorkflowEditorSession(_workflow())

    session.insert_step(
        WorkflowStep("inserted", "Inserted", StepKind.REPORT, "middle"),
        index=1,
    )
    session.duplicate_step("inserted")
    session.add_step_after(None)
    assert [step.step_id for step in session.workflow().steps] == [
        "step-1",
        "first",
        "inserted",
        "inserted-copy",
        "second",
    ]

    session.delete_step("inserted-copy")
    assert "inserted-copy" not in {step.step_id for step in session.workflow().steps}


def test_notes_and_positions_are_separate_from_definition_history() -> None:
    session = WorkflowEditorSession(_workflow())
    session.set_note("first", "Helpful note")
    session.move_node("first", 12.5, 40.0)
    session.rename_workflow("Changed")

    assert session.note("first") == "Helpful note"
    assert session.node_position("first") == (12.5, 40.0)
    session.undo()
    assert session.workflow() == _workflow()
    assert session.note("first") == "Helpful note"
    assert session.node_position("first") == (12.5, 40.0)


def test_save_and_load_round_trip_through_service(tmp_path) -> None:
    service = WorkflowService(workflow_directory=tmp_path / "workflows")
    session = WorkflowEditorSession(_workflow())
    session.rename_workflow("Saved editor flow")

    path = session.save(service)
    loaded = WorkflowEditorSession.load(service, path)

    assert loaded.workflow() == session.workflow()
    assert service.load(path) == session.workflow()


def test_seeded_edit_sequences_keep_unique_ids_and_valid_workflows() -> None:
    session = WorkflowEditorSession(_workflow())
    generator = random.Random(42)  # noqa: S311

    for _ in range(50):
        steps = session.workflow().steps
        operation = generator.randrange(3)
        if operation == 0:
            session.add_step_after(None)
        elif operation == 1 and steps:
            session.move_step(steps[generator.randrange(len(steps))].step_id, 1)
        elif steps:
            session.duplicate_step(steps[generator.randrange(len(steps))].step_id)
        if len(session.workflow().steps) > 20:
            session.delete_step(session.workflow().steps[-1].step_id)

    assert len({step.step_id for step in session.workflow().steps}) == len(session.workflow().steps)
