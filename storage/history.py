"""SQLite persistence for completed workflow runs."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from engine.loop import DecisionCode, LoopDecision, LoopRun, LoopStatus
from engine.verifier import CaseResult, EvidenceBundle, FieldResult
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

    def record_verification(self, bundle: EvidenceBundle) -> None:
        """Atomically insert one verification run and its case results."""
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO acceptance_runs
                    (run_id, started_at, finished_at, passed, redaction_applied)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    bundle.run_id,
                    bundle.started_at,
                    bundle.finished_at,
                    int(bundle.passed),
                    int(bundle.redaction_applied),
                ),
            )
            self._connection.executemany(
                """
                INSERT INTO acceptance_case_results
                    (run_id, position, case_id, passed, exit_code, timed_out,
                     stdout_tail, stderr_tail, fields)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        bundle.run_id,
                        position,
                        case.case_id,
                        int(case.passed),
                        case.exit_code,
                        int(case.timed_out),
                        case.stdout_tail,
                        case.stderr_tail,
                        json.dumps(
                            [
                                {
                                    "field": field.field,
                                    "passed": field.passed,
                                    "status": field.status,
                                    "expected": field.expected,
                                    "actual": field.actual,
                                }
                                for field in case.fields
                            ]
                        ),
                    )
                    for position, case in enumerate(bundle.cases)
                ],
            )

    def list_verification_runs(self) -> tuple[EvidenceBundle, ...]:
        """Return persisted verification runs newest first."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT run_id, started_at, finished_at, redaction_applied
                FROM acceptance_runs
                ORDER BY started_at DESC, run_id DESC
                """
            ).fetchall()
        bundles: list[EvidenceBundle] = []
        with self._lock:
            for row in rows:
                case_rows = self._connection.execute(
                    """
                    SELECT case_id, passed, exit_code, timed_out,
                           stdout_tail, stderr_tail, fields
                    FROM acceptance_case_results
                    WHERE run_id = ?
                    ORDER BY position
                    """,
                    (row["run_id"],),
                ).fetchall()
                bundles.append(
                    EvidenceBundle(
                        run_id=row["run_id"],
                        started_at=row["started_at"],
                        finished_at=row["finished_at"],
                        cases=tuple(
                            CaseResult(
                                case_id=case_row["case_id"],
                                passed=bool(case_row["passed"]),
                                fields=tuple(
                                    FieldResult(
                                        field=field_row["field"],
                                        passed=bool(field_row["passed"]),
                                        status=field_row["status"],
                                        expected=field_row["expected"],
                                        actual=field_row["actual"],
                                    )
                                    for field_row in json.loads(case_row["fields"])
                                ),
                                exit_code=case_row["exit_code"],
                                timed_out=bool(case_row["timed_out"]),
                                stdout_tail=case_row["stdout_tail"],
                                stderr_tail=case_row["stderr_tail"],
                            )
                            for case_row in case_rows
                        ),
                        redaction_applied=bool(row["redaction_applied"]),
                    )
                )
        return tuple(bundles)

    def record_loop(self, run: LoopRun) -> None:
        """Atomically insert one loop run and its decisions."""
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO loop_runs (loop_id, status, started_at, finished_at)
                VALUES (?, ?, ?, ?)
                """,
                (run.loop_id, run.status.value, run.started_at, run.finished_at),
            )
            self._connection.executemany(
                """
                INSERT INTO loop_decisions
                    (loop_id, position, attempt, code, reason, evidence_run_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run.loop_id,
                        position,
                        decision.attempt,
                        decision.code.value,
                        decision.reason,
                        decision.evidence_run_id,
                    )
                    for position, decision in enumerate(run.decisions)
                ],
            )

    def list_loops(self) -> tuple[LoopRun, ...]:
        """Return persisted loop runs newest first."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT loop_id, status, started_at, finished_at
                FROM loop_runs
                ORDER BY started_at DESC, loop_id DESC
                """
            ).fetchall()
        runs: list[LoopRun] = []
        with self._lock:
            for row in rows:
                decision_rows = self._connection.execute(
                    """
                    SELECT attempt, code, reason, evidence_run_id
                    FROM loop_decisions
                    WHERE loop_id = ?
                    ORDER BY position
                    """,
                    (row["loop_id"],),
                ).fetchall()
                runs.append(
                    LoopRun(
                        loop_id=row["loop_id"],
                        status=LoopStatus(row["status"]),
                        started_at=row["started_at"],
                        finished_at=row["finished_at"],
                        decisions=tuple(
                            LoopDecision(
                                attempt=decision_row["attempt"],
                                code=DecisionCode(decision_row["code"]),
                                reason=decision_row["reason"],
                                evidence_run_id=decision_row["evidence_run_id"],
                            )
                            for decision_row in decision_rows
                        ),
                    )
                )
        return tuple(runs)

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
