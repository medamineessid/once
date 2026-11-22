"""A failed or cancelled desktop run closes only the apps it launched."""

from __future__ import annotations

import json
import sys

from controller.service import WorkflowService
from engine.desktop import approve_desktop_workflow
from engine.workflow import StepKind, StepResult, StepStatus, Workflow, WorkflowStep


class CleanupActions:
    """Minimal desktop provider that records cleanup calls."""

    def __init__(self, script: dict[str, object] | None = None) -> None:
        self.scripted = script or {}
        self.cleanup_calls = 0

    def _result(self, kind: str, fallback: str) -> StepResult:
        status, message, evidence = self.scripted.get(kind, (StepStatus.SUCCEEDED, fallback, ()))
        return StepResult("", status, message, evidence)

    def launch_application(self, _target: str) -> StepResult:
        return self._result("LAUNCH_APPLICATION", "The application was launched.")

    def close_application(self, _target: str) -> StepResult:
        return self._result("CLOSE_APPLICATION", "The application windows were closed.")

    def close_launched_applications(self) -> tuple[str, ...]:
        self.cleanup_calls += 1
        return ("The application windows were closed.",)


class StubKillSwitch:
    triggered = False

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


def _approval():
    workflow = Workflow(
        "cleanup",
        "Cleanup",
        (
            WorkflowStep(
                "launch",
                "Launch",
                StepKind.LAUNCH_APPLICATION,
                "Launch.",
                target=json.dumps({"executable": sys.executable}),
            ),
            WorkflowStep(
                "close",
                "Close",
                StepKind.CLOSE_APPLICATION,
                "Close.",
                target=json.dumps({"executable": sys.executable}),
            ),
        ),
    )
    return approve_desktop_workflow(workflow)


def test_failed_run_closes_launched_applications() -> None:
    actions = CleanupActions(
        {
            "LAUNCH_APPLICATION": (
                StepStatus.SUCCEEDED,
                "The application was launched.",
                (),
            ),
            "CLOSE_APPLICATION": (
                StepStatus.FAILED,
                "The application did not close.",
                (),
            ),
        }
    )
    service = WorkflowService(desktop_actions=actions, kill_switch=StubKillSwitch())

    run = service.run_desktop_approved(_approval())

    assert run.status.value == "FAILED"
    assert actions.cleanup_calls == 1


def test_cancelled_run_closes_launched_applications() -> None:
    actions = CleanupActions()
    service = WorkflowService(desktop_actions=actions, kill_switch=StubKillSwitch())

    run = service.run_desktop_approved(_approval(), cancel_check=lambda: True)

    assert run.status.value == "CANCELLED"
    assert actions.cleanup_calls == 1


def test_successful_run_does_not_force_cleanup() -> None:
    actions = CleanupActions()

    def launch(_target: str) -> StepResult:
        return StepResult("", StepStatus.SUCCEEDED, "The application was launched.")

    def close(_target: str) -> StepResult:
        return StepResult("", StepStatus.SUCCEEDED, "The application windows were closed.")

    actions.launch_application = launch  # type: ignore[method-assign]
    actions.close_application = close  # type: ignore[method-assign]
    service = WorkflowService(desktop_actions=actions, kill_switch=StubKillSwitch())

    run = service.run_desktop_approved(_approval())

    assert run.status.value == "SUCCEEDED"
    assert actions.cleanup_calls == 0
