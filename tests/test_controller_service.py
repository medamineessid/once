"""Tests for controller-owned workflow and history access."""

from __future__ import annotations

from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from storage.database import connect
from storage.history import ExecutionHistory


def test_service_saves_lists_loads_and_records_workflows(tmp_path) -> None:
    service = WorkflowService(
        history=ExecutionHistory(connect(tmp_path / "history.db")),
        workflow_directory=tmp_path / "workflows",
    )
    workflow = Workflow(
        "saved-workflow",
        "Saved workflow",
        (WorkflowStep("step", "Step", StepKind.REPORT, "Done"),),
    )

    path = service.save(workflow)
    loaded = service.load(path)
    service.run_workflow(loaded)

    assert service.list_saved() == (path,)
    assert service.history()[0].workflow_id == "saved-workflow"


def test_service_persists_editor_layout_separately(tmp_path) -> None:
    from storage.database import connect

    service = WorkflowService(
        workflow_directory=tmp_path / "workflows",
        layout_connection=connect(tmp_path / "layout.db"),
    )

    service.save_layout("workflow", {"step": (1.0, 2.0)}, {"step": "Note"})

    loaded = service.load_layout("workflow")
    assert loaded.warning is None
    assert loaded.record is not None
    assert loaded.record.node_positions == {"step": (1.0, 2.0)}
    assert loaded.record.notes == {"step": "Note"}
