"""Resolve a recorded target against the live surface, then act — flag-gated.

This is the boundary between the pure resolver (``engine.resolve``) and a real
UI adapter. It is consulted only when smart replay is enabled *and* the step
carries a descriptor, so with the flag off every workflow runs through exactly
the code path it ran through before.

Safety rules enforced here (docs/SMART_REPLAY.md §6, §10, §11):

- a destructive step is never performed by the engine's own choice, even with a
  perfect score; only a person may confirm it;
- an unattended run never asks: it stops, changes nothing, and says why;
- every wait is a bounded poll that checks cancellation before each poll, so
  Ctrl+Alt+Q and Stop are honoured while a target is being waited for.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .resolve import (
    Candidate,
    ClueKind,
    Resolution,
    ResolutionContext,
    ResolutionDecision,
    SafetyClass,
    normalise_text,
    resolve,
)
from .workflow import (
    ExpectedKind,
    ExpectedOutcome,
    StepDescriptor,
    StepResolution,
    StepResult,
    StepStatus,
    WaitBudget,
    WaitCondition,
    WorkflowStep,
)

#: Environment switch. Absent, empty or "0" keeps smart replay off.
SMART_REPLAY_ENV = "ONCE_SMART_REPLAY"
#: How many alternatives a run report keeps; the rest are counted only.
MAX_RECORDED_ALTERNATIVES = 4
#: How many "what differed" lines a run report keeps.
MAX_RECORDED_DIFFERENCES = 4
#: Clue kinds that describe where an element sits rather than what it is.
_POSITIONAL_KINDS = frozenset({ClueKind.ORDINAL, ClueKind.POSITION})


class UserAnswer(StrEnum):
    """What a person decided when the resolver asked which element to use."""

    APPROVE = "APPROVE"
    SKIP = "SKIP"
    STOP = "STOP"


@dataclass(frozen=True)
class StepQuestion:
    """The question shown to a person when one clear winner cannot be found."""

    step_id: str
    intent: str
    explanation: str
    candidates: tuple[str, ...]
    safety: SafetyClass


AskUser = Callable[[StepQuestion], UserAnswer]


@dataclass(frozen=True)
class SmartReplayOptions:
    """Feature switch plus who is watching the run."""

    enabled: bool = False
    unattended: bool = False
    ask_user: AskUser | None = None


def options_from_environment(
    environ: Mapping[str, str] | None = None,
    *,
    ask_user: AskUser | None = None,
    unattended: bool = False,
) -> SmartReplayOptions:
    """Build options from the environment; smart replay is off unless asked for."""
    values = os.environ if environ is None else environ
    return SmartReplayOptions(
        enabled=values.get(SMART_REPLAY_ENV, "").strip() == "1",
        unattended=unattended,
        ask_user=ask_user,
    )


class StepTargetAdapter(Protocol):
    """What a real adapter must provide; S3 implements this over UI Automation.

    ``observe`` returns the surface's human-readable state after an action. For
    ``VALUE_EQUALS`` and ``ELEMENT_ENABLED`` it returns exactly the value or
    ``"enabled"``; for the text kinds it returns the visible text.
    """

    def handles(self, step: WorkflowStep) -> bool: ...

    def candidates(self, step: WorkflowStep) -> tuple[Candidate, ...]: ...

    def perform(self, step: WorkflowStep, candidate: Candidate) -> StepResult: ...

    def observe(self, step: WorkflowStep) -> str: ...


class SmartReplay:
    """Run one descriptor step through the resolver and the adapter."""

    def __init__(
        self,
        adapter: StepTargetAdapter,
        options: SmartReplayOptions,
        *,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._adapter = adapter
        self._options = options
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic

    def handles(self, step: WorkflowStep) -> bool:
        """True only when the flag is on, a descriptor exists, and the adapter acts."""
        return self._options.enabled and step.descriptor is not None and self._adapter.handles(step)

    def run_step(self, step: WorkflowStep, cancel_check: Callable[[], bool]) -> StepResult:
        """Resolve, ask or stop, then act and verify — in that order."""
        descriptor = step.descriptor
        if descriptor is None:
            raise AssertionError("smart replay was asked to run a step without a descriptor")
        candidates, cancelled = self._wait_for_candidates(step, cancel_check)
        if cancelled:
            return StepResult(
                step.step_id,
                StepStatus.SKIPPED,
                "Skipped because the workflow was cancelled.",
            )

        resolution = resolve(
            descriptor.to_target(step.safety or SafetyClass.DESTRUCTIVE),
            candidates,
            ResolutionContext(unattended=self._options.unattended),
            intent=step.name,
        )
        if resolution.may_act and resolution.chosen is not None:
            return self._act(step, resolution, resolution.chosen)
        return self._handle_non_automatic(step, descriptor, resolution)

    # ------------------------------------------------------------- actions

    def _act(
        self,
        step: WorkflowStep,
        resolution: Resolution,
        chosen: Candidate,
        *,
        confirmed: bool = False,
    ) -> StepResult:
        """Perform the chosen element and check the expected outcome."""
        performed = self._adapter.perform(step, chosen)
        evidence = _evidence(resolution, step.descriptor, chosen)
        message = performed.message
        status = performed.status
        if status in {StepStatus.SUCCEEDED, StepStatus.VERIFIED} and step.expected is not None:
            observed = self._adapter.observe(step)
            if not _expected_met(step.expected, observed):
                status = StepStatus.FAILED
                message = _mismatch_message(step, chosen, step.expected, observed)
            elif confirmed:
                message = f"{message} You confirmed this step."
        return StepResult(
            step.step_id,
            status,
            message,
            performed.evidence,
            resolution=evidence,
        )

    def _handle_non_automatic(
        self,
        step: WorkflowStep,
        descriptor: StepDescriptor,
        resolution: Resolution,
    ) -> StepResult:
        """Ask a person when possible; otherwise stop without changing anything."""
        evidence = _evidence(resolution, descriptor, resolution.chosen)
        if (
            resolution.decision is ResolutionDecision.ASK_USER
            and self._options.ask_user is not None
        ):
            question = StepQuestion(
                step_id=step.step_id,
                intent=step.name,
                explanation=resolution.explanation,
                candidates=_candidate_labels(resolution),
                safety=descriptor.to_target(step.safety or SafetyClass.DESTRUCTIVE).safety,
            )
            answer = self._options.ask_user(question)
            if answer is UserAnswer.APPROVE and resolution.best is not None:
                return self._act(step, resolution, resolution.best.candidate, confirmed=True)
            if answer is UserAnswer.SKIP:
                return StepResult(
                    step.step_id,
                    StepStatus.FAILED,
                    "You chose to skip this step, so the run stopped instead of "
                    "continuing without it. Nothing was clicked.",
                    resolution=evidence,
                )
            return StepResult(
                step.step_id,
                StepStatus.FAILED,
                "You chose to stop, so the run stopped here. Nothing was clicked.",
                resolution=evidence,
            )
        return StepResult(
            step.step_id,
            StepStatus.FAILED,
            f"{resolution.explanation} Nothing was clicked.",
            resolution=evidence,
        )

    # --------------------------------------------------------------- waits

    def _wait_for_candidates(
        self, step: WorkflowStep, cancel_check: Callable[[], bool]
    ) -> tuple[tuple[Candidate, ...], bool]:
        """Bounded poll for the target; returns (candidates, cancelled)."""
        budget = step.wait
        if budget is None:
            if cancel_check():
                return (), True
            return self._adapter.candidates(step), False

        deadline = self._clock() + budget.timeout_seconds
        while True:
            if cancel_check():
                return (), True
            candidates = self._adapter.candidates(step)
            if self._condition_met(step, budget, candidates):
                return candidates, False
            remaining = deadline - self._clock()
            if remaining <= 0:
                return candidates, False
            self._sleep(min(budget.poll_interval_seconds, remaining))

    def _condition_met(
        self,
        step: WorkflowStep,
        budget: WaitBudget,
        candidates: tuple[Candidate, ...],
    ) -> bool:
        if budget.condition is WaitCondition.ELEMENT_PRESENT:
            return bool(candidates)
        if budget.condition is WaitCondition.ELEMENT_ENABLED:
            return any(candidate.enabled for candidate in candidates)
        expected = step.expected
        if expected is None:
            return bool(candidates)
        return _expected_met(expected, self._adapter.observe(step))


def _candidate_labels(resolution: Resolution) -> tuple[str, ...]:
    return tuple(
        f"{entry.candidate.label} ({entry.identity_score})"
        for entry in resolution.evaluated
        if entry.candidate.enabled
    )


def _evidence(
    resolution: Resolution,
    descriptor: StepDescriptor | None,
    chosen: Candidate | None,
) -> StepResolution:
    """The run report's account of why this element was chosen."""
    best = resolution.best
    strategy = tuple(kind.value for kind in best.matched_kinds) if best is not None else ()
    confidence = best.identity_score if best is not None else 0
    chosen_id = chosen.candidate_id if chosen is not None else None
    alternatives = tuple(
        f"{entry.candidate.label} ({entry.identity_score})"
        for entry in resolution.evaluated
        if entry.candidate.enabled and entry.candidate.candidate_id != chosen_id
    )[:MAX_RECORDED_ALTERNATIVES]
    return StepResolution(
        decision=resolution.decision.value,
        strategy=strategy,
        confidence=confidence,
        alternatives=alternatives,
        differed=_differences(descriptor, chosen),
        explanation=resolution.explanation,
    )


def _differences(descriptor: StepDescriptor | None, chosen: Candidate | None) -> tuple[str, ...]:
    """What no longer matches the recording, in plain language."""
    if descriptor is None or chosen is None:
        return ()
    lines: list[str] = []
    for clue in descriptor.clues:
        if clue.kind in _POSITIONAL_KINDS:
            continue
        found = [other.value for other in chosen.clues if other.kind is clue.kind]
        wanted = normalise_text(clue.value)
        if not found:
            lines.append(f"{clue.kind.value}: not found")
        elif not any(normalise_text(value) == wanted for value in found):
            lines.append(f'{clue.kind.value}: recorded "{clue.value}", found "{found[0]}"')
        if len(lines) >= MAX_RECORDED_DIFFERENCES:
            break
    return tuple(lines)


def _expected_met(expected: ExpectedOutcome, observed: str) -> bool:
    """Check the adapter's observation against the step's expected outcome."""
    value = expected.value.strip().casefold()
    seen = observed.strip().casefold()
    if expected.kind is ExpectedKind.TEXT_APPEARS:
        return bool(value) and value in seen
    if expected.kind is ExpectedKind.TEXT_DISAPPEARS:
        return bool(value) and value not in seen
    if expected.kind is ExpectedKind.VALUE_EQUALS:
        return seen == value
    if expected.kind is ExpectedKind.ELEMENT_ENABLED:
        return seen == "enabled"
    if expected.kind in {
        ExpectedKind.URL_MATCHES,
        ExpectedKind.WINDOW_TITLE,
        ExpectedKind.FOCUSED_ELEMENT,
    }:
        return bool(value) and value in seen
    return True


def _mismatch_message(
    step: WorkflowStep,
    chosen: Candidate,
    expected: ExpectedOutcome,
    observed: str,
) -> str:
    """A failed expectation in plain English, with no internal names."""
    want = expected.value.strip() or "the expected state"
    seen = observed.strip() or "nothing"
    return (
        f"Once used {chosen.label} but did not see what {step.name} expects "
        f"({want}). The screen shows: {seen}. Nothing else was done."
    )
