"""The headless scenario lab: record on A, replay on B/C/D, count outcomes.

Both surfaces are real: the web scenarios run against a local HTTP server and
the Qt scenarios against an offscreen widget tree. No browser is launched and
nothing touches the real desktop.
"""

from __future__ import annotations

import pytest

from engine.resolve import Candidate, Clue, ClueKind, SafetyClass, Surface, TargetDescriptor
from tests.scenarios.catalog import qt_cases, web_cases
from tests.scenarios.lab import run_matrix, run_scenario
from tests.scenarios.model import Expectation, Intent, LabReport, LabSurface, Scenario, Variant


def test_web_scenarios_meet_expectations_without_wrong_actions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with web_cases() as cases:
        report = run_matrix(cases)

    with capsys.disabled():
        print("\n[web]")
        print(report.summary())

    assert report.wrong_actions == 0, [result.line for result in report.failures]
    assert not report.failures, [result.line for result in report.failures]
    assert report.pass_rate == 1.0


def test_qt_scenarios_meet_expectations_without_wrong_actions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with qt_cases() as cases:
        report = run_matrix(cases)

    with capsys.disabled():
        print("\n[qt]")
        print(report.summary())

    assert report.wrong_actions == 0, [result.line for result in report.failures]
    assert not report.failures, [result.line for result in report.failures]
    assert report.pass_rate == 1.0


def test_the_matrix_covers_every_expected_outcome() -> None:
    with web_cases() as web, qt_cases() as qt:
        report = run_matrix([*web, *qt])

    assert {result.expectation.value for result in report.results} == {
        "SUCCESS",
        "ASKS_USER",
        "SAFE_FAILURE",
    }
    assert report.wrong_actions == 0
    assert report.prompts > 0
    assert len(report.results) >= 15


class _WrongElementAdapter:
    """A deliberately bad adapter: it always offers one element that is not the target."""

    def prepare(self, variant: str) -> None:
        self._variant = variant

    def snapshot(self, variant: str, row_rule: str | None) -> tuple[Candidate, ...]:
        del variant, row_rule
        return (Candidate("not-the-target", (Clue(ClueKind.NAME, "Save", "name"),)),)

    def truth_id(self, variant: str) -> str | None:
        del variant
        return "wanted"

    def perform(self, candidate: Candidate) -> None:
        self._performed = candidate.candidate_id

    def observe(self) -> str:
        return "action=not-the-target"


def test_the_lab_counts_a_wrong_action_and_fails_the_variant() -> None:
    """The metric must be able to fail, or the green matrix means nothing."""
    scenario = Scenario(
        "self-check",
        LabSurface.DESKTOP,
        "A",
        Intent(
            "step",
            "Save",
            TargetDescriptor(
                surface=Surface.DESKTOP,
                clues=(Clue(ClueKind.NAME, "Save", "name"),),
                safety=SafetyClass.REVERSIBLE,
            ),
            "action=wanted",
        ),
        (Variant("B", Expectation.SUCCESS),),
    )

    result = run_scenario(scenario, _WrongElementAdapter())[0]

    assert result.acted
    assert result.wrong_action
    assert result.postcondition_met is False
    assert not result.passed
    assert LabReport((result,)).wrong_actions == 1
    assert LabReport((result,)).pass_rate == 0.0
