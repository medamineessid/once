"""Deterministic orchestration of declarative workflow steps."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4


class StepKind(StrEnum):
    """Built-in step behaviours available without external integrations."""

    REPORT = "REPORT"
    FAIL = "FAIL"


class StepStatus(StrEnum):
    """Lifecycle state of one workflow step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WorkflowStatus(StrEnum):
    """Lifecycle state of a workflow run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class WorkflowStep:
    """A bounded, declarative step with no executable user-supplied code."""

    step_id: str
    name: str
    kind: StepKind
    message: str


@dataclass(frozen=True)
class Workflow:
    """A named, ordered workflow definition."""

    workflow_id: str
    name: str
    steps: tuple[WorkflowStep, ...]


@dataclass(frozen=True)
class StepResult:
    """The observable result of one step."""

    step_id: str
    status: StepStatus
    message: str


@dataclass(frozen=True)
class WorkflowRun:
    """A complete immutable snapshot of workflow execution state."""

    run_id: str
    workflow_id: str
    status: WorkflowStatus
    results: tuple[StepResult, ...]


CancelCheck = Callable[[], bool]


class WorkflowRunner:
    """Execute known step kinds in order and retain an inspectable run result."""

    def run(
        self,
        workflow: Workflow,
        *,
        cancel_check: CancelCheck | None = None,
        run_id: str | None = None,
    ) -> WorkflowRun:
        """Run a workflow until completion, failure, or cancellation."""
        results: list[StepResult] = []
        is_cancelled = cancel_check or (lambda: False)

        for index, step in enumerate(workflow.steps):
            if is_cancelled():
                results.extend(
                    StepResult(
                        step_id=remaining.step_id,
                        status=StepStatus.SKIPPED,
                        message="Skipped because the workflow was cancelled.",
                    )
                    for remaining in workflow.steps[index:]
                )
                return WorkflowRun(
                    run_id=run_id or str(uuid4()),
                    workflow_id=workflow.workflow_id,
                    status=WorkflowStatus.CANCELLED,
                    results=tuple(results),
                )

            results.append(
                StepResult(
                    step_id=step.step_id,
                    status=StepStatus.RUNNING,
                    message=f"Running: {step.name}",
                )
            )
            if step.kind is StepKind.FAIL:
                results[-1] = StepResult(
                    step_id=step.step_id,
                    status=StepStatus.FAILED,
                    message=step.message,
                )
                results.extend(
                    StepResult(
                        step_id=remaining.step_id,
                        status=StepStatus.SKIPPED,
                        message="Skipped because an earlier step failed.",
                    )
                    for remaining in workflow.steps[index + 1 :]
                )
                return WorkflowRun(
                    run_id=run_id or str(uuid4()),
                    workflow_id=workflow.workflow_id,
                    status=WorkflowStatus.FAILED,
                    results=tuple(results),
                )

            results[-1] = StepResult(
                step_id=step.step_id,
                status=StepStatus.SUCCEEDED,
                message=step.message,
            )

        return WorkflowRun(
            run_id=run_id or str(uuid4()),
            workflow_id=workflow.workflow_id,
            status=WorkflowStatus.SUCCEEDED,
            results=tuple(results),
        )
