"""Run-truth contract (docs/contracts/run-outcomes.md): a report is not a success."""

from __future__ import annotations

import sqlite3

from controller.run_events import RunEventKind, RunEventStream
from engine.workflow import (
    StepKind,
    StepStatus,
    Workflow,
    WorkflowRunner,
    WorkflowStatus,
    WorkflowStep,
)
from storage.database import connect
from storage.history import ExecutionHistory


def workflow_of(*steps: WorkflowStep, workflow_id: str = "outcome-workflow") -> Workflow:
    return Workflow(workflow_id, "Outcome workflow", steps)


def report_step(step_id: str = "report", **kwargs: object) -> WorkflowStep:
    return WorkflowStep(step_id, "Report", StepKind.REPORT, "Nothing to do yet.", **kwargs)


def test_S_report_only_run_is_observation_only() -> None:
    run = WorkflowRunner().run(workflow_of(report_step("a"), report_step("b")))

    assert run.status is WorkflowStatus.OBSERVATION_ONLY
    assert [result.status for result in run.results] == [StepStatus.OBSERVED] * 2


def test_S_empty_workflow_performs_nothing_so_is_observation_only() -> None:
    run = WorkflowRunner().run(workflow_of())

    assert run.status is WorkflowStatus.OBSERVATION_ONLY
    assert run.results == ()


def test_read_only_inspection_still_counts_as_success(tmp_path) -> None:
    target = tmp_path / "invoice.txt"
    target.write_bytes(b"invoice")
    step = WorkflowStep("check", "Check", StepKind.INSPECT_PATH, "Found", str(target))

    run = WorkflowRunner().run(workflow_of(step), allowed_root=tmp_path)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].status is StepStatus.VERIFIED


def test_a_report_after_real_work_stays_succeeded(tmp_path) -> None:
    target = tmp_path / "invoice.txt"
    target.write_bytes(b"invoice")
    step = WorkflowStep("check", "Check", StepKind.INSPECT_PATH, "Found", str(target))

    run = WorkflowRunner().run(workflow_of(step, report_step()), allowed_root=tmp_path)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert [result.status for result in run.results] == [
        StepStatus.VERIFIED,
        StepStatus.OBSERVED,
    ]


def test_observation_never_hides_a_later_failure() -> None:
    failing = WorkflowStep("boom", "Break", StepKind.FAIL, "It broke.")

    run = WorkflowRunner().run(workflow_of(report_step(), failing, report_step("after")))

    assert run.status is WorkflowStatus.FAILED
    assert [result.status for result in run.results] == [
        StepStatus.OBSERVED,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
    ]
    assert "earlier step failed" in run.results[-1].message


def test_observation_does_not_continue_after_cancellation() -> None:
    checks = iter((False, True))

    run = WorkflowRunner().run(
        workflow_of(report_step("a"), report_step("b")), cancel_check=lambda: next(checks)
    )

    assert run.status is WorkflowStatus.CANCELLED
    assert [result.status for result in run.results] == [
        StepStatus.OBSERVED,
        StepStatus.SKIPPED,
    ]


def test_a_retried_report_is_still_an_observation() -> None:
    workflow = workflow_of(report_step("a", max_attempts=2))

    run = WorkflowRunner().run(workflow)

    assert run.status is WorkflowStatus.OBSERVATION_ONLY
    assert run.results[0].status is StepStatus.OBSERVED


def test_history_round_trips_the_new_outcomes(tmp_path) -> None:
    history = ExecutionHistory(connect(tmp_path / "history.db"))
    run = WorkflowRunner().run(workflow_of(report_step()), run_id="observed-run")
    history.record(run)

    (record,) = history.list_runs()

    assert record.run.status is WorkflowStatus.OBSERVATION_ONLY
    assert record.run.results[0].status is StepStatus.OBSERVED
    history.close()


def test_history_still_loads_rows_written_before_this_contract(tmp_path) -> None:
    """An old run row (SUCCEEDED for an all-REPORT run) keeps its stored meaning."""
    connection: sqlite3.Connection = connect(tmp_path / "history.db")
    connection.execute(
        "INSERT INTO workflow_runs (run_id, workflow_id, status, started_at, finished_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            "old-run",
            "demo",
            "SUCCEEDED",
            "2026-10-01T10:00:00+00:00",
            "2026-10-01T10:00:01+00:00",
        ),
    )
    connection.execute(
        "INSERT INTO workflow_step_results"
        " (run_id, position, step_id, status, message, evidence)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        ("old-run", 0, "report", "SUCCEEDED", "Nothing to do yet.", "[]"),
    )
    connection.commit()

    history = ExecutionHistory(connection)
    (record,) = history.list_runs()

    assert record.run.status is WorkflowStatus.SUCCEEDED
    assert record.run.results[0].status is StepStatus.SUCCEEDED
    history.close()


def test_run_events_treat_an_observation_as_a_success_continuation() -> None:
    workflow = workflow_of(report_step())
    stream = RunEventStream(workflow)
    run = WorkflowRunner().run(workflow, run_id="observed-run")

    started = stream.start()
    finished = stream.observe_run(run)
    events = started + finished

    step_events = [event for event in events if event.step_id is not None]
    assert [event.kind for event in step_events] == [RunEventKind.STEP_SUCCEEDED]
    assert step_events[0].status == StepStatus.OBSERVED.value
    assert events[-1].kind is RunEventKind.RUN_FINISHED
    assert events[-1].status == WorkflowStatus.OBSERVATION_ONLY.value


def test_a_failed_run_does_not_report_observation_only() -> None:
    """Guard: OBSERVED must not be reachable through a failure path."""
    run = WorkflowRunner().run(workflow_of(WorkflowStep("boom", "Break", StepKind.FAIL, "No.")))

    assert run.status is WorkflowStatus.FAILED
    assert StepStatus.OBSERVED not in {result.status for result in run.results}
