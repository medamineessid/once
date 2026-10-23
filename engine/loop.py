"""Bounded diagnose-fix-test loop orchestration (pure domain logic)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from time import monotonic
from typing import Protocol
from uuid import uuid4

from engine.errors import WorkflowValidationError
from engine.verifier import EvidenceBundle

MAX_ATTEMPTS = 50
MAX_WALL_SECONDS = 3600.0

STOP_NO_PROPOSER_TEXT = (
    "Verification failed and no fix proposer is configured. "
    "Configure a reviewed coding-agent proposer to continue."
)
STOP_MAX_ATTEMPTS_TEXT = "The diagnose-fix-test loop reached its configured attempt limit."
STOP_WALL_TIME_TEXT = "The diagnose-fix-test loop reached its time limit."
STOP_NO_PROGRESS_TEXT = (
    "The same verification failures repeated, so the loop stopped instead of "
    "retrying without change."
)


class LoopStatus(StrEnum):
    """Terminal outcomes of one bounded loop run."""

    COMPLETED = "COMPLETED"
    STOPPED_MAX_ATTEMPTS = "STOPPED_MAX_ATTEMPTS"
    STOPPED_WALL_TIME = "STOPPED_WALL_TIME"
    STOPPED_NO_PROGRESS = "STOPPED_NO_PROGRESS"
    STOPPED_NO_PROPOSER = "STOPPED_NO_PROPOSER"


class DecisionCode(StrEnum):
    """One recorded loop event."""

    VERIFIED_PASS = "verified_pass"  # noqa: S105 - decision code, not a secret
    VERIFIED_FAIL = "verified_fail"
    PROPOSER_NOTIFIED = "proposer_notified"
    STOP_NO_PROPOSER = "stop_no_proposer"
    STOP_MAX_ATTEMPTS = "stop_max_attempts"
    STOP_WALL_TIME = "stop_wall_time"
    STOP_NO_PROGRESS = "stop_no_progress"


@dataclass(frozen=True)
class FixProposer(Protocol):
    """Receives redacted evidence and performs its own external fix.

    Proposers are untrusted integration boundaries. The loop never executes
    whatever a proposer returns; it only re-verifies observable outputs. No
    real coding-agent adapter is implemented yet, which is a documented gap.
    """

    def propose(self, evidence: EvidenceBundle) -> None: ...


@dataclass(frozen=True)
class LoopPolicy:
    """Mandatory bounds; unbounded loops cannot be constructed."""

    max_attempts: int
    max_wall_seconds: float

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= MAX_ATTEMPTS:
            raise WorkflowValidationError("The loop attempt limit must be between 1 and 50.")
        if not 0 < self.max_wall_seconds <= MAX_WALL_SECONDS:
            raise WorkflowValidationError("The loop time limit must be between 0 and 3600 seconds.")


@dataclass(frozen=True)
class LoopDecision:
    """One recorded loop event with its optional verification-run link."""

    attempt: int
    code: DecisionCode
    reason: str
    evidence_run_id: str | None = None


@dataclass(frozen=True)
class LoopRun:
    """Immutable outcome of one bounded loop run."""

    loop_id: str
    status: LoopStatus
    started_at: str
    finished_at: str
    decisions: tuple[LoopDecision, ...]

    @property
    def passed(self) -> bool:
        return self.status is LoopStatus.COMPLETED


class LoopController:
    """Run verification, bounded fixes, and re-verification until a stop limit."""

    def __init__(
        self,
        verify: Callable[[], EvidenceBundle],
        proposer: FixProposer | None = None,
        stopwatch: Callable[[], float] = monotonic,
    ) -> None:
        self._verify = verify
        self._proposer = proposer
        self._stopwatch = stopwatch

    def run(self, policy: LoopPolicy | None = None) -> LoopRun:
        """Execute the bounded loop and return its immutable outcome."""
        policy = policy or LoopPolicy(max_attempts=3, max_wall_seconds=600.0)
        started_clock = self._stopwatch()
        started_at = datetime.now(UTC).isoformat()
        decisions: list[LoopDecision] = []
        previous_failures: frozenset[str] | None = None
        verify_calls = 0

        while True:
            bundle = self._verify()
            verify_calls += 1
            if bundle.passed:
                decisions.append(
                    LoopDecision(
                        verify_calls, DecisionCode.VERIFIED_PASS, "All cases passed.", bundle.run_id
                    )
                )
                return self._finish(started_clock, started_at, LoopStatus.COMPLETED, decisions)
            decisions.append(
                LoopDecision(
                    verify_calls,
                    DecisionCode.VERIFIED_FAIL,
                    f"{sum(1 for case in bundle.cases if not case.passed)} case(s) failed.",
                    bundle.run_id,
                )
            )

            if verify_calls >= policy.max_attempts:
                decisions.append(
                    LoopDecision(
                        verify_calls, DecisionCode.STOP_MAX_ATTEMPTS, STOP_MAX_ATTEMPTS_TEXT
                    )
                )
                return self._finish(
                    started_clock, started_at, LoopStatus.STOPPED_MAX_ATTEMPTS, decisions
                )
            if self._stopwatch() - started_clock >= policy.max_wall_seconds:
                decisions.append(
                    LoopDecision(verify_calls, DecisionCode.STOP_WALL_TIME, STOP_WALL_TIME_TEXT)
                )
                return self._finish(
                    started_clock, started_at, LoopStatus.STOPPED_WALL_TIME, decisions
                )
            current_failures = frozenset(case.case_id for case in bundle.cases if not case.passed)
            if current_failures == previous_failures:
                decisions.append(
                    LoopDecision(verify_calls, DecisionCode.STOP_NO_PROGRESS, STOP_NO_PROGRESS_TEXT)
                )
                return self._finish(
                    started_clock, started_at, LoopStatus.STOPPED_NO_PROGRESS, decisions
                )
            if self._proposer is None:
                decisions.append(
                    LoopDecision(verify_calls, DecisionCode.STOP_NO_PROPOSER, STOP_NO_PROPOSER_TEXT)
                )
                return self._finish(
                    started_clock, started_at, LoopStatus.STOPPED_NO_PROPOSER, decisions
                )
            previous_failures = current_failures
            self._proposer.propose(bundle)
            decisions.append(
                LoopDecision(
                    verify_calls,
                    DecisionCode.PROPOSER_NOTIFIED,
                    "Redacted evidence sent to the proposer.",
                )
            )

    def _finish(
        self,
        started_clock: float,
        started_at: str,
        status: LoopStatus,
        decisions: list[LoopDecision],
    ) -> LoopRun:
        return LoopRun(
            str(uuid4()),
            status,
            started_at,
            datetime.now(UTC).isoformat(),
            tuple(decisions),
        )
