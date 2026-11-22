"""Value types for the headless scenario lab.

A scenario records one step on variant A and replays it on variants B, C and D.
Each variant declares what *should* happen — ``SUCCESS``, ``ASKS_USER`` or
``SAFE_FAILURE`` — so the lab can count wrong actions instead of praising
itself for a resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from engine.resolve import ResolutionDecision, TargetDescriptor


class LabSurface(StrEnum):
    """Which adapter family a scenario drives."""

    WEB = "WEB"
    DESKTOP = "DESKTOP"


class Expectation(StrEnum):
    """The outcome a variant must produce."""

    SUCCESS = "SUCCESS"
    ASKS_USER = "ASKS_USER"
    SAFE_FAILURE = "SAFE_FAILURE"


@dataclass(frozen=True)
class Intent:
    """What the recorder captured on variant A for one step."""

    step_id: str
    words: str
    descriptor: TargetDescriptor
    expected_state: str
    #: Row/list rule the adapter may use to find the container first (None for
    #: a plain button). Never an index: an inserted advert would shift it.
    row_rule: str | None = None


@dataclass(frozen=True)
class Variant:
    """One replay variant of the surface plus its expected outcome."""

    name: str
    expectation: Expectation
    unattended: bool = False


@dataclass(frozen=True)
class Scenario:
    """One recorded step replayed across variant surfaces."""

    scenario_id: str
    surface: LabSurface
    recording: str
    intent: Intent
    variants: tuple[Variant, ...]


@dataclass(frozen=True)
class VariantResult:
    """What actually happened on one variant."""

    scenario_id: str
    variant: str
    expectation: Expectation
    decision: ResolutionDecision
    acted: bool
    wrong_action: bool
    postcondition_met: bool | None
    explanation: str

    @property
    def desired_decision(self) -> ResolutionDecision:
        return {
            Expectation.SUCCESS: ResolutionDecision.RESOLVED,
            Expectation.ASKS_USER: ResolutionDecision.ASK_USER,
            Expectation.SAFE_FAILURE: ResolutionDecision.STOP,
        }[self.expectation]

    @property
    def passed(self) -> bool:
        if self.decision is not self.desired_decision:
            return False
        if self.wrong_action:
            return False
        return self.postcondition_met is not False

    @property
    def line(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        post = "n/a" if self.postcondition_met is None else str(self.postcondition_met).lower()
        return (
            f"{status} {self.scenario_id}/{self.variant}: expected "
            f"{self.expectation.value}, got {self.decision.value} "
            f"(acted={str(self.acted).lower()}, wrong={str(self.wrong_action).lower()}, "
            f"postcondition={post})"
        )


@dataclass(frozen=True)
class LabReport:
    """The whole matrix, with the three numbers that matter."""

    results: tuple[VariantResult, ...]

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for result in self.results if result.passed) / len(self.results)

    @property
    def prompts(self) -> int:
        return sum(1 for result in self.results if result.decision is ResolutionDecision.ASK_USER)

    @property
    def wrong_actions(self) -> int:
        return sum(1 for result in self.results if result.wrong_action)

    @property
    def failures(self) -> tuple[VariantResult, ...]:
        return tuple(result for result in self.results if not result.passed)

    def summary(self) -> str:
        lines = [result.line for result in self.results]
        lines.append(
            f"pass rate: {self.pass_rate:.0%} "
            f"({sum(1 for r in self.results if r.passed)}/{len(self.results)} variants), "
            f"prompts: {self.prompts}, WRONG actions: {self.wrong_actions}"
        )
        return "\n".join(lines)
