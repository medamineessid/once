"""SQLite persistence for completed workflow runs."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from engine.workflow import StepResult, StepStatus, WorkflowRun, WorkflowStatus


@dataclass(frozen=True)
class HistoryRecord:
    """A persisted run and its step outcomes."""

    run: WorkflowRun


class ExecutionHistory:
    """Store and retrieve immutable workflow run snapshots."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._lock = RLock()

    def close(self) -> None:
        """Close the history database connection owned by this repository."""
        with self._lock:
            self._connection.close()

    def record(self, run: WorkflowRun) -> None:
        """Atomically insert one run and all of its step results."""
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    """
                    INSERT INTO workflow_runs
                        (run_id, workflow_id, status, started_at, finished_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        run.run_id,
                        run.workflow_id,
                        run.status.value,
                        run.started_at.isoformat(),
                        run.finished_at.isoformat(),
                    ),
                )
                self._connection.executemany(
                    """
                    INSERT INTO workflow_step_results
                        (run_id, position, step_id, status, message, evidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            run.run_id,
                            position,
                            result.step_id,
                            result.status.value,
                            result.message,
                            json.dumps(result.evidence),
                        )
                        for position, result in enumerate(run.results)
                    ],
                )
        except sqlite3.IntegrityError:
            raise

    def list_runs(self) -> tuple[HistoryRecord, ...]:
        """Return persisted runs newest first with their step results."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT run_id, workflow_id, status, started_at, finished_at
                FROM workflow_runs
                ORDER BY started_at DESC, run_id DESC
                """
            ).fetchall()
        records: list[HistoryRecord] = []
        with self._lock:
            for row in rows:
                step_rows = self._connection.execute(
                    """
                    SELECT step_id, status, message, evidence
                    FROM workflow_step_results
                    WHERE run_id = ?
                    ORDER BY position
                    """,
                    (row["run_id"],),
                ).fetchall()
                run = WorkflowRun(
                    run_id=row["run_id"],
                    workflow_id=row["workflow_id"],
                    status=WorkflowStatus(row["status"]),
                    results=tuple(
                        StepResult(
                            step_id=step_row["step_id"],
                            status=StepStatus(step_row["status"]),
                            message=step_row["message"],
                            evidence=tuple(json.loads(step_row["evidence"])),
                        )
                        for step_row in step_rows
                    ),
                    started_at=datetime.fromisoformat(row["started_at"]),
                    finished_at=datetime.fromisoformat(row["finished_at"]),
                )
                records.append(HistoryRecord(run=run))
        return tuple(records)
