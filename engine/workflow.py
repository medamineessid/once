"""Deterministic orchestration of declarative workflow steps."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from .errors import WorkflowValidationError

MAX_WORKFLOW_STEPS = 100
MAX_TEXT_LENGTH = 500


class StepKind(StrEnum):
    """Built-in step behaviours available without external integrations."""

    REPORT = "REPORT"
    FAIL = "FAIL"
    INSPECT_PATH = "INSPECT_PATH"
    VERIFY_PATH_EXISTS = "VERIFY_PATH_EXISTS"


class StepStatus(StrEnum):
    """Lifecycle state of one workflow step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    VERIFIED = "VERIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"


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
    target: str | None = None


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
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowRun:
    """A complete immutable snapshot of workflow execution state."""

    run_id: str
    workflow_id: str
    status: WorkflowStatus
    results: tuple[StepResult, ...]
    started_at: datetime
    finished_at: datetime


CancelCheck = Callable[[], bool]


class WorkflowRunner:
    """Execute known step kinds in order and retain an inspectable run result."""

    @staticmethod
    def validate(workflow: Workflow) -> None:
        """Reject malformed definitions before any step can start."""
        if not workflow.workflow_id.strip():
            raise WorkflowValidationError("Workflow ID must not be empty.")
        if not workflow.name.strip():
            raise WorkflowValidationError("Workflow name must not be empty.")
        if len(workflow.steps) > MAX_WORKFLOW_STEPS:
            raise WorkflowValidationError(
                f"Workflow cannot contain more than {MAX_WORKFLOW_STEPS} steps."
            )

        step_ids: set[str] = set()
        for step in workflow.steps:
            if not step.step_id.strip():
                raise WorkflowValidationError("Every workflow step needs an ID.")
            if step.step_id in step_ids:
                raise WorkflowValidationError(f"Step ID is duplicated: {step.step_id}.")
            if not step.name.strip():
                raise WorkflowValidationError(f"Step {step.step_id} needs a name.")
            if not isinstance(step.kind, StepKind):
                raise WorkflowValidationError(f"Step {step.step_id} has an unknown kind.")
            if len(step.name) > MAX_TEXT_LENGTH or len(step.message) > MAX_TEXT_LENGTH:
                raise WorkflowValidationError(
                    f"Step {step.step_id} contains text that is too long."
                )
            if step.kind in (StepKind.INSPECT_PATH, StepKind.VERIFY_PATH_EXISTS) and (
                not step.target or not Path(step.target).is_absolute()
            ):
                raise WorkflowValidationError(f"Step {step.step_id} needs an absolute target path.")
            step_ids.add(step.step_id)

    def run(
        self,
        workflow: Workflow,
        *,
        cancel_check: CancelCheck | None = None,
        run_id: str | None = None,
        allowed_root: Path | None = None,
    ) -> WorkflowRun:
        """Run a workflow until completion, failure, or cancellation."""
        self.validate(workflow)
        started_at = datetime.now(UTC)
        results: list[StepResult] = []
        is_cancelled = cancel_check or (lambda: False)

        def completed(status: WorkflowStatus) -> WorkflowRun:
            return WorkflowRun(
                run_id=run_id or str(uuid4()),
                workflow_id=workflow.workflow_id,
                status=status,
                results=tuple(results),
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )

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
                return completed(WorkflowStatus.CANCELLED)

            results.append(
                StepResult(
                    step_id=step.step_id,
                    status=StepStatus.RUNNING,
                    message=f"Running: {step.name}",
                )
            )
            if step.kind in (StepKind.INSPECT_PATH, StepKind.VERIFY_PATH_EXISTS):
                result = self._run_path_step(step, allowed_root)
                results[-1] = result
                if result.status is not StepStatus.VERIFIED:
                    results.extend(
                        StepResult(
                            step_id=remaining.step_id,
                            status=StepStatus.SKIPPED,
                            message="Skipped because an earlier step failed.",
                        )
                        for remaining in workflow.steps[index + 1 :]
                    )
                    return completed(WorkflowStatus.FAILED)
                continue
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
                return completed(WorkflowStatus.FAILED)

            results[-1] = StepResult(
                step_id=step.step_id,
                status=StepStatus.SUCCEEDED,
                message=step.message,
            )

        return completed(WorkflowStatus.SUCCEEDED)

    @staticmethod
    def _run_path_step(step: WorkflowStep, allowed_root: Path | None) -> StepResult:
        if allowed_root is None:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.INCONCLUSIVE,
                message="No authorized folder was provided for this path check.",
            )
        target = Path(step.target or "").resolve(strict=False)
        try:
            root = allowed_root.resolve(strict=True)
        except FileNotFoundError:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.INCONCLUSIVE,
                message="The authorized folder is unavailable.",
            )
        try:
            target.relative_to(root)
        except ValueError:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                message="The target is outside the authorized folder.",
            )
        if target.is_symlink() or not target.is_file():
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                message="The target is not an accessible regular file.",
            )
        stat = target.stat()
        evidence = (
            f"path={target}",
            f"size={stat.st_size}",
        )
        return StepResult(
            step_id=step.step_id,
            status=StepStatus.VERIFIED,
            message=step.message,
            evidence=evidence,
        )
