"""Tests for policy-gated read-only replay."""

from __future__ import annotations

import pytest

from controller.service import WorkflowService
from engine.errors import ExecutionError, WorkflowValidationError
from engine.replay import ReplayExecutor
from engine.workflow import (
    StepKind,
    StepStatus,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)
from integrations.windows_automation import PywinautoWindowInspector


def test_replay_dry_run_does_not_read_or_modify_target(tmp_path) -> None:
    target = tmp_path / "result.txt"
    workflow = Workflow(
        "verify",
        "Verify",
        (WorkflowStep("check", "Check", StepKind.VERIFY_PATH_EXISTS, "Check", str(target)),),
    )

    run = ReplayExecutor().execute(workflow, allowed_root=tmp_path, dry_run=True)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].status is StepStatus.SUCCEEDED
    assert "Dry run" in run.results[0].message
    assert not target.exists()


def test_replay_executes_read_only_path_verification(tmp_path) -> None:
    target = tmp_path / "result.txt"
    target.write_bytes(b"result")
    workflow = Workflow(
        "verify",
        "Verify",
        (WorkflowStep("check", "Check", StepKind.VERIFY_PATH_EXISTS, "Check", str(target)),),
    )

    run = ReplayExecutor().execute(workflow, allowed_root=tmp_path)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].status is StepStatus.VERIFIED


def test_replay_rejects_unallowlisted_actions() -> None:
    workflow = Workflow(
        "report",
        "Report",
        (WorkflowStep("report", "Report", StepKind.REPORT, "Not replayable"),),
    )

    with pytest.raises(ExecutionError, match="does not allow"):
        ReplayExecutor().validate(workflow)


def test_replay_preview_marks_unsupported_steps_without_executing() -> None:
    workflow = Workflow(
        "mixed",
        "Mixed",
        (
            WorkflowStep("check", "Check", StepKind.VERIFY_PATH_EXISTS, "Check", "C:\\missing"),
            WorkflowStep("report", "Report", StepKind.REPORT, "Unsupported"),
        ),
    )

    preview = ReplayExecutor().preview(workflow)

    assert preview.executable is False
    assert "permission=ALLOWED" in preview.steps[0]
    assert "permission=UNSUPPORTED" in preview.steps[1]


def test_replay_policy_rejects_unsupported_execution() -> None:
    workflow = Workflow(
        "report",
        "Report",
        (WorkflowStep("report", "Report", StepKind.REPORT, "Unsupported"),),
    )

    with pytest.raises(ExecutionError, match="does not allow"):
        ReplayExecutor().execute(workflow, allowed_root=None)


def test_controller_replay_persists_progress_and_cancellation(tmp_path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    workflow = Workflow(
        "cancelled-replay",
        "Cancelled replay",
        (
            WorkflowStep("first", "First", StepKind.VERIFY_PATH_EXISTS, "First", str(first)),
            WorkflowStep("second", "Second", StepKind.VERIFY_PATH_EXISTS, "Second", str(second)),
        ),
    )
    service = WorkflowService.for_app_data(tmp_path / "app-data")
    checks = iter((False, True))
    progress = []

    run = service.run_replay(
        workflow,
        allowed_root=tmp_path,
        cancel_check=lambda: next(checks),
        progress_callback=progress.append,
    )

    assert run.status is WorkflowStatus.CANCELLED
    assert [result.step_id for result in progress] == ["first"]
    assert service.history()[0].status is WorkflowStatus.CANCELLED
    service.close()


class FakeInfo:
    name = "Once fixture"
    process_id = 1234
    class_name = "FixtureWindow"
    automation_id = "root"
    control_type = "Window"


class FakeWindow:
    element_info = FakeInfo()

    def __init__(self, descendants=()) -> None:
        self._descendants = descendants

    def descendants(self):
        return self._descendants


class FakeElementInfo:
    automation_id = "save"
    control_type = "Button"
    class_name = "Button"


class FakeElement:
    element_info = FakeElementInfo()

    def is_enabled(self):
        return True


class FakeDesktop:
    def __init__(self, windows) -> None:
        self._windows = windows

    def windows(self):
        return self._windows


def test_windows_inspector_resolves_exact_identity_without_focus() -> None:
    inspector = PywinautoWindowInspector(lambda: FakeDesktop([FakeWindow()]))

    evidence = inspector.inspect(
        '{"title":"Once fixture","process_id":1234,"class_name":"FixtureWindow"}'
    )

    assert evidence == (
        "title=Once fixture",
        "process_id=1234",
        "class_name=FixtureWindow",
        "control_type=Window",
    )


def test_windows_inspector_rejects_ambiguous_identity() -> None:
    inspector = PywinautoWindowInspector(lambda: FakeDesktop([FakeWindow(), FakeWindow()]))

    with pytest.raises(ExecutionError, match="ambiguous"):
        inspector.inspect('{"title":"Once fixture"}')


def test_window_action_is_policy_allowed_and_has_no_fallback() -> None:
    workflow = Workflow(
        "window",
        "Window",
        (
            WorkflowStep(
                "inspect",
                "Inspect",
                StepKind.INSPECT_WINDOW,
                "Window found.",
                '{"title":"Once fixture"}',
            ),
        ),
    )
    service = WorkflowService(window_inspector=lambda _target: ("title=Once fixture",))

    run = service.run_replay(workflow, allowed_root=None)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].status is StepStatus.VERIFIED
    assert run.results[0].evidence == ("title=Once fixture",)


def element_target() -> str:
    return (
        '{"window":{"title":"Once fixture","process_id":1234},'
        '"element":{"automation_id":"save","control_type":"Button"}}'
    )


def test_windows_inspector_finds_one_element_without_reading_text() -> None:
    inspector = PywinautoWindowInspector(lambda: FakeDesktop([FakeWindow((FakeElement(),))]))

    evidence = inspector.inspect_element(element_target())

    assert evidence == (
        "automation_id=save",
        "control_type=Button",
        "class_name=Button",
        "enabled=True",
    )


def test_windows_inspector_rejects_missing_or_ambiguous_elements() -> None:
    target = element_target()
    missing = PywinautoWindowInspector(lambda: FakeDesktop([FakeWindow()]))
    ambiguous = PywinautoWindowInspector(
        lambda: FakeDesktop([FakeWindow((FakeElement(), FakeElement()))])
    )

    with pytest.raises(ExecutionError, match="element was not found"):
        missing.inspect_element(target)
    with pytest.raises(ExecutionError, match="element is ambiguous"):
        ambiguous.inspect_element(target)


def test_ui_element_target_requires_stable_selector() -> None:
    workflow = Workflow(
        "element",
        "Element inspection",
        (
            WorkflowStep(
                "inspect",
                "Inspect",
                StepKind.INSPECT_UI_ELEMENT,
                "Element found.",
                '{"window":{"title":"Once fixture"},"element":{"control_type":"Button"}}',
            ),
        ),
    )

    with pytest.raises(WorkflowValidationError, match="AutomationId"):
        ReplayExecutor().validate(workflow)


def test_ui_element_action_is_policy_allowed_and_persisted(tmp_path) -> None:
    workflow = Workflow(
        "element",
        "Element inspection",
        (
            WorkflowStep(
                "inspect",
                "Inspect",
                StepKind.INSPECT_UI_ELEMENT,
                "Element found.",
                element_target(),
            ),
        ),
    )
    service = WorkflowService.for_app_data(tmp_path / "app-data")
    run = service.run_replay(workflow, allowed_root=None)

    assert run.status is WorkflowStatus.FAILED
    assert run.results[0].status is StepStatus.FAILED
    assert service.history()[0].results[0].status is StepStatus.FAILED
    service.close()


def test_injected_ui_element_inspector_executes_through_controller() -> None:
    workflow = Workflow(
        "element",
        "Element inspection",
        (
            WorkflowStep(
                "inspect",
                "Inspect",
                StepKind.INSPECT_UI_ELEMENT,
                "Element found.",
                element_target(),
            ),
        ),
    )
    service = WorkflowService(ui_element_inspector=lambda _target: ("enabled=True",))

    run = service.run_replay(workflow, allowed_root=None)

    assert run.status is WorkflowStatus.SUCCEEDED
    assert run.results[0].evidence == ("enabled=True",)
