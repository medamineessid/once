"""Drive the resolver over the scenario matrix and count what really happened.

An adapter exposes the surface (candidates, truth, action, observation); the
resolver decides; this module records the outcome and flags a WRONG action
whenever an action hit anything other than the element the person meant, or
when anything at all was performed on a variant that should have asked or
stopped.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Protocol

from engine.resolve import (
    Candidate,
    ResolutionContext,
    ResolutionDecision,
    SafetyClass,
    Surface,
    TargetDescriptor,
    resolve,
)
from engine.smart_replay import SmartReplay, SmartReplayOptions
from engine.workflow import (
    ExpectedKind,
    ExpectedOutcome,
    StepDescriptor,
    StepKind,
    StepStatus,
    WorkflowStep,
)

from .model import Expectation, Intent, LabReport, LabSurface, Scenario, VariantResult

#: Called as ``observer(variant, phase)`` with phase ``"before"`` or ``"after"``.
Observer = Callable[[str, str], None]


class TargetAdapter(Protocol):
    """What the lab needs from a surface adapter.

    Deliberately tiny: candidates come from the live surface, while traversal
    (list paging, waiting for a delayed control) belongs to the adapter, not to
    the pure resolver.
    """

    def prepare(self, variant: str) -> None: ...

    def snapshot(self, variant: str, row_rule: str | None) -> tuple[Candidate, ...]: ...

    def truth_id(self, variant: str) -> str | None: ...

    def perform(self, candidate: Candidate) -> None: ...

    def observe(self) -> str: ...


def record_step(
    adapter: TargetAdapter,
    *,
    variant: str,
    step_id: str,
    words: str,
    safety: SafetyClass,
    surface: Surface,
    row_rule: str | None = None,
) -> Intent:
    """Record one step on the recording variant and capture its expected outcome.

    The descriptor is built from what the adapter actually observed on the
    recording variant, and the expected outcome from actually performing the
    action there, so a scenario cannot declare an outcome the app never showed.
    """
    adapter.prepare(variant)
    truth = adapter.truth_id(variant)
    candidates = adapter.snapshot(variant, row_rule)
    target = next((item for item in candidates if item.candidate_id == truth), None)
    if target is None:
        raise AssertionError(f"recording variant {variant} does not contain {truth}")
    descriptor = TargetDescriptor(
        surface=surface,
        clues=target.clues,
        safety=safety,
        position_hint=target.position,
    )
    adapter.perform(target)
    return Intent(
        step_id=step_id,
        words=words,
        descriptor=descriptor,
        expected_state=adapter.observe(),
        row_rule=row_rule,
    )


def run_scenario(
    scenario: Scenario,
    adapter: TargetAdapter,
    *,
    observer: Observer | None = None,
) -> tuple[VariantResult, ...]:
    """Replay one recorded step on every variant and record the outcome."""
    results: list[VariantResult] = []
    for variant in scenario.variants:
        adapter.prepare(variant.name)
        candidates = adapter.snapshot(variant.name, scenario.intent.row_rule)
        resolution = resolve(
            scenario.intent.descriptor,
            candidates,
            ResolutionContext(unattended=variant.unattended),
            intent=scenario.intent.words,
        )
        if observer is not None:
            observer(variant.name, "before")

        acted = False
        wrong_action = False
        postcondition: bool | None = None
        if resolution.may_act and resolution.chosen is not None:
            adapter.perform(resolution.chosen)
            acted = True
            wrong_action = resolution.chosen.candidate_id != adapter.truth_id(variant.name)
            if variant.expectation is not Expectation.SUCCESS:
                # Performing anything here was itself the wrong outcome.
                wrong_action = True
            postcondition = adapter.observe() == scenario.intent.expected_state

        if observer is not None:
            observer(variant.name, "after")
        results.append(
            VariantResult(
                scenario_id=scenario.scenario_id,
                variant=variant.name,
                expectation=variant.expectation,
                decision=resolution.decision,
                acted=acted,
                wrong_action=wrong_action,
                postcondition_met=postcondition,
                explanation=resolution.explanation,
            )
        )
    return tuple(results)


def run_matrix(cases: Iterable[tuple[Scenario, TargetAdapter]]) -> LabReport:
    """Run every scenario against its adapter and return one report."""
    results: list[VariantResult] = []
    for scenario, adapter in cases:
        results.extend(run_scenario(scenario, adapter))
    return LabReport(tuple(results))


class _Bridge:
    """Adapt a lab adapter to the smart-replay adapter interface."""

    def __init__(self, adapter: TargetAdapter, variant: str, row_rule: str | None) -> None:
        self._adapter = adapter
        self._variant = variant
        self._row_rule = row_rule
        self.performed: list[Candidate] = []

    def handles(self, step: WorkflowStep) -> bool:
        return step.kind is StepKind.CLICK_UI_ELEMENT

    def candidates(self, step: WorkflowStep) -> tuple[Candidate, ...]:
        return self._adapter.snapshot(self._variant, self._row_rule)

    def perform(self, step: WorkflowStep, chosen: Candidate) -> object:
        from engine.workflow import StepResult

        self._adapter.perform(chosen)
        self.performed.append(chosen)
        return StepResult(step.step_id, StepStatus.SUCCEEDED, "The step ran.")

    def observe(self, step: WorkflowStep) -> str:
        return self._adapter.observe()


def _lab_step(scenario: Scenario) -> WorkflowStep:
    """The recorded step as the engine would receive it from a workflow file."""
    descriptor = scenario.intent.descriptor
    surface = Surface.WEB if scenario.surface is LabSurface.WEB else Surface.DESKTOP
    return WorkflowStep(
        step_id=scenario.intent.step_id,
        name=scenario.intent.words,
        kind=StepKind.CLICK_UI_ELEMENT,
        message="Lab step.",
        target=json.dumps({"window": {"title": "Lab"}, "element": {"name": "lab"}}),
        descriptor=StepDescriptor(
            surface=surface, clues=descriptor.clues, position_hint=descriptor.position_hint
        ),
        expected=ExpectedOutcome(ExpectedKind.TEXT_APPEARS, scenario.intent.expected_state),
        safety=descriptor.safety,
    )


def run_scenario_through_smart_replay(
    scenario: Scenario, adapter: TargetAdapter
) -> tuple[VariantResult, ...]:
    """Replay the same matrix through the flag-gated integration, not the bare resolver."""
    step = _lab_step(scenario)
    results: list[VariantResult] = []
    for variant in scenario.variants:
        adapter.prepare(variant.name)
        bridge = _Bridge(adapter, variant.name, scenario.intent.row_rule)
        replay = SmartReplay(
            bridge,  # type: ignore[arg-type]
            SmartReplayOptions(enabled=True, unattended=variant.unattended),
        )
        outcome = replay.run_step(step, lambda: False)
        evidence = outcome.resolution
        decision = (
            ResolutionDecision(evidence.decision)
            if evidence is not None
            else ResolutionDecision.STOP
        )
        performed = [candidate.candidate_id for candidate in bridge.performed]
        truth = adapter.truth_id(variant.name)
        wrong = bool(performed) and (performed[0] != truth)
        if performed and variant.expectation is not Expectation.SUCCESS:
            wrong = True
        postcondition = adapter.observe() == scenario.intent.expected_state if performed else None
        results.append(
            VariantResult(
                scenario_id=scenario.scenario_id,
                variant=variant.name,
                expectation=variant.expectation,
                decision=decision,
                acted=bool(performed),
                wrong_action=wrong,
                postcondition_met=postcondition,
                explanation=evidence.explanation if evidence is not None else outcome.message,
            )
        )
    return tuple(results)


def run_matrix_through_smart_replay(
    cases: Iterable[tuple[Scenario, TargetAdapter]],
) -> LabReport:
    """Run every scenario through the integration and return one report."""
    results: list[VariantResult] = []
    for scenario, adapter in cases:
        results.extend(run_scenario_through_smart_replay(scenario, adapter))
    return LabReport(tuple(results))
