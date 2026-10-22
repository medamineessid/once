"""Tests for the deterministic workflow orchestration foundation."""

from __future__ import annotations

from engine.workflow import (
    StepKind,
    StepStatus,
    Workflow,
    WorkflowRunner,
    WorkflowStatus,
    WorkflowStep,
)


def make_workflow(*kinds: StepKind) -> Workflow:
    return Workflow(
        workflow_id="test-workflow",
        name="Test workflow",
        steps=tuple(
            WorkflowStep(
                step_id=f"step-{index}",
                name=f"Step {index}",
                kind=kind,
                message=f"Message {index}",
            )
            for index, kind in enumerate(kinds)
        ),
    )


def test_workflow_runner_records_successful_steps() -> None:
    run = WorkflowRunner().run(make_workflow(StepKind.REPORT, StepKind.REPORT), run_id="run-1")

    assert run.run_id == "run-1"
    assert run.status is WorkflowStatus.SUCCEEDED
    assert [result.status for result in run.results] == [
        StepStatus.SUCCEEDED,
        StepStatus.SUCCEEDED,
    ]


def test_workflow_runner_stops_after_controlled_failure() -> None:
    run = WorkflowRunner().run(
        make_workflow(StepKind.REPORT, StepKind.FAIL, StepKind.REPORT),
        run_id="run-2",
    )

    assert run.status is WorkflowStatus.FAILED
    assert [result.status for result in run.results] == [
        StepStatus.SUCCEEDED,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
    ]
    assert "earlier step failed" in run.results[-1].message


def test_workflow_runner_cancels_before_remaining_steps() -> None:
    checks = iter((False, True))
    run = WorkflowRunner().run(
        make_workflow(StepKind.REPORT, StepKind.REPORT),
        cancel_check=lambda: next(checks),
        run_id="run-3",
    )

    assert run.status is WorkflowStatus.CANCELLED
    assert [result.status for result in run.results] == [
        StepStatus.SUCCEEDED,
        StepStatus.SKIPPED,
    ]


def test_workflow_runner_terminates_empty_workflow() -> None:
    run = WorkflowRunner().run(make_workflow(), run_id="run-4")

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results == ()


def test_workflow_runner_verifies_file_within_authorized_root(tmp_path) -> None:
    target = tmp_path / "invoice.txt"
    target.write_bytes(b"invoice")
    workflow = Workflow(
        "inspect",
        "Inspect",
        (WorkflowStep("check", "Check file", StepKind.INSPECT_PATH, "File found", str(target)),),
    )

    run = WorkflowRunner().run(workflow, allowed_root=tmp_path)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].status is StepStatus.VERIFIED
    assert "size=7" in run.results[0].evidence


def test_workflow_runner_rejects_path_outside_authorized_root(tmp_path) -> None:
    target = tmp_path / "invoice.txt"
    target.write_bytes(b"invoice")
    workflow = Workflow(
        "inspect",
        "Inspect",
        (WorkflowStep("check", "Check file", StepKind.INSPECT_PATH, "File found", str(target)),),
    )

    run = WorkflowRunner().run(workflow, allowed_root=tmp_path / "other")

    assert run.status is WorkflowStatus.FAILED
    assert "authorized folder" in run.results[0].message
