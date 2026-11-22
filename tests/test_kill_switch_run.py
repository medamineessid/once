"""A kill-switch request during a long step must end the run as cancelled."""

from __future__ import annotations

import json
import sys

from engine.desktop import approve_desktop_workflow
from engine.workflow import StepKind, Workflow, WorkflowRunner, WorkflowStep


class FakeDesktop:
    triggered = False

    def __init__(self) -> None:
        self.launched = False

    def launch_application(self, _target: str):
        self.launched = True
        from engine.workflow import StepResult, StepStatus

        return StepResult("", StepStatus.SUCCEEDED, "launched")

    def wait_window(self, _target: str, _timeout: float):
        from engine.workflow import StepResult, StepStatus

        self.triggered = True
        return StepResult("", StepStatus.FAILED, "The wait was interrupted.")

    def close_application(self, _target: str):
        raise AssertionError("not reached")


def test_cancel_during_a_wait_returns_cancelled_not_failed() -> None:
    workflow = Workflow(
        "cancel-during-wait",
        "Cancel during wait",
        (
            WorkflowStep(
                "launch",
                "Launch",
                StepKind.LAUNCH_APPLICATION,
                "Launch.",
                target=json.dumps({"executable": sys.executable}),
            ),
            WorkflowStep(
                "wait",
                "Wait",
                StepKind.WAIT_WINDOW,
                "Wait.",
                target=json.dumps({"title": "never"}),
                timeout_seconds=1,
            ),
        ),
    )
    actions = FakeDesktop()
    approval = approve_desktop_workflow(workflow)

    run = WorkflowRunner().run(
        approval.workflow,
        desktop_actions=actions,
        cancel_check=lambda: actions.triggered,
    )

    assert run.status.value == "CANCELLED"
    assert run.results[0].status.value == "SUCCEEDED"
    assert run.results[1].status.value == "FAILED"
