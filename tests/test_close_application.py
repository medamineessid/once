"""Lane B follow-up: closing an application the run itself launched.

Chrome became closable in three places: the close step's allow-list, the
recorded-process mapping used by the AI recorder, and the Windows adapter.
The close is registry-directed and matches only the exact process id this run
launched, never a window title or an image name.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.provider import PROCESS_TO_APPLICATION
from engine.desktop import (
    ReplayExecutor,
    approve_desktop_workflow,
    mutating_kind_names,
)
from engine.errors import ExecutionError, WorkflowValidationError
from engine.replay import READ_ONLY_POLICY
from engine.workflow import (
    StepKind,
    StepResult,
    StepStatus,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)
from integrations.windows_desktop import PywinautoDesktopActions

CHROME_CLOSE = json.dumps({"application": "chrome"})


# --------------------------------------------------------------------- engine


def test_close_validation_accepts_chrome() -> None:
    step = WorkflowStep(
        "c1", "Close chrome", StepKind.CLOSE_APPLICATION, "Close chrome.", target=CHROME_CLOSE
    )
    WorkflowRunner.validate(Workflow("w", "w", (step,)))


def test_close_validation_refuses_an_unlisted_application() -> None:
    step = WorkflowStep(
        "c1",
        "Close cmd",
        StepKind.CLOSE_APPLICATION,
        "Close cmd.",
        target=json.dumps({"application": "cmd"}),
    )
    with pytest.raises(WorkflowValidationError, match="registry does not allow"):
        WorkflowRunner.validate(Workflow("w", "w", (step,)))


def test_close_validation_refuses_an_executable_target() -> None:
    """Closing is by allow-listed name only, so it can never target a path."""
    step = WorkflowStep(
        "c1",
        "Close chrome",
        StepKind.CLOSE_APPLICATION,
        "Close chrome.",
        target=json.dumps({"executable": r"C:\Program Files\Google\Chrome\chrome.exe"}),
    )
    with pytest.raises(WorkflowValidationError, match="unknown close fields"):
        WorkflowRunner.validate(Workflow("w", "w", (step,)))


def test_close_is_a_mutating_step_behind_the_approval_gate() -> None:
    step = WorkflowStep(
        "c1", "Close chrome", StepKind.CLOSE_APPLICATION, "Close chrome.", target=CHROME_CLOSE
    )
    workflow = Workflow("w", "w", (step,))

    with pytest.raises(ExecutionError, match="does not allow"):
        ReplayExecutor(READ_ONLY_POLICY).validate(workflow)

    approval = approve_desktop_workflow(workflow)
    assert StepKind.CLOSE_APPLICATION.value in mutating_kind_names(approval.workflow)


class RecordedActions:
    """Deterministic provider that records the validated targets it receives."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def _ok(self, message: str) -> StepResult:
        return StepResult(step_id="", status=StepStatus.SUCCEEDED, message=message)

    def launch_application(self, target_json: str) -> StepResult:
        self.calls.append(("LAUNCH_APPLICATION", json.loads(target_json)))
        return self._ok("The application was launched.")

    def close_application(self, target_json: str) -> StepResult:
        self.calls.append(("CLOSE_APPLICATION", json.loads(target_json)))
        return self._ok("The application windows were closed.")

    def wait_window(self, target_json: str, timeout_seconds: float) -> StepResult:
        raise AssertionError("this workflow has no wait step")

    def click_element(self, target_json: str) -> StepResult:
        raise AssertionError("this workflow has no click step")

    def type_text(self, target_json: str) -> StepResult:
        raise AssertionError("this workflow has no typing step")

    def press_shortcut(self, target_json: str) -> StepResult:
        raise AssertionError("this workflow has no shortcut step")


def test_launch_then_close_chrome_runs_through_the_provider() -> None:
    launch = WorkflowStep(
        "l1",
        "Launch chrome",
        StepKind.LAUNCH_APPLICATION,
        "Launch chrome.",
        target=CHROME_CLOSE,
    )
    close = WorkflowStep(
        "c1", "Close chrome", StepKind.CLOSE_APPLICATION, "Close chrome.", target=CHROME_CLOSE
    )
    actions = RecordedActions()

    run = WorkflowRunner().run(
        Workflow("w", "w", (launch, close)), allowed_root=None, desktop_actions=actions
    )

    assert tuple(result.status for result in run.results) == (
        StepStatus.SUCCEEDED,
        StepStatus.SUCCEEDED,
    )
    assert tuple(kind for kind, _target in actions.calls) == (
        "LAUNCH_APPLICATION",
        "CLOSE_APPLICATION",
    )
    assert [target for _kind, target in actions.calls] == [
        {"application": "chrome"},
        {"application": "chrome"},
    ]


# ------------------------------------------------------------------- recorder


def test_recorded_chrome_process_maps_to_the_chrome_application() -> None:
    assert PROCESS_TO_APPLICATION["chrome.exe"] == "chrome"


# -------------------------------------------------------------------- adapter


class FakeElementInfo:
    def __init__(self, name: str, process_id: int) -> None:
        self.name = name
        self.class_name = "Chrome_WidgetWin_1"
        self.automation_id = ""
        self.control_type = "Window"
        self.process_id = process_id
        self.handle = process_id
        self.is_password = False


class FakeWindow:
    def __init__(self, info: FakeElementInfo) -> None:
        self.element_info = info
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeDesktop:
    def __init__(self, windows: list[FakeWindow]) -> None:
        self._windows = windows

    def windows(self) -> list[FakeWindow]:
        return [window for window in self._windows if not window.closed]


class FakeProcess:
    pid = 4242


def process_with_pid(pid: int) -> FakeProcess:
    """One fake process whose pid the adapter records for that launch."""
    process = FakeProcess()
    process.pid = pid
    return process


def chrome_provider(windows: list[FakeWindow]) -> tuple[PywinautoDesktopActions, list[list[str]]]:
    """Provider bound to one fake desktop surface, launching a stubbed chrome.exe."""
    desktop = FakeDesktop(windows)
    launched: list[list[str]] = []

    def fake_popen(argv: list[str]) -> FakeProcess:
        launched.append(argv)
        return FakeProcess()

    provider = PywinautoDesktopActions(
        desktop_factory=lambda: desktop,
        popen=fake_popen,
        sleep=lambda _seconds: None,
    )
    return provider, launched


def test_chrome_launch_uses_an_isolated_profile_and_its_own_executable(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"")
    provider = PywinautoDesktopActions(
        desktop_factory=lambda: FakeDesktop([]),
        popen=lambda argv: FakeProcess(),
    )

    result = provider.launch_application(json.dumps({"executable": str(executable)}))

    assert result.status is StepStatus.SUCCEEDED
    assert "isolated_profile=true" in result.evidence
    assert any(item.startswith("chrome_profile=") for item in result.evidence)


def test_close_touches_only_the_launched_process_id() -> None:
    own = FakeWindow(FakeElementInfo("Chrome — Once", FakeProcess.pid))
    foreign = FakeWindow(FakeElementInfo("Chrome — my own browsing", 99))
    provider, _launched = chrome_provider([own, foreign])

    launched = provider.launch_application(json.dumps({"application": "chrome"}))
    assert launched.status is StepStatus.SUCCEEDED

    result = provider.close_application(CHROME_CLOSE)

    assert result.status is StepStatus.SUCCEEDED
    assert own.closed is True
    assert foreign.closed is False, "a same-named window of another process must be left alone"
    assert f"process_id={FakeProcess.pid}" in result.evidence
    assert "windows_closed=1" in result.evidence


def test_close_refuses_an_application_this_run_did_not_launch() -> None:
    own = FakeWindow(FakeElementInfo("Chrome", FakeProcess.pid))
    provider, launched = chrome_provider([own])

    result = provider.close_application(CHROME_CLOSE)

    assert result.status is StepStatus.FAILED
    assert "did not launch" in result.message
    assert "registered=false" in result.evidence
    assert own.closed is False
    assert launched == []


def test_close_reports_when_the_window_never_disappears() -> None:
    class StickyWindow(FakeWindow):
        def close(self) -> None:
            return None

    sticky = StickyWindow(FakeElementInfo("Chrome", FakeProcess.pid))
    ticks = iter(range(1, 200))
    desktop = FakeDesktop([sticky])
    provider = PywinautoDesktopActions(
        desktop_factory=lambda: desktop,
        popen=lambda argv: FakeProcess(),
        sleep=lambda _seconds: None,
        clock=lambda: float(next(ticks)),
    )
    provider.launch_application(json.dumps({"application": "chrome"}))

    result = provider.close_application(CHROME_CLOSE)

    assert result.status is StepStatus.FAILED
    assert "did not close" in result.message


def test_close_reports_a_window_that_raises_on_close() -> None:
    class BrokenWindow(FakeWindow):
        def close(self) -> None:
            raise RuntimeError("the surface refused")

    provider, _launched = chrome_provider([BrokenWindow(FakeElementInfo("Chrome", 4242))])
    provider.launch_application(json.dumps({"application": "chrome"}))

    result = provider.close_application(CHROME_CLOSE)

    assert result.status is StepStatus.FAILED
    assert "the surface refused" in result.message


def test_launching_a_second_process_replaces_the_registered_pid() -> None:
    """The registered pid is the newest launch, so close never guesses."""
    first = FakeWindow(FakeElementInfo("Chrome one", 1111))
    second = FakeWindow(FakeElementInfo("Chrome two", 2222))
    pids = iter((1111, 2222))
    provider = PywinautoDesktopActions(
        desktop_factory=lambda: FakeDesktop([first, second]),
        popen=lambda argv: process_with_pid(next(pids)),
        sleep=lambda _seconds: None,
    )

    provider.launch_application(json.dumps({"application": "chrome"}))
    assert provider.close_application(CHROME_CLOSE).status is StepStatus.SUCCEEDED
    provider.launch_application(json.dumps({"application": "chrome"}))

    assert first.closed is True
    assert second.closed is False
