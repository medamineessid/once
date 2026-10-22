"""Tests for policy-gated read-only replay."""

from __future__ import annotations

import pytest

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
