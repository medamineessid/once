"""Lane B follow-up: closing an application the run itself launched.

Chrome became closable in three places: the close step's allow-list, the
recorded-process mapping used by the AI recorder, and the Windows adapter.
The close is registry-directed and matches only the exact process id this run
launched, never a window title or an image name.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

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

APP_TARGET = json.dumps({"executable": str(sys.executable)})


CHROME_CLOSE = APP_TARGET
NOTEPAD_CLOSE = APP_TARGET


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
    with pytest.raises(WorkflowValidationError, match="unknown close fields"):
        WorkflowRunner.validate(Workflow("w", "w", (step,)))


def test_close_validation_accepts_the_executable_path_from_a_recording() -> None:
    """Closing targets exactly the executable path the recording captured."""
    step = WorkflowStep(
        "c1",
        "Close the application",
        StepKind.CLOSE_APPLICATION,
        "Close the application.",
        target=json.dumps({"executable": str(Path(sys.executable))}),
    )
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
        {"executable": str(sys.executable)},
        {"executable": str(sys.executable)},
    ]


# ------------------------------------------------------------------- recorder


# -------------------------------------------------------------------- adapter


class FakeElementInfo:
    def __init__(
        self,
        name: str,
        process_id: int,
        *,
        visible: bool = True,
        owner: bool = False,
        handle: int | None = None,
    ) -> None:
        self.name = name
        self.class_name = "Chrome_WidgetWin_1"
        self.automation_id = ""
        self.control_type = "Window"
        self.process_id = process_id
        self.handle = process_id if handle is None else handle
        self.is_password = False
        self.visible = visible
        self.owner = owner


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


def fake_surface(desktop: FakeDesktop, alive: set[int]) -> dict:
    """The injected window/process surface, standing in for Win32 calls."""
    return {
        "desktop_factory": lambda: desktop,
        "is_visible": lambda wrapper: bool(wrapper.element_info.visible),
        "has_owner": lambda wrapper: bool(wrapper.element_info.owner),
        "process_alive": lambda pid: pid in alive,
        "sleep": lambda _seconds: None,
    }


def notepad_provider(
    windows: list[FakeWindow], alive: set[int] | None = None
) -> tuple[PywinautoDesktopActions, list[list[str]]]:
    """Provider bound to one fake desktop surface, launching a stubbed notepad.exe."""
    desktop = FakeDesktop(windows)
    launched: list[list[str]] = []

    def fake_popen(argv: list[str]) -> FakeProcess:
        launched.append(argv)
        return FakeProcess()

    provider = approved_provider(
        **fake_surface(desktop, {FakeProcess.pid} if alive is None else alive),
        popen=fake_popen,
    )
    return provider, launched


def test_close_touches_only_the_launched_process_id() -> None:
    own = FakeWindow(FakeElementInfo("Chrome — Once", FakeProcess.pid))
    foreign = FakeWindow(FakeElementInfo("Chrome — my own browsing", 99))
    provider, _launched = notepad_provider([own, foreign])

    launched = provider.launch_application(APP_TARGET)
    assert launched.status is StepStatus.SUCCEEDED

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.SUCCEEDED
    assert own.closed is True
    assert foreign.closed is False, "a same-named window of another process must be left alone"
    assert f"process_id={FakeProcess.pid}" in result.evidence
    assert "windows_closed=1" in result.evidence


def test_close_refuses_an_application_this_run_did_not_launch() -> None:
    own = FakeWindow(FakeElementInfo("Chrome", FakeProcess.pid))
    provider, launched = notepad_provider([own])

    result = provider.close_application(NOTEPAD_CLOSE)

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
    ticks = iter(range(1, 400))
    desktop = FakeDesktop([sticky])
    provider = approved_provider(
        **fake_surface(desktop, {FakeProcess.pid}),
        popen=lambda argv: FakeProcess(),
        clock=lambda: float(next(ticks)),
    )
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.FAILED
    assert "did not close" in result.message


def test_close_reports_a_window_that_raises_on_close() -> None:
    class BrokenWindow(FakeWindow):
        def close(self) -> None:
            raise RuntimeError("the surface refused")

    provider, _launched = notepad_provider([BrokenWindow(FakeElementInfo("Chrome", 4242))])
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.FAILED
    assert "the surface refused" in result.message


def test_launching_a_second_process_replaces_the_registered_pid() -> None:
    """The registered pid is the newest launch, so close never guesses."""
    first = FakeWindow(FakeElementInfo("Chrome one", 1111))
    second = FakeWindow(FakeElementInfo("Chrome two", 2222))
    pids = iter((1111, 2222))
    provider = approved_provider(
        **fake_surface(FakeDesktop([first, second]), {1111, 2222}),
        popen=lambda argv: process_with_pid(next(pids)),
    )

    provider.launch_application(APP_TARGET)
    assert provider.close_application(NOTEPAD_CLOSE).status is StepStatus.SUCCEEDED
    provider.launch_application(APP_TARGET)

    assert first.closed is True
    assert second.closed is False


class LateDesktop:
    """A desktop surface whose window only exists from the Nth poll onwards."""

    def __init__(self, window: FakeWindow, appear_after: int) -> None:
        self._window = window
        self._appear_after = appear_after
        self.calls = 0

    def windows(self) -> list[FakeWindow]:
        self.calls += 1
        if self._window.closed:
            return []
        return [self._window] if self.calls > self._appear_after else []


def test_close_waits_for_a_window_that_appears_after_the_first_polls() -> None:
    own = FakeWindow(FakeElementInfo("Chrome", FakeProcess.pid))
    desktop = LateDesktop(own, appear_after=2)
    provider = approved_provider(
        **fake_surface(desktop, {FakeProcess.pid}),  # type: ignore[arg-type]
        popen=lambda argv: FakeProcess(),
    )
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert desktop.calls > 2, "close must poll instead of giving up on the first look"
    assert result.status is StepStatus.SUCCEEDED
    assert own.closed is True
    assert "windows_closed=1" in result.evidence


def test_close_ignores_hidden_windows_of_the_launched_process() -> None:
    hidden = FakeWindow(FakeElementInfo("Chrome", FakeProcess.pid, visible=False))
    ticks = iter(range(1, 100))
    provider = approved_provider(
        **fake_surface(FakeDesktop([hidden]), {FakeProcess.pid}),
        popen=lambda argv: FakeProcess(),
        clock=lambda: float(next(ticks)),
    )
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.FAILED
    assert "never appeared" in result.message
    assert "window_appeared=false" in result.evidence
    assert hidden.closed is False


def test_close_closes_the_visible_window_and_leaves_the_hidden_one_alone() -> None:
    hidden = FakeWindow(FakeElementInfo("Chrome", FakeProcess.pid, visible=False, handle=1))
    visible = FakeWindow(FakeElementInfo("Chrome", FakeProcess.pid, handle=2))
    provider, _launched = notepad_provider([hidden, visible])
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.SUCCEEDED
    assert visible.closed is True
    assert hidden.closed is False, "a hidden window is not the application window"
    assert "windows_closed=1" in result.evidence


def test_close_ignores_owned_windows_of_the_launched_process() -> None:
    owned = FakeWindow(FakeElementInfo("Chrome popup", FakeProcess.pid, owner=True))
    ticks = iter(range(1, 100))
    provider = approved_provider(
        **fake_surface(FakeDesktop([owned]), {FakeProcess.pid}),
        popen=lambda argv: FakeProcess(),
        clock=lambda: float(next(ticks)),
    )
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.FAILED
    assert "never appeared" in result.message
    assert owned.closed is False


def test_close_reports_a_process_that_already_exited() -> None:
    provider, _launched = notepad_provider([], alive=set())
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.SUCCEEDED
    assert result.message == "The application had already exited."
    assert "exited=true" in result.evidence
    assert not any(item.startswith("windows_closed=") for item in result.evidence)


def test_close_fails_when_no_window_ever_appears() -> None:
    ticks = iter(range(1, 100))
    provider = approved_provider(
        **fake_surface(FakeDesktop([]), {FakeProcess.pid}),
        popen=lambda argv: FakeProcess(),
        clock=lambda: float(next(ticks)),
    )
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.FAILED, "closing nothing is never a success"
    assert "never appeared" in result.message
    assert "windows_closed=0" in result.evidence


def test_close_reports_success_when_the_process_exits_after_the_request() -> None:
    alive = {FakeProcess.pid}

    class ExitingWindow(FakeWindow):
        def close(self) -> None:
            alive.discard(self.element_info.process_id)
            self.closed = True

    window = ExitingWindow(FakeElementInfo("Chrome", FakeProcess.pid))
    provider = approved_provider(
        **fake_surface(FakeDesktop([window]), alive),
        popen=lambda argv: FakeProcess(),
    )
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.SUCCEEDED
    assert window.closed is True
    assert "windows_closed=1" in result.evidence
    assert "exited=true" in result.evidence


def test_close_reports_the_windows_that_are_still_visible() -> None:
    class StickyWindow(FakeWindow):
        def close(self) -> None:
            return None

    sticky = StickyWindow(FakeElementInfo("Chrome", FakeProcess.pid))
    ticks = iter(range(1, 400))
    provider = approved_provider(
        **fake_surface(FakeDesktop([sticky]), {FakeProcess.pid}),
        popen=lambda argv: FakeProcess(),
        clock=lambda: float(next(ticks)),
    )
    provider.launch_application(APP_TARGET)

    result = provider.close_application(NOTEPAD_CLOSE)

    assert result.status is StepStatus.FAILED
    assert "did not close" in result.message
    assert "visible_windows_remaining=1" in result.evidence


def test_close_fails_closed_when_the_approved_record_forbids_closing() -> None:
    """close_supported comes from the approval record, never from a name in code."""
    own = FakeWindow(FakeElementInfo("Harmless app", FakeProcess.pid))
    desktop = FakeDesktop([own])
    provider = approved_provider(
        **fake_surface(desktop, {FakeProcess.pid}),
        popen=lambda argv: FakeProcess(),
        approvals=FakeApprovals(close_supported=False),
    )
    assert provider.launch_application(APP_TARGET).status is StepStatus.SUCCEEDED

    result = provider.close_application(APP_TARGET)

    assert result.status is StepStatus.FAILED
    assert "cannot close this application" in result.message
    assert "close_supported=false" in result.evidence
    assert own.closed is False, "a fail-closed close must not touch anything"


class FakeApprovals:
    """One approved-application record, standing in for the storage registry."""

    def __init__(
        self,
        *,
        approved: bool = True,
        close_supported: bool = True,
        sha256: str | None = None,
        display_name: str = "Harmless app",
    ) -> None:
        self.approved = approved
        self.close_supported = close_supported
        self.sha256 = sha256
        self.display_name = display_name

    def find(self, executable):
        from engine.workflow import ApprovedApplication

        return ApprovedApplication(
            executable=executable,
            sha256=self.sha256 or hashlib.sha256(executable.read_bytes()).hexdigest(),
            display_name=self.display_name,
            approved=self.approved,
            close_supported=self.close_supported,
        )


def approved_provider(**kwargs):
    """A desktop provider whose approval source is the fake registry above."""
    kwargs.setdefault("approvals", FakeApprovals())
    return PywinautoDesktopActions(**kwargs)
