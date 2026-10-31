"""Tests for the Qt-free workflow editor session."""

from __future__ import annotations

import ast
import json
import random
from pathlib import Path

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


@pytest.mark.parametrize(
    "edit",
    [
        lambda session: session.rename_workflow("Renamed"),
        lambda session: session.rename_step("first", "Renamed step"),
        lambda session: session.update_step("first", message="Changed"),
        lambda session: session.insert_step(
            WorkflowStep("inserted", "Inserted", StepKind.REPORT, "middle"), 1
        ),
        lambda session: session.add_step_after("first"),
        lambda session: session.delete_step("first"),
        lambda session: session.duplicate_step("first"),
        lambda session: session.move_step("second", -1),
    ],
    ids=(
        "rename-workflow",
        "rename-step",
        "update",
        "insert",
        "add",
        "delete",
        "duplicate",
        "move",
    ),
)
def test_each_definition_operation_has_undo_redo_identity(edit) -> None:
    session = WorkflowEditorSession(_workflow())
    original = session.workflow()

    edit(session)
    edited = session.workflow()
    session.undo()
    assert session.workflow() == original
    session.redo()
    assert session.workflow() == edited


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


def test_editor_op_sequences_keep_valid_linear_graph_invariants() -> None:
    session = WorkflowEditorSession(_workflow())
    generator = random.Random(42)  # noqa: S311

    for _ in range(50):
        steps = session.workflow().steps
        if generator.randrange(2):
            session.add_step_after(None)
        elif steps:
            session.move_step(steps[generator.randrange(len(steps))].step_id, 1)
        if len(session.workflow().steps) > 20:
            session.delete_step(session.workflow().steps[-1].step_id)
        ids = [step.step_id for step in session.workflow().steps]
        assert len(ids) == len(set(ids))
        assert all(step.step_id for step in session.workflow().steps)


@pytest.mark.parametrize("schema_version", [1, 2, 3])
def test_existing_workflow_schema_corpus_opens_and_round_trips(tmp_path, schema_version) -> None:
    path = tmp_path / f"schema-{schema_version}.json"
    step = {
        "step_id": "step-1",
        "name": "Report",
        "kind": "REPORT",
        "message": "Done",
    }
    if schema_version >= 2:
        step.update({"target": None, "max_attempts": 1, "postcondition": None})
    if schema_version >= 3:
        step["timeout_seconds"] = 30.0
    path.write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "workflow_id": "corpus",
                "name": "Corpus workflow",
                "steps": [step],
            }
        ),
        encoding="utf-8",
    )
    service = WorkflowService(workflow_directory=tmp_path / "saved")
    session = WorkflowEditorSession.load(service, path)
    saved = session.save(service)
    assert WorkflowEditorSession.load(service, saved).workflow() == session.workflow()


def test_editor_architecture_has_no_qt_or_ui_imports() -> None:
    source = (
        Path(__file__).parents[1].joinpath("controller", "editor.py").read_text(encoding="utf-8")
    )
    tree = ast.parse(source)
    imports = [
        node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert all(not name.startswith(("PySide6", "ui")) for name in imports if name)
