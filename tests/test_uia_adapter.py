"""UI Automation adapter: clue capture, fallback order, focus and DPI rules.

Everything here runs against a fake surface, so no window is ever opened and no
key or click is ever sent. Real pywinauto behaviour is covered only by the
opt-in test at the bottom, which is skipped unless ``ONCE_REAL_DESKTOP=1``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import pytest

from engine.errors import ExecutionError
from engine.resolve import Candidate, Clue, ClueKind, SafetyClass, Surface
from engine.smart_replay import SmartReplay, SmartReplayOptions
from engine.workflow import (
    ExpectedKind,
    ExpectedOutcome,
    StepDescriptor,
    StepKind,
    StepStatus,
    WorkflowStep,
)
from integrations.uia_adapter import (
    UIA_STEP_KINDS,
    UiaTargetAdapter,
    descriptor_from_element,
    descriptor_from_event,
    element_clues,
)

WINDOW = {"title": "Once demo", "class_name": "DemoWindowClass"}
CLICK_TARGET = json.dumps({"window": WINDOW, "element": {"automation_id": "edit-1042"}})
TEXT_TARGET = json.dumps(
    {"window": WINDOW, "element": {"automation_id": "edit-1042"}, "text": "1042"}
)
SHORTCUT_TARGET = json.dumps({"window": WINDOW, "keys": "ctrl+s"})


@dataclass
class FakeInfo:
    """The metadata fields pywinauto exposes on ``element_info``."""

    name: str | None = "Edit"
    automation_id: str | None = "edit-1042"
    control_type: str | None = "Button"
    class_name: str | None = "Button"
    is_password: bool = False


@dataclass
class FakeElement:
    element_info: FakeInfo = field(default_factory=FakeInfo)
    enabled: bool = True
    rect: tuple[int, int, int, int] = (100, 300, 200, 340)
    pattern: bool = True
    keeps_text: bool = True
    fail_invoke: bool = False


@dataclass
class FakeWindow:
    element_info: FakeInfo = field(default_factory=lambda: FakeInfo(name="Once demo"))
    handle: int = 4242


class FakeSurface:
    """A desktop that records what was attempted and never touches the OS."""

    def __init__(
        self,
        elements: list[FakeElement] | None = None,
        *,
        title: str = "Once demo",
        in_front: bool = True,
        focus_works: bool = True,
        scale: int = 1,
    ) -> None:
        self.elements = elements if elements is not None else [FakeElement()]
        self.title = title
        self.in_front = in_front
        self.focus_works = focus_works
        self.scale = scale
        self.window_calls = 0
        self.descendant_scans = 0
        self.invoked: list[FakeElement] = []
        self.clicks: list[tuple[int, int]] = []
        self.keys: list[tuple[object, str]] = []
        self.focus_calls: list[object] = []
        self.set_values: list[str] = []
        self.values: dict[int, str] = {}
        self._window = FakeWindow(handle=4242)

    # -- window / elements
    def window(self) -> FakeWindow:
        self.window_calls += 1
        return self._window

    def window_title(self) -> str:
        return self.title

    def descendants(self, window: object) -> list[FakeElement]:
        self.descendant_scans += 1
        return list(self.elements)

    def info(self, element: FakeElement) -> FakeInfo:
        return element.element_info

    def enabled(self, element: FakeElement) -> bool:
        return element.enabled

    def rectangle(self, element: FakeElement) -> tuple[int, int, int, int]:
        return element.rect

    # -- actions
    def supports_invoke(self, element: FakeElement) -> bool:
        return element.pattern

    def invoke(self, element: FakeElement) -> None:
        if element.fail_invoke:
            raise ExecutionError("The control refused the pattern action.")
        self.invoked.append(element)

    def set_text(self, element: FakeElement, text: str) -> None:
        self.set_values.append(text)
        if element.keeps_text:
            self.values[id(element)] = text

    def read_text(self, element: FakeElement) -> str | None:
        return self.values.get(id(element))

    def focus(self, target: object) -> None:
        self.focus_calls.append(target)
        if self.focus_works:
            self.in_front = True

    def send_keys(self, target: object, keys: str) -> None:
        self.keys.append((target, keys))
        if isinstance(target, FakeElement) and target.keeps_text:
            self.values[id(target)] = keys

    def click_point(self, x: int, y: int) -> None:
        self.clicks.append((x, y))

    def foreground_handle(self) -> int:
        return self._window.handle if self.in_front else 0

    def window_handle(self) -> int:
        return self._window.handle

    def physical_point(self, x: int, y: int) -> tuple[int, int]:
        return (x * self.scale, y * self.scale)


def step(
    kind: StepKind = StepKind.CLICK_UI_ELEMENT,
    *,
    target: str = CLICK_TARGET,
    descriptor: StepDescriptor | None = None,
    expected: ExpectedOutcome | None = None,
    safety: SafetyClass | None = None,
) -> WorkflowStep:
    return WorkflowStep(
        step_id="edit",
        name="Open invoice 1042",
        kind=kind,
        message="Open the invoice.",
        target=target,
        descriptor=descriptor,
        expected=expected,
        safety=safety,
    )


class FakeClock:
    """A clock that only moves when something sleeps on it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def adapter(
    surface: FakeSurface,
    *,
    target: str = CLICK_TARGET,
    clock: FakeClock | None = None,
) -> UiaTargetAdapter:
    ticking = clock or FakeClock()
    return UiaTargetAdapter(surface, target, sleep=ticking.sleep, clock=ticking)


def chosen(surface: FakeSurface, step_obj: WorkflowStep) -> Candidate:
    candidates = adapter(surface).candidates(step_obj)
    assert candidates, "the fake surface should offer at least one candidate"
    return candidates[0]


# ------------------------------------------------------------------ capture


def test_each_captured_clue_keeps_its_own_group() -> None:
    clues = element_clues(FakeInfo(), ordinal=3, process="notepad.exe")

    groups = {clue.kind: clue.group for clue in clues}
    assert groups[ClueKind.AUTOMATION_ID] == "element.id"
    assert groups[ClueKind.ROLE] == "element.role"
    assert groups[ClueKind.NAME] == "element.name"
    assert groups[ClueKind.PROCESS] == "element.process"
    assert len(set(groups.values())) == len(groups), "one clue per group, never stacked evidence"


def test_a_captured_descriptor_names_the_desktop_surface() -> None:
    descriptor = descriptor_from_element(FakeInfo(), process="notepad.exe", position=(120, 340))

    assert descriptor is not None
    assert descriptor.surface is Surface.DESKTOP
    assert descriptor.position_hint == (120, 340)


def test_a_password_field_never_produces_a_descriptor() -> None:
    assert descriptor_from_element(FakeInfo(is_password=True)) is None


def test_an_element_with_no_identity_is_refused_even_with_a_position() -> None:
    anonymous = FakeInfo(name=None, automation_id=None, control_type=None)

    assert descriptor_from_element(anonymous, position=(10, 20)) is None


def test_position_and_ordinal_alone_are_not_an_identity() -> None:
    anonymous = FakeInfo(name=None, automation_id=None, control_type=None)

    assert descriptor_from_element(anonymous, ordinal=4, position=(10, 20)) is None


def test_a_recorded_click_becomes_a_descriptor_with_a_position_hint() -> None:
    from recorder.models import RecordedEvent, RecordedEventKind, UIElementInfo

    event = RecordedEvent(
        sequence=4,
        timestamp_ns=1,
        kind=RecordedEventKind.MOUSE_CLICK,
        window_title="Once demo",
        process_name="once.exe",
        element=UIElementInfo(automation_id="edit-1042", control_type="Button", name="Edit"),
        x=120,
        y=340,
    )

    descriptor = descriptor_from_event(event)

    assert descriptor is not None
    assert descriptor.position_hint == (120, 340)
    assert any(clue.kind is ClueKind.PROCESS for clue in descriptor.clues)


def test_a_keystroke_without_element_metadata_is_not_captured() -> None:
    from recorder.models import RecordedEvent, RecordedEventKind

    event = RecordedEvent(
        sequence=5, timestamp_ns=2, kind=RecordedEventKind.KEY_PRESS, key="ctrl+s"
    )

    assert descriptor_from_event(event) is None


def test_a_password_click_is_never_captured() -> None:
    from recorder.models import RecordedEvent, RecordedEventKind, UIElementInfo

    event = RecordedEvent(
        sequence=6,
        timestamp_ns=3,
        kind=RecordedEventKind.MOUSE_CLICK,
        element=UIElementInfo(automation_id="pw", name="Password", is_password=True),
        x=10,
        y=20,
    )

    assert descriptor_from_event(event) is None


# ---------------------------------------------------------------- candidates


def test_candidates_carry_position_and_enabled_state() -> None:
    surface = FakeSurface([FakeElement(), FakeElement(enabled=False, rect=(0, 0, 0, 0))])

    candidates = adapter(surface).candidates(step())

    assert [candidate.position for candidate in candidates] == [(150, 320), None]
    assert [candidate.enabled for candidate in candidates] == [True, False]


def test_a_missing_window_offers_no_candidates_instead_of_raising() -> None:
    class ClosedSurface(FakeSurface):
        def window(self) -> FakeWindow:
            raise ExecutionError("The identified window was not found.")

    assert adapter(ClosedSurface()).candidates(step()) == ()


def test_the_adapter_only_claims_the_kinds_it_can_perform() -> None:
    surface = FakeSurface()
    assert adapter(surface).handles(step(StepKind.CLICK_UI_ELEMENT))
    assert adapter(surface).handles(step(StepKind.TYPE_TEXT))
    assert not adapter(surface).handles(step(StepKind.REPORT))
    assert StepKind.CLICK_UI_ELEMENT in UIA_STEP_KINDS


# ------------------------------------------------------------------ fallbacks


def test_the_pattern_is_tried_before_any_key_or_click() -> None:
    surface = FakeSurface()

    result = adapter(surface).perform(step(), chosen(surface, step()))

    assert result.status is StepStatus.SUCCEEDED
    assert len(surface.invoked) == 1
    assert surface.keys == [] and surface.clicks == []
    assert "click_method=pattern" in result.evidence


def test_a_control_without_a_pattern_is_clicked_with_the_keyboard() -> None:
    surface = FakeSurface([FakeElement(pattern=False)])

    result = adapter(surface).perform(step(), chosen(surface, step()))

    assert result.status is StepStatus.SUCCEEDED
    assert surface.keys and surface.keys[0][1] == "{ENTER}"
    assert surface.focus_calls, "the window must be focused before keys are sent"
    assert "click_method=keyboard" in result.evidence
    assert "foreground_verified=true" in result.evidence


def test_a_window_that_will_not_come_forward_never_receives_keys() -> None:
    surface = FakeSurface([FakeElement(pattern=False)], in_front=False, focus_works=False)

    result = adapter(surface).perform(step(), chosen(surface, step()))

    assert surface.keys == [], "no key may be sent to whatever happens to be focused"
    assert "keyboard_refused" in result.evidence
    # The mouse fallback is still allowed, because it names an exact point.
    assert result.status is StepStatus.SUCCEEDED
    assert "click_method=mouse_centre" in result.evidence


def test_the_mouse_fallback_clicks_converted_physical_pixels() -> None:
    surface = FakeSurface([FakeElement(pattern=False)], in_front=False, focus_works=False, scale=2)

    result = adapter(surface).perform(step(), chosen(surface, step()))

    assert surface.clicks == [(300, 640)], "the click must use DPI-converted pixels"
    assert "coords=300,640" in result.evidence
    assert result.status is StepStatus.SUCCEEDED


def test_a_failed_pattern_click_falls_through_to_the_next_method() -> None:
    surface = FakeSurface([FakeElement(fail_invoke=True)], in_front=False, focus_works=False)

    result = adapter(surface).perform(step(), chosen(surface, step()))

    assert "pattern_refused" in result.evidence
    assert surface.clicks, "the mouse centre is the last resort"
    assert result.status is StepStatus.SUCCEEDED


def test_every_attempt_finds_the_element_again() -> None:
    surface = FakeSurface([FakeElement(pattern=False)])

    adapter(surface).perform(step(), chosen(surface, step()))

    # One scan for the candidates, then one per attempt before it runs.
    assert surface.descendant_scans >= 3


def test_a_vanished_element_stops_the_step_without_acting() -> None:
    surface = FakeSurface()
    stale = chosen(surface, step())
    surface.elements = []

    result = adapter(surface).perform(step(), stale)

    assert result.status is StepStatus.FAILED
    assert "no longer on screen" in result.message
    assert surface.clicks == [] and surface.keys == [] and surface.invoked == []


def test_two_matching_elements_are_refused_rather_than_guessed() -> None:
    surface = FakeSurface([FakeElement(), FakeElement()])

    result = adapter(surface).perform(step(), chosen(surface, step()))

    assert result.status is StepStatus.FAILED
    assert "refused rather than guessing" in result.message
    assert surface.invoked == []


def test_a_disabled_element_is_never_acted_on() -> None:
    surface = FakeSurface([FakeElement(enabled=False)])

    result = adapter(surface).perform(step(), chosen(surface, step()))

    assert result.status is StepStatus.FAILED
    assert "disabled" in result.message
    assert surface.invoked == [] and surface.clicks == []


def test_an_element_identified_only_by_place_is_refused_at_perform_time() -> None:
    surface = FakeSurface()
    positional_only = Candidate(
        "uia-0",
        (Clue(ClueKind.ROLE, "Button", "element.role"),),
        position=(150, 320),
    )

    result = adapter(surface).perform(step(), positional_only)

    assert result.status is StepStatus.FAILED
    assert "anything but its place" in result.message


# ---------------------------------------------------------------------- text


def test_text_is_confirmed_by_reading_the_control_back() -> None:
    surface = FakeSurface()
    target = TEXT_TARGET

    result = adapter(surface, target=target).perform(
        step(StepKind.TYPE_TEXT, target=target),
        chosen(surface, step(StepKind.TYPE_TEXT, target=target)),
    )

    assert result.status is StepStatus.SUCCEEDED
    assert surface.set_values == ["1042"]
    assert "readback_confirmed=true" in result.evidence


def test_text_the_control_does_not_keep_is_a_failure() -> None:
    surface = FakeSurface([FakeElement(pattern=False, keeps_text=False)])
    target = TEXT_TARGET

    result = adapter(surface, target=target).perform(
        step(StepKind.TYPE_TEXT, target=target),
        chosen(surface, step(StepKind.TYPE_TEXT, target=target)),
    )

    assert result.status is StepStatus.FAILED
    assert "did not keep" in result.message
    assert "readback_confirmed" not in " ".join(result.evidence)


def test_typing_never_uses_the_mouse() -> None:
    surface = FakeSurface([FakeElement(pattern=False, keeps_text=False)])
    target = TEXT_TARGET

    adapter(surface, target=target).perform(
        step(StepKind.TYPE_TEXT, target=target),
        chosen(surface, step(StepKind.TYPE_TEXT, target=target)),
    )

    assert surface.clicks == []


# ----------------------------------------------------------------- shortcut


def test_a_shortcut_only_reaches_a_window_that_is_in_front() -> None:
    surface = FakeSurface(in_front=False, focus_works=False)
    target = SHORTCUT_TARGET

    result = adapter(surface, target=target).perform(
        step(StepKind.PRESS_SHORTCUT, target=target),
        chosen(surface, step(StepKind.PRESS_SHORTCUT, target=target)),
    )

    assert result.status is StepStatus.FAILED
    assert surface.keys == []
    assert "sent no keys" in result.message


def test_a_shortcut_on_the_allowlist_is_sent_once_the_window_is_in_front() -> None:
    surface = FakeSurface(in_front=False, focus_works=True)
    target = SHORTCUT_TARGET

    result = adapter(surface, target=target).perform(
        step(StepKind.PRESS_SHORTCUT, target=target),
        chosen(surface, step(StepKind.PRESS_SHORTCUT, target=target)),
    )

    assert result.status is StepStatus.SUCCEEDED
    assert surface.keys == [(surface.window(), "^s")]
    assert "keys=^s" in result.evidence


def test_a_shortcut_outside_the_allowlist_sends_nothing() -> None:
    surface = FakeSurface()
    target = json.dumps({"window": WINDOW, "keys": "ctrl+shift+escape"})

    result = adapter(surface, target=target).perform(
        step(StepKind.PRESS_SHORTCUT, target=target),
        chosen(surface, step(StepKind.PRESS_SHORTCUT, target=target)),
    )

    assert result.status is StepStatus.FAILED
    assert "allowlist" in result.message
    assert surface.keys == []


# ------------------------------------------------------------- end to end


def test_a_captured_descriptor_drives_the_flag_gated_layer_to_a_click() -> None:
    surface = FakeSurface()
    descriptor = descriptor_from_element(FakeInfo(), process="Once demo")
    assert descriptor is not None
    click_step = step(
        descriptor=descriptor,
        expected=ExpectedOutcome(ExpectedKind.TEXT_APPEARS, "Once demo"),
        safety=SafetyClass.REVERSIBLE,
    )
    clock = FakeClock()
    replay = SmartReplay(
        adapter(surface, clock=clock),
        SmartReplayOptions(enabled=True),
        sleep=clock.sleep,
        clock=clock,
    )

    result = replay.run_step(click_step, lambda: False)

    assert result.status is StepStatus.SUCCEEDED, result.message
    assert len(surface.invoked) == 1
    assert result.resolution is not None
    assert "AUTOMATION_ID" in result.resolution.strategy


@pytest.mark.skipif(
    os.environ.get("ONCE_REAL_DESKTOP", "") != "1",
    reason="needs a real desktop: set ONCE_REAL_DESKTOP=1 to run against a live window",
)
def test_a_real_window_offers_candidates_and_refuses_an_unknown_target() -> None:
    """Opt-in smoke test: the real surface either finds candidates or refuses."""
    from integrations.uia_adapter import PywinautoSurface

    surface = PywinautoSurface(json.dumps({"window": {"title": "Once"}}))
    adapter_real = UiaTargetAdapter(surface, CLICK_TARGET, sleep=lambda _: None)

    candidates = adapter_real.candidates(step())

    assert isinstance(candidates, tuple)
