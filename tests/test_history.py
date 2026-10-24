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


def test_preMigration_database_opens_after_an_update(tmp_path) -> None:
    """An older-cycle database (before additive columns) must open and keep rows."""
    import sqlite3

    database_path = tmp_path / "history.db"
    legacy = sqlite3.connect(database_path)
    legacy.executescript(
        """
        CREATE TABLE workflow_runs (
            run_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL
        );
        CREATE TABLE workflow_step_results (
            run_id TEXT NOT NULL REFERENCES workflow_runs(run_id),
            position INTEGER NOT NULL,
            step_id TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            PRIMARY KEY (run_id, position)
        );
        CREATE TABLE acceptance_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            passed INTEGER NOT NULL,
            redaction_applied INTEGER NOT NULL
        );
        """
    )
    legacy.execute(
        "INSERT INTO workflow_runs VALUES ('old-run', 'wf', 'SUCCEEDED',"
        " '2026-01-01T10:00:00', '2026-01-01T10:01:00')"
    )
    legacy.execute(
        "INSERT INTO workflow_step_results VALUES ('old-run', 0, 'step-1', 'SUCCEEDED', 'fine')"
    )
    legacy.execute(
        "INSERT INTO acceptance_runs VALUES ('ver-run',"
        " '2026-01-01T10:02:00', '2026-01-01T10:03:00', 1, 1)"
    )
    legacy.commit()
    legacy.close()

    connection = connect(database_path)
    history = ExecutionHistory(connection)
    runs = history.list_runs()
    assert [record.run.run_id for record in runs] == ["old-run"]
    assert runs[0].run.results[0].evidence == ()  # additive default, not data loss
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(acceptance_runs)")}
    assert "cancelled" in columns
    connection.close()
