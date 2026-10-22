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
