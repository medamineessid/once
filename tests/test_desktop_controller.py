"""Controller-level tests for desktop approval gating and persistence."""

from __future__ import annotations

import json

import pytest

from controller.service import WorkflowService
from engine.desktop import DesktopApproval, approve_desktop_workflow
from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, StepStatus, Workflow, WorkflowStep
from storage.database import connect
from storage.history import ExecutionHistory
from tests.test_desktop_engine import FakeDesktopActions

WINDOW = {"title": "Once demo", "class_name": "DemoWindowClass"}
TYPE_TARGET = {
    "window": WINDOW,
    "element": {"class_name": "DemoEditClass", "control_type": "Edit"},
    "text": "hello once",
}


def make_service(tmp_path, actions) -> WorkflowService:
    return WorkflowService(
        history=ExecutionHistory(connect(tmp_path / "history.db")),
        workflow_directory=tmp_path / "workflows",
        desktop_actions=actions,
        window_inspector=lambda target_json: ("title=demo",),
        ui_element_inspector=lambda target_json: ("automation_id=x",),
    )


def typed_workflow() -> Workflow:
    step = WorkflowStep(
        "type",
        "Type",
        StepKind.TYPE_TEXT,
        "Text entered.",
        target=json.dumps(TYPE_TARGET),
    )
    return Workflow("desktop-flow", "Desktop flow", (step,))


def test_mutating_desktop_workflow_cannot_run_as_an_ordinary_replay(tmp_path) -> None:
    """The default replay path must never execute desktop mutations."""
    service = make_service(tmp_path, FakeDesktopActions())
    preview = service.preview_replay(typed_workflow())
    assert preview.executable is False


class FakeBrowserProvider:
    """Records shutdown calls like the real isolated-Chrome provider would."""

    def __init__(self) -> None:
        self.shutdown_calls = 0
        self.launch_calls = 0

    def launch_browser(self, target_json: str):
        from engine.workflow import StepResult

        self.launch_calls += 1
        return StepResult(
            step_id="", status=StepStatus.SUCCEEDED, message="launched"
        )

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def make_browser_service(tmp_path, browser_actions) -> WorkflowService:
    return WorkflowService(
        history=ExecutionHistory(connect(tmp_path / "history.db")),
        workflow_directory=tmp_path / "workflows",
        desktop_actions=FakeDesktopActions(),
        browser_actions=browser_actions,
        window_inspector=lambda target_json: ("title=demo",),
        ui_element_inspector=lambda target_json: ("automation_id=x",),
    )


def launch_workflow() -> Workflow:
    launch = WorkflowStep(
        "launch",
        "Launch",
        StepKind.LAUNCH_BROWSER,
        "An isolated browser is running.",
        target=json.dumps({"application": "chrome"}),
    )
    return Workflow("browser-launch", "Browser launch", (launch,))


def test_browser_is_closed_when_the_approved_run_finishes(tmp_path) -> None:
    browser = FakeBrowserProvider()
    service = make_browser_service(tmp_path, browser)
    approval = approve_desktop_workflow(launch_workflow())
    run = service.run_desktop_approved(approval)
    assert run.status.value == "SUCCEEDED"
    assert browser.launch_calls == 1
    assert browser.shutdown_calls == 1


def test_browser_is_closed_even_when_the_run_fails(tmp_path) -> None:
    browser = FakeBrowserProvider()
    service = make_browser_service(tmp_path, browser)

    class FailingBrowser(FakeBrowserProvider):
        def launch_browser(self, target_json: str):
            from engine.errors import ExecutionError

            raise ExecutionError("The browser could not be launched.")

    failing = FailingBrowser()
    service2 = make_browser_service(tmp_path, failing)
    approval = approve_desktop_workflow(launch_workflow())
    run = service2.run_desktop_approved(approval)
    assert run.status.value == "FAILED"
    assert failing.shutdown_calls == 1
    assert browser.launch_calls == 0  # the unused provider stayed untouched


def test_browser_is_closed_when_the_run_is_cancelled(tmp_path) -> None:
    browser = FakeBrowserProvider()
    service = make_browser_service(tmp_path, browser)
    approval = approve_desktop_workflow(launch_workflow())
    run = service.run_desktop_approved(
        approval, cancel_check=lambda: True  # cancelled before the first step
    )
    assert run.status.value == "CANCELLED"
    assert browser.launch_calls == 0
    assert browser.shutdown_calls == 1


def test_launch_only_run_may_keep_the_browser_for_a_later_run(tmp_path) -> None:
    """The documented two-run pattern: launch run keeps the browser open."""
    browser = FakeBrowserProvider()
    service = make_browser_service(tmp_path, browser)
    approval = approve_desktop_workflow(launch_workflow())
    service.run_desktop_approved(approval, keep_browsers_after_run=True)
    assert browser.shutdown_calls == 0
    # the consuming run closes it when it finishes
    service.run_desktop_approved(approval, keep_browsers_after_run=False)
    assert browser.shutdown_calls == 1


def test_close_browser_sessions_is_a_safe_public_cleanup(tmp_path) -> None:
    from controller import service as service_module

    registered: list[object] = []
    original_register = service_module.atexit.register

    def recording_register(function):
        registered.append(function)

    service_module.atexit.register = recording_register
    try:
        service = make_service(tmp_path, FakeDesktopActions())
    finally:
        service_module.atexit.register = original_register
    assert len(registered) == 1
    # calling the exit hook is idempotent and safe with a provider without shutdown
    service.close_browser_sessions()
    service.close_browser_sessions()

    class NoShutdownProvider:
        pass

    bare = WorkflowService(
        history=ExecutionHistory(connect(tmp_path / "history.db")),
        workflow_directory=tmp_path / "workflows",
        desktop_actions=FakeDesktopActions(),
        browser_actions=NoShutdownProvider(),
        window_inspector=lambda target_json: (),
        ui_element_inspector=lambda target_json: (),
    )
    bare.close_browser_sessions()  # no AttributeError



def test_desktop_preview_allows_for_the_desktop_policy(tmp_path) -> None:
    service = make_service(tmp_path, FakeDesktopActions())
    preview = service.preview_desktop_replay(typed_workflow())
    assert preview.executable is True


def test_run_desktop_approved_persists_a_succeeded_run(tmp_path) -> None:
    actions = FakeDesktopActions()
    service = make_service(tmp_path, actions)
    approval = approve_desktop_workflow(typed_workflow())
    run = service.run_desktop_approved(approval)
    assert run.status.value == "SUCCEEDED"
    assert run.results[0].status is StepStatus.SUCCEEDED
    assert ("TYPE_TEXT", json.dumps(TYPE_TARGET)) in actions.calls
    assert service.history()[0].workflow_id == "desktop-flow"


def test_run_desktop_approved_refuses_unapproved_workflows(tmp_path) -> None:
    """A bare workflow (even valid) is not an approval; execution is refused."""
    service = make_service(tmp_path, FakeDesktopActions())
    with pytest.raises(WorkflowValidationError, match="desktop approval gate"):
        service.run_desktop_approved(typed_workflow())


def test_run_desktop_approved_refuses_a_forged_approval(tmp_path) -> None:
    """Only a real DesktopApproval passes the gate; fakes of the same shape do not."""

    class ForgedApproval:
        def __init__(self, workflow: Workflow) -> None:
            self.workflow = workflow
            self.approved_at = None

    service = make_service(tmp_path, FakeDesktopActions())
    with pytest.raises(WorkflowValidationError, match="desktop approval gate"):
        service.run_desktop_approved(ForgedApproval(typed_workflow()))


def test_run_desktop_approved_records_failures_in_history(tmp_path) -> None:
    actions = FakeDesktopActions(
        script={"TYPE_TEXT": (StepStatus.FAILED, "The element is disabled.", ())}
    )
    service = make_service(tmp_path, actions)
    approval = approve_desktop_workflow(typed_workflow())
    run = service.run_desktop_approved(approval)
    assert run.status.value == "FAILED"
    recorded = service.history()[0]
    assert recorded.workflow_id == "desktop-flow"


def test_desktop_approval_object_is_not_constructible_outside_the_gate(tmp_path) -> None:
    """A hand-made DesktopApproval still fails the runtime policy re-validation."""
    actions = FakeDesktopActions()
    service = make_service(tmp_path, actions)
    # An invalid workflow inside a hand-built approval must fail closed.
    bad_step = WorkflowStep(
        "press",
        "Press",
        StepKind.PRESS_SHORTCUT,
        "Sent.",
        target=json.dumps({"window": WINDOW, "keys": "ctrl+unlisted"}),
    )
    forged = DesktopApproval(Workflow("bad", "bad", (bad_step,)), None)  # type: ignore[arg-type]
    with pytest.raises(WorkflowValidationError):
        service.run_desktop_approved(forged)
