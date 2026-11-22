"""Smart replay wiring: resolver behind a flag, default off.

Written before ``engine/smart_replay.py`` exists; every test fails at import
until the module, the step-resolution evidence and the runner hook exist.
"""

from __future__ import annotations

import json

import pytest

from engine.resolve import Candidate, Clue, ClueKind, SafetyClass, Surface
from engine.smart_replay import (
    SMART_REPLAY_ENV,
    SmartReplay,
    SmartReplayOptions,
    StepQuestion,
    UserAnswer,
    options_from_environment,
)
from engine.workflow import (
    ExpectedKind,
    ExpectedOutcome,
    StepDescriptor,
    StepKind,
    StepStatus,
    WaitBudget,
    WaitCondition,
    Workflow,
    WorkflowRunner,
    WorkflowStatus,
    WorkflowStep,
)

WINDOW = {"title": "Once demo", "class_name": "DemoWindowClass"}
CLICK_TARGET = json.dumps(
    {"window": WINDOW, "element": {"automation_id": "edit-1042", "control_type": "Button"}}
)

DESCRIPTOR = StepDescriptor(
    surface=Surface.DESKTOP,
    clues=(
        Clue(ClueKind.AUTOMATION_ID, "edit-1042", "automation_id"),
        Clue(ClueKind.NAME, "Edit", "name"),
        Clue(ClueKind.CONTAINER_TEXT, "Invoice 1042", "container"),
    ),
    position_hint=(120, 340),
)


def edit_step(
    *,
    safety: SafetyClass = SafetyClass.REVERSIBLE,
    expected: ExpectedOutcome | None = None,
    wait: WaitBudget | None = None,
    descriptor: StepDescriptor | None = DESCRIPTOR,
) -> WorkflowStep:
    return WorkflowStep(
        step_id="edit",
        name="Edit invoice 1042",
        kind=StepKind.CLICK_UI_ELEMENT,
        message="Open the invoice.",
        target=CLICK_TARGET,
        descriptor=descriptor,
        expected=expected,
        safety=safety,
        wait=wait,
    )


def candidate(
    candidate_id: str,
    *,
    name: str = "Edit",
    container: str = "Invoice 1042",
    identifier: str | None = "edit-1042",
) -> Candidate:
    clues = [
        Clue(ClueKind.ROLE, "button", "role"),
        Clue(ClueKind.NAME, name, "name"),
        Clue(ClueKind.CONTAINER_TEXT, container, "container"),
    ]
    if identifier is not None:
        clues.insert(0, Clue(ClueKind.AUTOMATION_ID, identifier, "automation_id"))
    return Candidate(candidate_id, tuple(clues), enabled=True, position=(120, 340))


class FakeAdapter:
    """Deterministic stand-in for a real UI adapter."""

    def __init__(
        self,
        snapshots: list[tuple[Candidate, ...]],
        *,
        observation: str = "Invoice 1042 opened",
        perform_status: StepStatus = StepStatus.SUCCEEDED,
    ) -> None:
        self.snapshots = list(snapshots)
        self.observation = observation
        self.perform_status = perform_status
        self.performed: list[str] = []
        self.observed = 0

    def handles(self, step: WorkflowStep) -> bool:
        return step.kind is StepKind.CLICK_UI_ELEMENT

    def candidates(self, step: WorkflowStep) -> tuple[Candidate, ...]:
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]

    def perform(self, step: WorkflowStep, chosen: Candidate):
        from engine.workflow import StepResult

        self.performed.append(chosen.candidate_id)
        return StepResult(step.step_id, self.perform_status, "Clicked the element.")

    def observe(self, step: WorkflowStep) -> str:
        self.observed += 1
        return self.observation


class FakeDeskActions:
    """Legacy path marker: proves the old provider is or is not used."""

    def __init__(self) -> None:
        self.calls = 0

    def click_element(self, target_json: str):
        from engine.workflow import StepResult

        self.calls += 1
        return StepResult("edit", StepStatus.SUCCEEDED, "Legacy click.")


def replay_of(adapter: FakeAdapter, **options: object) -> SmartReplay:
    defaults: dict[str, object] = {"enabled": True, "unattended": False}
    defaults.update(options)
    return SmartReplay(adapter, SmartReplayOptions(**defaults))  # type: ignore[arg-type]


def run(step: WorkflowStep, replay: SmartReplay | None, desk: FakeDeskActions | None = None):
    workflow = Workflow("w", "W", (step,))
    return WorkflowRunner().run(
        workflow,
        allowed_root=None,
        smart_replay=replay,
        desktop_actions=desk,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------- flag off


def test_the_flag_is_off_by_default() -> None:
    assert options_from_environment({}).enabled is False
    assert SmartReplayOptions().enabled is False


def test_the_flag_can_be_enabled_from_the_environment() -> None:
    assert options_from_environment({SMART_REPLAY_ENV: "1"}).enabled is True


def test_flag_off_uses_the_existing_path_and_never_consults_the_adapter() -> None:
    adapter = FakeAdapter([(candidate("right"),)])
    desk = FakeDeskActions()

    result = run(edit_step(), SmartReplay(adapter, SmartReplayOptions(enabled=False)), desk)

    assert result.results[0].status is StepStatus.SUCCEEDED
    assert desk.calls == 1
    assert adapter.performed == []
    assert result.results[0].resolution is None


def test_a_step_without_a_descriptor_is_left_to_the_existing_path() -> None:
    adapter = FakeAdapter([(candidate("right"),)])
    desk = FakeDeskActions()

    result = run(edit_step(descriptor=None), replay_of(adapter), desk)

    assert desk.calls == 1
    assert adapter.performed == []
    assert result.results[0].resolution is None


# ---------------------------------------------------------------- flag on


def test_a_clear_winner_is_performed_and_the_evidence_is_recorded() -> None:
    adapter = FakeAdapter([(candidate("right"),)])
    step = edit_step(expected=ExpectedOutcome(ExpectedKind.TEXT_APPEARS, "Invoice 1042"))

    result = run(step, replay_of(adapter))
    step_result = result.results[0]

    assert adapter.performed == ["right"]
    assert step_result.status is StepStatus.SUCCEEDED
    assert step_result.resolution is not None
    assert "AUTOMATION_ID" in step_result.resolution.strategy
    assert step_result.resolution.confidence >= 30
    assert step_result.resolution.explanation


def test_the_evidence_records_what_differed_from_the_recording() -> None:
    adapter = FakeAdapter([(candidate("right", name="Modify"),)])

    result = run(edit_step(), replay_of(adapter))
    evidence = result.results[0].resolution

    assert evidence is not None
    assert any("Edit" in line and "Modify" in line for line in evidence.differed)


def test_alternatives_are_recorded_for_the_run_report() -> None:
    adapter = FakeAdapter(
        [(candidate("right"), candidate("other", name="Archive", identifier="archive-1042"))]
    )

    result = run(edit_step(), replay_of(adapter))
    evidence = result.results[0].resolution

    assert evidence is not None
    assert evidence.alternatives
    assert all(isinstance(line, str) for line in evidence.alternatives)


def test_an_ambiguous_target_stops_an_unattended_run_without_acting() -> None:
    adapter = FakeAdapter([(candidate("a"), candidate("b"))])

    result = run(edit_step(), replay_of(adapter, unattended=True))

    assert adapter.performed == []
    assert result.results[0].status is StepStatus.FAILED
    assert result.status is WorkflowStatus.FAILED
    assert "person" in result.results[0].message.lower()
    assert "delete" not in result.results[0].message.lower()


def test_an_ambiguous_target_asks_and_acts_when_the_person_approves() -> None:
    seen: list[StepQuestion] = []

    def ask(question: StepQuestion) -> UserAnswer:
        seen.append(question)
        return UserAnswer.APPROVE

    adapter = FakeAdapter([(candidate("a"), candidate("b"))])
    result = run(edit_step(), replay_of(adapter, ask_user=ask))

    assert len(seen) == 1
    assert seen[0].step_id == "edit"
    assert len(seen[0].candidates) == 2
    assert adapter.performed == ["a"]
    assert result.results[0].status is StepStatus.SUCCEEDED


def test_an_ambiguous_target_asks_and_stops_when_the_person_skips() -> None:
    adapter = FakeAdapter([(candidate("a"), candidate("b"))])

    result = run(edit_step(), replay_of(adapter, ask_user=lambda question: UserAnswer.SKIP))

    assert adapter.performed == []
    assert result.results[0].status is StepStatus.FAILED


def test_a_destructive_step_is_never_auto_picked() -> None:
    adapter = FakeAdapter([(candidate("right"),)])
    step = edit_step(safety=SafetyClass.DESTRUCTIVE)

    result = run(step, replay_of(adapter))

    assert adapter.performed == []
    assert result.results[0].status is StepStatus.FAILED
    assert "confirmation" in result.results[0].message.lower()


def test_a_person_may_confirm_a_destructive_step() -> None:
    adapter = FakeAdapter([(candidate("right"),)])
    step = edit_step(safety=SafetyClass.DESTRUCTIVE)

    result = run(step, replay_of(adapter, ask_user=lambda question: UserAnswer.APPROVE))

    assert adapter.performed == ["right"]
    assert result.results[0].status is StepStatus.SUCCEEDED


# ------------------------------------------------------------------ waits


class Clock:
    """Deterministic clock: sleeping advances time instead of pausing."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_a_wait_honours_cancellation_before_the_next_poll() -> None:
    clock = Clock()
    adapter = FakeAdapter([()])
    step = edit_step(wait=WaitBudget(WaitCondition.ELEMENT_PRESENT, 10.0, 0.5))
    replay = SmartReplay(adapter, SmartReplayOptions(enabled=True), sleep=clock.sleep, clock=clock)
    calls = {"count": 0}

    def cancelled() -> bool:
        calls["count"] += 1
        return calls["count"] > 1

    result = replay.run_step(step, cancelled)

    assert result.status is StepStatus.SKIPPED
    assert adapter.performed == []
    assert clock.slept, "the wait should have polled before giving up"


def test_a_wait_finishes_as_soon_as_the_target_appears() -> None:
    clock = Clock()
    adapter = FakeAdapter([(), (), (candidate("right"),)])
    step = edit_step(wait=WaitBudget(WaitCondition.ELEMENT_PRESENT, 10.0, 0.5))
    replay = SmartReplay(adapter, SmartReplayOptions(enabled=True), sleep=clock.sleep, clock=clock)

    result = replay.run_step(step, lambda: False)

    assert adapter.performed == ["right"]
    assert result.status is StepStatus.SUCCEEDED
    assert len(clock.slept) == 2


def test_a_wait_gives_up_at_its_deadline() -> None:
    clock = Clock()
    adapter = FakeAdapter([()])
    step = edit_step(wait=WaitBudget(WaitCondition.ELEMENT_PRESENT, 1.0, 0.5))
    replay = SmartReplay(
        adapter, SmartReplayOptions(enabled=True, unattended=True), sleep=clock.sleep, clock=clock
    )

    result = replay.run_step(step, lambda: False)

    assert adapter.performed == []
    assert result.status is StepStatus.FAILED
    assert clock.now >= 1.0


# ------------------------------------------------------------- postcondition


def test_a_missing_expected_result_fails_the_step() -> None:
    adapter = FakeAdapter([(candidate("right"),)], observation="Editor closed")
    step = edit_step(expected=ExpectedOutcome(ExpectedKind.TEXT_APPEARS, "Invoice 1042"))

    result = run(step, replay_of(adapter))

    assert result.results[0].status is StepStatus.FAILED
    assert "invoice 1042" in result.results[0].message.lower()


def test_a_satisfied_expected_result_keeps_the_step_successful() -> None:
    adapter = FakeAdapter([(candidate("right"),)], observation="Invoice 1042 is open")
    step = edit_step(expected=ExpectedOutcome(ExpectedKind.TEXT_APPEARS, "Invoice 1042"))

    result = run(step, replay_of(adapter))

    assert result.results[0].status is StepStatus.SUCCEEDED


# -------------------------------------------------------------------- run level


def test_a_smart_failure_stops_the_run_and_explains_the_skipped_step() -> None:
    adapter = FakeAdapter([(candidate("a"), candidate("b"))])
    workflow = Workflow(
        "w",
        "W",
        (edit_step(), WorkflowStep("after", "Later", StepKind.REPORT, "Later.")),
    )

    result = WorkflowRunner().run(workflow, allowed_root=None, smart_replay=replay_of(adapter))

    assert result.status is WorkflowStatus.FAILED
    assert result.results[1].status is StepStatus.SKIPPED
    assert "earlier step failed" in result.results[1].message


def test_the_replay_executor_passes_the_layer_through_the_policy_gate() -> None:
    from engine.replay import DESKTOP_INTERACTION_POLICY, ReplayExecutor

    adapter = FakeAdapter([(candidate("right"),)])
    executor = ReplayExecutor(DESKTOP_INTERACTION_POLICY)

    run_result = executor.execute(
        Workflow("w", "W", (edit_step(),)),
        allowed_root=None,
        smart_replay=replay_of(adapter),
        desktop_actions=FakeDeskActions(),  # type: ignore[arg-type]
    )

    assert adapter.performed == ["right"]
    assert run_result.results[0].resolution is not None


@pytest.mark.parametrize("attempts", [1, 2, 3])
def test_the_evidence_survives_retries(attempts: int) -> None:
    adapter = FakeAdapter([(candidate("a"), candidate("b"))])
    step = edit_step()
    if attempts > 1:
        step = WorkflowStep(
            step_id=step.step_id,
            name=step.name,
            kind=step.kind,
            message=step.message,
            target=step.target,
            max_attempts=attempts,
            descriptor=step.descriptor,
            safety=step.safety,
        )

    result = run(step, replay_of(adapter))

    assert result.results[0].status is StepStatus.FAILED
    assert result.results[0].resolution is not None
