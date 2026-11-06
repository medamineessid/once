"""Typed run events, produced only from real engine execution results.

The engine reports exactly one ``StepResult`` per step that actually ran
(``WorkflowRunner.run`` -> ``progress_callback``) and one ``WorkflowRun``
containing every result, including remaining steps it marked SKIPPED after a
failure or a cancellation (engine/workflow.py:832-869). This module converts
that real, sequential stream into typed events for the UI.

Honesty rules (see docs/contracts/run_events.md):

- Events never invent state. A ``STEP_STARTED`` event is derived, at
  completion time, from the SAME real result that produced the final event:
  the strictly sequential runner means a result proves the step ran.
- Retried steps appear once, as their real final result carries "(attempt
  N)" in the message and the recorded attempts in the evidence.
- Skipped steps appear exactly once, either live (a retry that was
  cancelled) or reconciled from the real run results; the engine's two
  canonical skip phrases decide whether the user sees "skipped" or
  "cancelled".
- After the run finishes, the stream is closed and never produces anything.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from engine.workflow import StepResult, StepStatus, Workflow, WorkflowStatus

logger = logging.getLogger(__name__)


class RunEventKind(StrEnum):
    """The complete set of run events; the contract forbids other kinds."""

    RUN_STARTED = "RUN_STARTED"
    STEP_STARTED = "STEP_STARTED"
    STEP_SUCCEEDED = "STEP_SUCCEEDED"
    STEP_FAILED = "STEP_FAILED"
    STEP_SKIPPED = "STEP_SKIPPED"
    STEP_CANCELLED = "STEP_CANCELLED"
    RUN_FINISHED = "RUN_FINISHED"


#: The engine writes exactly these two skip phrases (engine/workflow.py).
_CANCELLED_SKIP_PHRASE = "cancelled"

_SUCCESS_STATUSES = frozenset({StepStatus.SUCCEEDED, StepStatus.VERIFIED, StepStatus.OBSERVED})
_FAILURE_STATUSES = frozenset({StepStatus.FAILED, StepStatus.INCONCLUSIVE})


@dataclass(frozen=True)
class RunEvent:
    """One immutable timeline event for a workflow run."""

    kind: RunEventKind
    run_id: str
    sequence: int
    workflow_id: str
    created_at: datetime
    message: str = ""
    step_id: str | None = None
    step_name: str | None = None
    status: str | None = None
    evidence: tuple[str, ...] = ()
    engine_run_id: str | None = None


class RunEventSource(Protocol):
    """What the UI consumes; real streams and test fakes both fit."""

    def start(self) -> tuple[RunEvent, ...]: ...

    def observe_step(self, step_result: StepResult) -> tuple[RunEvent, ...]: ...

    def observe_run(self, workflow_run: object) -> tuple[RunEvent, ...]: ...

    def observe_failure(self, message: str) -> tuple[RunEvent, ...]: ...

    @property
    def finished(self) -> bool: ...


class RunEventStream:
    """Turn one real engine run into a closed, ordered event sequence.

    Thread safety: every method takes a lock because callbacks arrive on a
    worker thread while the UI thread may query the stream; events are
    immutable, so sharing is safe.
    """

    def __init__(self, workflow: Workflow) -> None:
        self._workflow = workflow
        self._run_id = uuid4().hex
        self._sequence = 0
        self._finished = False
        self._observed_step_ids: set[str] = set()
        self._lock = threading.Lock()

    @property
    def finished(self) -> bool:
        with self._lock:
            return self._finished

    def start(self) -> tuple[RunEvent, ...]:
        """Emit the RUN_STARTED event exactly once."""
        with self._lock:
            if self._finished:
                return ()
            event = self._emit_locked(
                RunEventKind.RUN_STARTED,
                message="The run started.",
            )
            return (event,)

    def observe_step(self, step_result: StepResult) -> tuple[RunEvent, ...]:
        """Convert one real engine step result into its ordered events."""
        step_id = getattr(step_result, "step_id", None)
        if step_id is None or self.finished:
            return ()
        with self._lock:
            if self._finished or step_id in self._observed_step_ids:
                return ()
            self._observed_step_ids.add(step_id)
            events: list[RunEvent] = [self._emit_locked(RunEventKind.STEP_STARTED, step_id=step_id)]
            events.append(
                self._emit_locked(
                    self._step_kind(step_result),
                    step_id=step_id,
                    message=getattr(step_result, "message", ""),
                    status=getattr(getattr(step_result, "status", None), "value", None),
                    evidence=tuple(getattr(step_result, "evidence", ()) or ()),
                )
            )
            return tuple(events)

    def observe_run(self, workflow_run: object) -> tuple[RunEvent, ...]:
        """Reconcile the real final run and emit RUN_FINISHED exactly once."""
        if self.finished:
            return ()
        with self._lock:
            if self._finished:
                return ()
            events: list[RunEvent] = []
            results = getattr(workflow_run, "results", ()) or ()
            for result in results:
                step_id = getattr(result, "step_id", None)
                if step_id is None or step_id in self._observed_step_ids:
                    continue
                self._observed_step_ids.add(step_id)
                events.append(
                    self._emit_locked(
                        self._step_kind(result),
                        step_id=step_id,
                        message=getattr(result, "message", ""),
                        status=getattr(getattr(result, "status", None), "value", None),
                        evidence=tuple(getattr(result, "evidence", ()) or ()),
                    )
                )
            status_value = getattr(getattr(workflow_run, "status", None), "value", None)
            engine_run_id = getattr(workflow_run, "run_id", None)
            events.append(
                self._emit_locked(
                    RunEventKind.RUN_FINISHED,
                    message="The run finished.",
                    status=status_value,
                    engine_run_id=str(engine_run_id) if engine_run_id else None,
                )
            )
            self._finished = True
            return tuple(events)

    def observe_failure(self, message: str) -> tuple[RunEvent, ...]:
        """The run call itself failed; report a real FAILED finish, then close."""
        if self.finished:
            return ()
        with self._lock:
            if self._finished:
                return ()
            event = self._emit_locked(
                RunEventKind.RUN_FINISHED,
                message=str(message),
                status=WorkflowStatus.FAILED.value,
                evidence=(str(message),),
            )
            self._finished = True
            return (event,)

    def _step_kind(self, result: object) -> RunEventKind:
        status = getattr(result, "status", None)
        if status in _SUCCESS_STATUSES:
            return RunEventKind.STEP_SUCCEEDED
        if status in _FAILURE_STATUSES:
            return RunEventKind.STEP_FAILED
        if status is StepStatus.SKIPPED:
            message = str(getattr(result, "message", ""))
            if _CANCELLED_SKIP_PHRASE in message.lower():
                return RunEventKind.STEP_CANCELLED
            return RunEventKind.STEP_SKIPPED
        logger.warning("Unexpected step status %s; recording it as a failure event.", status)
        return RunEventKind.STEP_FAILED

    def _emit_locked(
        self,
        kind: RunEventKind,
        *,
        step_id: str | None = None,
        message: str = "",
        status: str | None = None,
        engine_run_id: str | None = None,
        evidence: tuple[str, ...] = (),
    ) -> RunEvent:
        self._sequence += 1
        step_name: str | None = None
        if step_id is not None:
            for step in self._workflow.steps:
                if step.step_id == step_id:
                    step_name = step.name
                    break
        return RunEvent(
            kind=kind,
            run_id=self._run_id,
            sequence=self._sequence,
            workflow_id=self._workflow.workflow_id,
            created_at=datetime.now(UTC),
            message=message,
            step_id=step_id,
            step_name=step_name,
            status=status,
            evidence=evidence,
            engine_run_id=engine_run_id,
        )


class FakeRunEventSource:
    """Deterministic event source for tests and UI previews only.

    It hands out one scripted batch per call, in the order the caller would
    see from a real stream, then stays closed. The product never uses it.
    """

    def __init__(self, workflow: Workflow, batches: dict[str, tuple[RunEvent, ...]]) -> None:
        self._workflow = workflow
        self._batches = dict(batches)
        self._consumed: list[str] = []
        self._run_id = f"fake-{uuid4().hex[:12]}"

    @property
    def finished(self) -> bool:
        return all(name in self._consumed for name in ("start", "run"))

    def _next(self, name: str) -> tuple[RunEvent, ...]:
        self._consumed.append(name)
        return tuple(self._batches.get(name, ()))

    def start(self) -> tuple[RunEvent, ...]:
        return self._next("start")

    def observe_step(self, step_result: object) -> tuple[RunEvent, ...]:
        return self._next("step")

    def observe_run(self, workflow_run: object) -> tuple[RunEvent, ...]:
        return self._next("run")

    def observe_failure(self, message: str) -> tuple[RunEvent, ...]:
        return self._next("failure")

    def event(self, kind: RunEventKind, **overrides: object) -> RunEvent:
        """Build one fake event with realistic defaults for tests."""
        defaults: dict[str, object] = {
            "kind": kind,
            "run_id": self._run_id,
            "sequence": len(self._consumed) + 1,
            "workflow_id": self._workflow.workflow_id,
            "created_at": datetime.now(UTC),
            "message": "",
        }
        defaults.update(overrides)
        return RunEvent(**defaults)  # type: ignore[arg-type]
