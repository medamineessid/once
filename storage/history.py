"""SQLite persistence for completed workflow runs."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from engine.agent_change import ChangeReview
from engine.errors import AgentIntegrationError
from engine.loop import DecisionCode, LoopDecision, LoopRun, LoopStatus
from engine.verifier import CaseResult, EvidenceBundle, FieldResult
from engine.workflow import StepResult, StepStatus, WorkflowRun, WorkflowStatus


@dataclass(frozen=True)
class HistoryRecord:
    """A persisted run and its step outcomes."""

    run: WorkflowRun


@dataclass(frozen=True)
class AgentProposalRecord:
    """A persisted agent proposal and its review decision."""

    review: ChangeReview
    status: str
    decided_at: str | None


@dataclass(frozen=True)
class ProposalVerificationRecord:
    """One pre-merge or post-merge verification bound to a proposal commit."""

    proposal_id: str
    agent_tip: str
    phase: str
    verification_run_id: str
    passed: bool
    cancelled: bool
    checked_at: str


@dataclass(frozen=True)
class WorktreeRecord:
    """One disposable verification worktree and its cleanup state."""

    proposal_id: str
    agent_tip: str
    path: str
    status: str  # ACTIVE, CLOSED, LEFTOVER, REFUSED
    created_at: str
    closed_at: str | None


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
                    (run_id, started_at, finished_at, passed, redaction_applied, cancelled)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle.run_id,
                    bundle.started_at,
                    bundle.finished_at,
                    int(bundle.passed),
                    int(bundle.redaction_applied),
                    int(bundle.cancelled),
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
                SELECT run_id, started_at, finished_at, redaction_applied, cancelled
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
                        cancelled=bool(row["cancelled"]),
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

    def record_agent_proposal(self, review: ChangeReview, created_at: str) -> None:
        """Atomically insert one agent proposal in PENDING state."""
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO agent_proposals
                    (proposal_id, created_at, repo_path, base_branch, agent_branch,
                     base_commit, agent_tip, diff, changed_files, untracked_files, truncated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.proposal_id,
                    created_at,
                    review.repo_path,
                    review.base_branch,
                    review.agent_branch,
                    review.base_commit,
                    review.agent_tip,
                    review.diff,
                    json.dumps(list(review.changed_files)),
                    json.dumps(list(review.untracked_files)),
                    int(review.truncated),
                ),
            )

    def record_agent_decision(self, proposal_id: str, decision: str, decided_at: str) -> None:
        """Record exactly one approval or rejection per proposal."""
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    """
                    INSERT INTO agent_decisions (proposal_id, decision, decided_at)
                    VALUES (?, ?, ?)
                    """,
                    (proposal_id, decision, decided_at),
                )
        except sqlite3.IntegrityError as error:
            raise AgentIntegrationError(
                "This proposal has already been approved or rejected."
            ) from error

    def proposal_record(self, proposal_id: str) -> AgentProposalRecord | None:
        """Return the exact recorded proposal and its decision, if any."""
        with self._lock:
            row = self._connection.execute(
                """
                    SELECT proposal_id, created_at, repo_path, base_branch, agent_branch,
                           base_commit, agent_tip, diff, changed_files, untracked_files, truncated
                    FROM agent_proposals
                    WHERE proposal_id = ?
                    """,
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return self._proposal_record_from_row(row)

    def proposal_status(self, proposal_id: str) -> str | None:
        """Return PENDING, APPROVED, or REJECTED for one proposal."""
        with self._lock:
            exists = self._connection.execute(
                "SELECT 1 FROM agent_proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
            if exists is None:
                return None
        with self._lock:
            decisions = self._connection.execute(
                """
                SELECT decision FROM agent_decisions WHERE proposal_id = ?
                ORDER BY decided_at
                """,
                (proposal_id,),
            ).fetchall()
        if not decisions:
            return "PENDING"
        return decisions[0]["decision"]

    def list_agent_proposals(self) -> tuple[AgentProposalRecord, ...]:
        """Return persisted agent proposals newest first with decisions."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT proposal_id, created_at, repo_path, base_branch, agent_branch,
                       base_commit, agent_tip, diff, changed_files, untracked_files, truncated
                FROM agent_proposals
                ORDER BY created_at DESC, proposal_id DESC
                """
            ).fetchall()
        records: list[AgentProposalRecord] = []
        with self._lock:
            for row in rows:
                decision_row = self._connection.execute(
                    """
                        SELECT decision, decided_at FROM agent_decisions WHERE proposal_id = ?
                        ORDER BY decided_at
                        """,
                    (row["proposal_id"],),
                ).fetchone()
                records.append(self._proposal_record_from_row(row, decision_row))
        return tuple(records)

    @staticmethod
    def _proposal_record_from_row(
        row: sqlite3.Row, decision_row: sqlite3.Row | None = None
    ) -> AgentProposalRecord:
        """Rebuild one immutable proposal record from its persisted rows."""
        if decision_row is None:
            status, decided_at = "PENDING", None
        else:
            status, decided_at = decision_row["decision"], decision_row["decided_at"]
        return AgentProposalRecord(
            review=ChangeReview(
                proposal_id=row["proposal_id"],
                repo_path=row["repo_path"],
                base_branch=row["base_branch"],
                agent_branch=row["agent_branch"],
                base_commit=row["base_commit"],
                agent_tip=row["agent_tip"],
                diff=row["diff"],
                changed_files=tuple(json.loads(row["changed_files"])),
                untracked_files=tuple(json.loads(row["untracked_files"])),
                truncated=bool(row["truncated"]),
            ),
            status=status,
            decided_at=decided_at,
        )

    def record_proposal_verification(self, record: ProposalVerificationRecord) -> None:
        """Persist one pre-merge or post-merge verification of a proposal."""
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO proposal_verifications
                    (proposal_id, agent_tip, phase, verification_run_id,
                     passed, cancelled, checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.proposal_id,
                    record.agent_tip,
                    record.phase,
                    record.verification_run_id,
                    int(record.passed),
                    int(record.cancelled),
                    record.checked_at,
                ),
            )

    def list_proposal_verifications(
        self, proposal_id: str | None = None
    ) -> tuple[ProposalVerificationRecord, ...]:
        """Return persisted proposal verifications, newest first."""
        with self._lock:
            if proposal_id is None:
                rows = self._connection.execute(
                    """
                    SELECT proposal_id, agent_tip, phase, verification_run_id,
                           passed, cancelled, checked_at
                    FROM proposal_verifications
                    ORDER BY checked_at DESC, verification_run_id DESC
                    """
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT proposal_id, agent_tip, phase, verification_run_id,
                           passed, cancelled, checked_at
                    FROM proposal_verifications
                    WHERE proposal_id = ?
                    ORDER BY checked_at DESC, verification_run_id DESC
                    """,
                    (proposal_id,),
                ).fetchall()
        return tuple(
            ProposalVerificationRecord(
                proposal_id=row["proposal_id"],
                agent_tip=row["agent_tip"],
                phase=row["phase"],
                verification_run_id=row["verification_run_id"],
                passed=bool(row["passed"]),
                cancelled=bool(row["cancelled"]),
                checked_at=row["checked_at"],
            )
            for row in rows
        )

    def record_worktree(self, record: WorktreeRecord) -> None:
        """Persist one worktree lifecycle event for cleanup-state tracking."""
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO worktree_checkouts
                    (proposal_id, agent_tip, path, status, created_at, closed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.proposal_id,
                    record.agent_tip,
                    record.path,
                    record.status,
                    record.created_at,
                    record.closed_at,
                ),
            )

    def list_worktree_records(self) -> tuple[WorktreeRecord, ...]:
        """Return persisted worktree lifecycle records, newest first."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT proposal_id, agent_tip, path, status, created_at, closed_at
                FROM worktree_checkouts
                ORDER BY created_at DESC, path DESC
                """
            ).fetchall()
        return tuple(
            WorktreeRecord(
                proposal_id=row["proposal_id"],
                agent_tip=row["agent_tip"],
                path=row["path"],
                status=row["status"],
                created_at=row["created_at"],
                closed_at=row["closed_at"],
            )
            for row in rows
        )

    def stale_worktrees(self) -> tuple[WorktreeRecord, ...]:
        """Return worktrees whose latest lifecycle state is not cleanly closed."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT w.proposal_id, w.agent_tip, w.path, w.status, w.created_at, w.closed_at
                FROM worktree_checkouts w
                WHERE w.status != 'CLOSED'
                  AND w.created_at = (
                      SELECT MAX(w2.created_at)
                      FROM worktree_checkouts w2
                      WHERE w2.path = w.path
                  )
                ORDER BY w.created_at DESC, w.path DESC
                """
            ).fetchall()
        return tuple(
            WorktreeRecord(
                proposal_id=row["proposal_id"],
                agent_tip=row["agent_tip"],
                path=row["path"],
                status=row["status"],
                created_at=row["created_at"],
                closed_at=row["closed_at"],
            )
            for row in rows
        )

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
