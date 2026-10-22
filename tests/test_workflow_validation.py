"""Validation tests for workflow lifecycle inputs."""

from __future__ import annotations

import pytest

from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowRunner, WorkflowStep


def workflow_with(step: WorkflowStep) -> Workflow:
    return Workflow("workflow", "Workflow", (step,))


def test_runner_rejects_duplicate_step_ids_before_execution() -> None:
    workflow = Workflow(
        "workflow",
        "Workflow",
        (
            WorkflowStep("same", "One", StepKind.REPORT, "one"),
            WorkflowStep("same", "Two", StepKind.REPORT, "two"),
        ),
    )

    with pytest.raises(WorkflowValidationError, match="duplicated"):
        WorkflowRunner().run(workflow)


@pytest.mark.parametrize(
    ("workflow", "message"),
    [
        (Workflow("", "Workflow", ()), "Workflow ID"),
        (Workflow("workflow", "", ()), "Workflow name"),
        (workflow_with(WorkflowStep("", "Step", StepKind.REPORT, "")), "needs an ID"),
        (workflow_with(WorkflowStep("step", "", StepKind.REPORT, "")), "needs a name"),
    ],
)
def test_runner_rejects_missing_required_values(workflow: Workflow, message: str) -> None:
    with pytest.raises(WorkflowValidationError, match=message):
        WorkflowRunner().run(workflow)
