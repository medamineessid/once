"""Tests for SQLite execution history and controller integration."""

from __future__ import annotations

from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from storage.database import connect
from storage.history import ExecutionHistory


def test_history_round_trips_run_and_step_results(tmp_path) -> None:
    connection = connect(tmp_path / "history.db")
    history = ExecutionHistory(connection)
    workflow = Workflow(
        "history-workflow",
        "History workflow",
        (WorkflowStep("step-1", "Report", StepKind.REPORT, "Recorded"),),
    )

    run = WorkflowService(history=history).run_workflow(workflow)
    records = history.list_runs()

    assert len(records) == 1
    assert records[0].run.run_id == run.run_id
    assert records[0].run.status == run.status
    assert records[0].run.results == run.results
    assert records[0].run.started_at <= records[0].run.finished_at
    connection.close()


def test_history_persists_step_evidence(tmp_path) -> None:
    connection = connect(tmp_path / "history.db")
    history = ExecutionHistory(connection)
    target = tmp_path / "evidence.txt"
    target.write_bytes(b"evidence")
    workflow = Workflow(
        "evidence-workflow",
        "Evidence workflow",
        (
            WorkflowStep(
                "inspect",
                "Inspect",
                StepKind.INSPECT_PATH,
                "Verified",
                str(target),
            ),
        ),
    )

    run = WorkflowService(history=history).run_workflow(workflow, allowed_root=tmp_path)

    assert history.list_runs()[0].run.results[0].evidence == (
        f"path={target.resolve()}",
        "size=8",
    )
    assert run.status.value == "SUCCEEDED"
    connection.close()


def test_history_persists_failures_and_skipped_steps(tmp_path) -> None:
    connection = connect(tmp_path / "history.db")
    history = ExecutionHistory(connection)
    workflow = Workflow(
        "failure-workflow",
        "Failure workflow",
        (
            WorkflowStep("fail", "Fail", StepKind.FAIL, "Controlled failure"),
            WorkflowStep("after", "After", StepKind.REPORT, "Not run"),
        ),
    )

    run = WorkflowService(history=history).run_workflow(workflow)

    assert run.status.value == "FAILED"
    assert [result.status.value for result in history.list_runs()[0].run.results] == [
        "FAILED",
        "SKIPPED",
    ]
    connection.close()
