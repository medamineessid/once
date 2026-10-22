"""Tests for the deterministic workflow orchestration foundation."""

from __future__ import annotations

import pytest

from engine.workflow import (
    PostconditionKind,
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


def test_workflow_runner_reports_progress_for_completed_steps() -> None:
    progress = []

    WorkflowRunner().run(
        make_workflow(StepKind.REPORT, StepKind.REPORT),
        progress_callback=progress.append,
    )

    assert [result.step_id for result in progress] == ["step-0", "step-1"]
    assert all(result.status is StepStatus.SUCCEEDED for result in progress)


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


def test_workflow_runner_rejects_symlink_target(tmp_path) -> None:
    target = tmp_path / "real.txt"
    target.write_bytes(b"real")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are not available on this machine")
    workflow = Workflow(
        "inspect",
        "Inspect",
        (WorkflowStep("check", "Check file", StepKind.INSPECT_PATH, "Found", str(link)),),
    )

    run = WorkflowRunner().run(workflow, allowed_root=tmp_path)

    assert run.status is WorkflowStatus.FAILED
    assert "symbolic link" in run.results[0].message


def test_workflow_runner_retries_and_records_attempt_evidence() -> None:
    class EventuallySuccessfulRunner(WorkflowRunner):
        def __init__(self) -> None:
            self.calls = 0

        def _run_once(self, step, allowed_root):
            self.calls += 1
            if self.calls < 2:
                return super()._run_once(
                    WorkflowStep(step.step_id, step.name, StepKind.FAIL, "temporary"), allowed_root
                )
            return super()._run_once(step, allowed_root)

    workflow = Workflow(
        "retry",
        "Retry",
        (WorkflowStep("step", "Retrying", StepKind.REPORT, "done", max_attempts=2),),
    )

    run = EventuallySuccessfulRunner().run(workflow)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].message.endswith("(attempt 2)")


def test_workflow_runner_fails_after_exhausting_retries() -> None:
    workflow = Workflow(
        "retry",
        "Retry",
        (WorkflowStep("step", "Always fails", StepKind.FAIL, "broken", max_attempts=2),),
    )

    run = WorkflowRunner().run(workflow)

    assert run.status is WorkflowStatus.FAILED
    assert "after 2 attempt(s)" in run.results[0].message
    assert any("attempt 1" in evidence for evidence in run.results[0].evidence)


def test_workflow_runner_checks_path_postcondition(tmp_path) -> None:
    target = tmp_path / "result.txt"
    target.write_bytes(b"result")
    workflow = Workflow(
        "postcondition",
        "Postcondition",
        (
            WorkflowStep(
                "step",
                "Check result",
                StepKind.REPORT,
                "Created",
                target=str(target),
                postcondition=PostconditionKind.PATH_EXISTS,
            ),
        ),
    )

    run = WorkflowRunner().run(workflow, allowed_root=tmp_path)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].status is StepStatus.SUCCEEDED
    assert "size=6" in run.results[0].evidence


def test_workflow_runner_cancels_between_retry_attempts() -> None:
    checks = iter((False, True))
    workflow = Workflow(
        "retry-cancel",
        "Retry cancellation",
        (WorkflowStep("step", "Fail", StepKind.FAIL, "broken", max_attempts=3),),
    )

    run = WorkflowRunner().run(workflow, cancel_check=lambda: next(checks))

    assert run.status is WorkflowStatus.CANCELLED
    assert run.results[0].status is StepStatus.SKIPPED
