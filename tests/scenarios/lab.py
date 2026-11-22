"""Drive the resolver over the scenario matrix and count what really happened.

An adapter exposes the surface (candidates, truth, action, observation); the
resolver decides; this module records the outcome and flags a WRONG action
whenever an action hit anything other than the element the person meant, or
when anything at all was performed on a variant that should have asked or
stopped.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from engine.resolve import (
    Candidate,
    ResolutionContext,
    SafetyClass,
    Surface,
    TargetDescriptor,
    resolve,
)

from .model import Expectation, Intent, LabReport, Scenario, VariantResult

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
