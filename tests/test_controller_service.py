"""Tests for controller-owned workflow and history access."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai.approval import ApprovedProposal
from controller.service import WorkflowService, classify_workflow_steps
from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowStep
from storage.database import connect
from storage.history import ExecutionHistory


class _FakeDesktopActions:
    def launch_application(self, target_json: str) -> None:
        return None

    def close_application(self, target_json: str) -> None:
        return None


def _service_with_fakes(tmp_path) -> WorkflowService:
    return WorkflowService(
        history=ExecutionHistory(connect(tmp_path / "history.db")),
        workflow_directory=tmp_path / "workflows",
        desktop_actions=_FakeDesktopActions(),
        browser_actions=_FakeDesktopActions(),
    )


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


def test_classify_workflow_steps_marks_replayable_and_observation_only() -> None:
    workflow = Workflow(
        "mixed",
        "Mixed",
        (
            WorkflowStep("inspect", "Inspect", StepKind.VERIFY_PATH_EXISTS, "exists", "a.txt"),
            WorkflowStep(
                "launch",
                "Launch",
                StepKind.LAUNCH_APPLICATION,
                "launch",
                '{"executable": "C:/work/app.exe"}',
            ),
            WorkflowStep("observe", "Observe", StepKind.REPORT, "just a note", None),
        ),
    )
    classified = classify_workflow_steps(workflow)
    by_id = {item.step_id: item for item in classified}
    assert by_id["inspect"].replayable is True
    assert by_id["launch"].replayable is True
    assert by_id["observe"].replayable is False
    assert "nothing is performed" in by_id["observe"].reason


def test_save_approved_refuses_observation_only_workflow(tmp_path) -> None:
    service = _service_with_fakes(tmp_path)
    workflow = Workflow(
        "obs-only",
        "Observation only",
        (WorkflowStep("s", "Step", StepKind.REPORT, "just a note"),),
    )
    proposal = ApprovedProposal(workflow, datetime.now(UTC))
    with pytest.raises(WorkflowValidationError, match="no steps Once can perform"):
        service.save_approved(proposal)
    assert service.list_saved() == ()


def test_save_approved_saves_replayable_workflow(tmp_path) -> None:
    service = _service_with_fakes(tmp_path)
    workflow = Workflow(
        "rel",
        "Read only",
        (
            WorkflowStep(
                "s", "Step", StepKind.VERIFY_PATH_EXISTS, "exists", str(tmp_path / "x.txt")
            ),
        ),
    )
    proposal = ApprovedProposal(workflow, datetime.now(UTC))
    path = service.save_approved(proposal)
    assert path.exists()
    assert service.list_saved() == (path,)
