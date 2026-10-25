"""Controller-level tests for desktop approval gating and persistence."""

from __future__ import annotations

import json

import pytest

from controller.service import WorkflowService
from engine.desktop import DesktopApproval, approve_desktop_workflow
from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, StepStatus, Workflow, WorkflowStep
from storage.history import ExecutionHistory
from storage.database import connect
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
    with pytest.raises(Exception):
        service.run_desktop_approved(forged)
