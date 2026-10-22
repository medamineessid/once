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
