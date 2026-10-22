"""Tests for policy-gated read-only replay."""

from __future__ import annotations

import pytest

from controller.service import WorkflowService
from engine.errors import ExecutionError
from engine.replay import ReplayExecutor
from engine.workflow import (
    StepKind,
    StepStatus,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)


def test_replay_dry_run_does_not_read_or_modify_target(tmp_path) -> None:
    target = tmp_path / "result.txt"
    workflow = Workflow(
        "verify",
        "Verify",
        (WorkflowStep("check", "Check", StepKind.VERIFY_PATH_EXISTS, "Check", str(target)),),
    )

    run = ReplayExecutor().execute(workflow, allowed_root=tmp_path, dry_run=True)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].status is StepStatus.SUCCEEDED
    assert "Dry run" in run.results[0].message
    assert not target.exists()


def test_replay_executes_read_only_path_verification(tmp_path) -> None:
    target = tmp_path / "result.txt"
    target.write_bytes(b"result")
    workflow = Workflow(
        "verify",
        "Verify",
        (WorkflowStep("check", "Check", StepKind.VERIFY_PATH_EXISTS, "Check", str(target)),),
    )

    run = ReplayExecutor().execute(workflow, allowed_root=tmp_path)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].status is StepStatus.VERIFIED


def test_replay_rejects_unallowlisted_actions() -> None:
    workflow = Workflow(
        "report",
        "Report",
        (WorkflowStep("report", "Report", StepKind.REPORT, "Not replayable"),),
    )

    with pytest.raises(ExecutionError, match="does not allow"):
        ReplayExecutor().validate(workflow)


def test_replay_preview_marks_unsupported_steps_without_executing() -> None:
    workflow = Workflow(
        "mixed",
        "Mixed",
        (
            WorkflowStep("check", "Check", StepKind.VERIFY_PATH_EXISTS, "Check", "C:\\missing"),
            WorkflowStep("report", "Report", StepKind.REPORT, "Unsupported"),
        ),
    )

    preview = ReplayExecutor().preview(workflow)

    assert preview.executable is False
    assert "permission=ALLOWED" in preview.steps[0]
    assert "permission=UNSUPPORTED" in preview.steps[1]


def test_replay_policy_rejects_unsupported_execution() -> None:
    workflow = Workflow(
        "report",
        "Report",
        (WorkflowStep("report", "Report", StepKind.REPORT, "Unsupported"),),
    )

    with pytest.raises(ExecutionError, match="does not allow"):
        ReplayExecutor().execute(workflow, allowed_root=None)


def test_controller_replay_persists_progress_and_cancellation(tmp_path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    workflow = Workflow(
        "cancelled-replay",
        "Cancelled replay",
        (
            WorkflowStep("first", "First", StepKind.VERIFY_PATH_EXISTS, "First", str(first)),
            WorkflowStep("second", "Second", StepKind.VERIFY_PATH_EXISTS, "Second", str(second)),
        ),
    )
    service = WorkflowService.for_app_data(tmp_path / "app-data")
    checks = iter((False, True))
    progress = []

    run = service.run_replay(
        workflow,
        allowed_root=tmp_path,
        cancel_check=lambda: next(checks),
        progress_callback=progress.append,
    )

    assert run.status is WorkflowStatus.CANCELLED
    assert [result.step_id for result in progress] == ["first"]
    assert service.history()[0].status is WorkflowStatus.CANCELLED
    service.close()
