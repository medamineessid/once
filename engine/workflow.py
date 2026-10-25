"""Deterministic orchestration of declarative workflow steps."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from .errors import ExecutionError, WorkflowValidationError

MAX_WORKFLOW_STEPS = 100
MAX_TEXT_LENGTH = 500


class StepKind(StrEnum):
    """Built-in step behaviours available without external integrations."""

    REPORT = "REPORT"
    FAIL = "FAIL"
    INSPECT_PATH = "INSPECT_PATH"
    VERIFY_PATH_EXISTS = "VERIFY_PATH_EXISTS"
    INSPECT_WINDOW = "INSPECT_WINDOW"
    INSPECT_UI_ELEMENT = "INSPECT_UI_ELEMENT"


class PostconditionKind(StrEnum):
    """Built-in checks that may be required after a step succeeds."""

    PATH_EXISTS = "PATH_EXISTS"


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
    max_attempts: int = 1
    postcondition: PostconditionKind | None = None


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
ProgressCallback = Callable[[StepResult], None]
WindowInspector = Callable[[str], tuple[str, ...]]
UIElementInspector = Callable[[str], tuple[str, ...]]


def _validate_window_target(step: WorkflowStep) -> None:
    if not step.target:
        raise WorkflowValidationError(f"Step {step.step_id} needs a window target.")
    try:
        target = json.loads(step.target)
    except json.JSONDecodeError as error:
        raise WorkflowValidationError(
            f"Step {step.step_id} has an invalid window target."
        ) from error
    _validate_window_identity(step, target)


def _validate_window_identity(step: WorkflowStep, target: object) -> None:
    if not isinstance(target, dict) or not set(target).issubset(
        {"title", "process_id", "class_name", "automation_id"}
    ):
        raise WorkflowValidationError(f"Step {step.step_id} has unknown window target fields.")
    if not isinstance(target.get("title"), str) or not target["title"].strip():
        raise WorkflowValidationError(f"Step {step.step_id} needs a window title.")
    if "process_id" in target and (
        not isinstance(target["process_id"], int) or target["process_id"] < 1
    ):
        raise WorkflowValidationError(f"Step {step.step_id} has an invalid process ID.")
    for field in ("title", "class_name", "automation_id"):
        if field in target and not isinstance(target[field], str):
            raise WorkflowValidationError(f"Step {step.step_id} has an invalid {field}.")


def _validate_ui_element_target(step: WorkflowStep) -> None:
    if not step.target:
        raise WorkflowValidationError(f"Step {step.step_id} needs a UI element target.")
    try:
        target = json.loads(step.target)
    except json.JSONDecodeError as error:
        raise WorkflowValidationError(
            f"Step {step.step_id} has an invalid UI element target."
        ) from error
    if not isinstance(target, dict) or set(target) != {"window", "element"}:
        raise WorkflowValidationError(
            f"Step {step.step_id} needs window and element target fields."
        )
    window = target["window"]
    element = target["element"]
    if not isinstance(window, dict) or not isinstance(element, dict):
        raise WorkflowValidationError(f"Step {step.step_id} has invalid UI target fields.")
    _validate_window_identity(step, window)
    if not set(element).issubset({"automation_id", "control_type", "class_name"}):
        raise WorkflowValidationError(f"Step {step.step_id} has unknown element target fields.")
    if not isinstance(element.get("automation_id"), str) or not element["automation_id"].strip():
        raise WorkflowValidationError(f"Step {step.step_id} needs an AutomationId.")
    if not isinstance(element.get("control_type"), str) or not element["control_type"].strip():
        raise WorkflowValidationError(f"Step {step.step_id} needs a control type.")
    if "class_name" in element and not isinstance(element["class_name"], str):
        raise WorkflowValidationError(f"Step {step.step_id} has an invalid element class name.")


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
            if not isinstance(step.max_attempts, int) or not 1 <= step.max_attempts <= 3:
                raise WorkflowValidationError(
                    f"Step {step.step_id} must allow between 1 and 3 attempts."
                )
            if step.postcondition is not None and not isinstance(
                step.postcondition, PostconditionKind
            ):
                raise WorkflowValidationError(f"Step {step.step_id} has an unknown postcondition.")
            if step.postcondition is not None and not step.target:
                raise WorkflowValidationError(
                    f"Step {step.step_id} needs a target for its postcondition."
                )
            if step.kind in (StepKind.INSPECT_PATH, StepKind.VERIFY_PATH_EXISTS) and (
                not step.target or not Path(step.target).is_absolute()
            ):
                raise WorkflowValidationError(f"Step {step.step_id} needs an absolute target path.")
            if step.kind is StepKind.INSPECT_WINDOW:
                _validate_window_target(step)
            if step.kind is StepKind.INSPECT_UI_ELEMENT:
                _validate_ui_element_target(step)
            step_ids.add(step.step_id)

    def run(
        self,
        workflow: Workflow,
        *,
        cancel_check: CancelCheck | None = None,
        run_id: str | None = None,
        allowed_root: Path | None = None,
        progress_callback: ProgressCallback | None = None,
        window_inspector: WindowInspector | None = None,
        ui_element_inspector: UIElementInspector | None = None,
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

            result = self._run_with_retries(
                step,
                allowed_root,
                is_cancelled,
                window_inspector,
                ui_element_inspector,
            )
            results.append(result)
            if progress_callback is not None:
                progress_callback(result)
            if result.status not in (StepStatus.SUCCEEDED, StepStatus.VERIFIED):
                results.extend(
                    StepResult(
                        step_id=remaining.step_id,
                        status=StepStatus.SKIPPED,
                        message="Skipped because an earlier step failed.",
                    )
                    for remaining in workflow.steps[index + 1 :]
                )
                return completed(
                    WorkflowStatus.CANCELLED
                    if result.status is StepStatus.SKIPPED
                    else WorkflowStatus.FAILED
                )

        return completed(WorkflowStatus.SUCCEEDED)

    def _run_with_retries(
        self,
        step: WorkflowStep,
        allowed_root: Path | None,
        cancel_check: CancelCheck,
        window_inspector: WindowInspector | None,
        ui_element_inspector: UIElementInspector | None,
    ) -> StepResult:
        attempts: list[str] = []
        for attempt in range(1, step.max_attempts + 1):
            if attempt > 1 and cancel_check():
                return StepResult(
                    step.step_id,
                    StepStatus.SKIPPED,
                    "Skipped because the workflow was cancelled.",
                    tuple(attempts),
                )
            if window_inspector is None and ui_element_inspector is None:
                result = self._run_once(step, allowed_root)
            else:
                result = self._run_once(step, allowed_root, window_inspector, ui_element_inspector)
            if result.status in (StepStatus.SUCCEEDED, StepStatus.VERIFIED):
                if step.postcondition is None:
                    if attempt == 1:
                        return result
                    return StepResult(
                        step.step_id,
                        result.status,
                        f"{result.message} (attempt {attempt})",
                        tuple(attempts),
                    )
                postcondition = self._check_postcondition(step, allowed_root)
                if postcondition.status is StepStatus.VERIFIED:
                    return StepResult(
                        step.step_id,
                        result.status,
                        f"{result.message} (attempt {attempt})",
                        result.evidence + postcondition.evidence,
                    )
                result = postcondition
            attempts.append(f"attempt {attempt}: {result.message}")
            if attempt < step.max_attempts:
                continue
            return StepResult(
                step.step_id,
                result.status,
                f"{result.message} after {attempt} attempt(s).",
                tuple(attempts) + result.evidence,
            )
        raise AssertionError("Retry loop must return a result.")

    def _run_once(
        self,
        step: WorkflowStep,
        allowed_root: Path | None,
        window_inspector: WindowInspector | None = None,
        ui_element_inspector: UIElementInspector | None = None,
    ) -> StepResult:
        if step.kind in (StepKind.INSPECT_PATH, StepKind.VERIFY_PATH_EXISTS):
            return self._run_path_step(step, allowed_root)
        if step.kind is StepKind.INSPECT_WINDOW:
            if window_inspector is not None:
                try:
                    return StepResult(
                        step.step_id,
                        StepStatus.VERIFIED,
                        step.message,
                        window_inspector(step.target or ""),
                    )
                except (ExecutionError, OSError, RuntimeError, ValueError) as error:
                    return StepResult(step.step_id, StepStatus.FAILED, str(error))
            return StepResult(
                step.step_id,
                StepStatus.INCONCLUSIVE,
                "No Windows UI Automation inspector was configured.",
            )
        if step.kind is StepKind.INSPECT_UI_ELEMENT:
            if ui_element_inspector is not None:
                try:
                    return StepResult(
                        step.step_id,
                        StepStatus.VERIFIED,
                        step.message,
                        ui_element_inspector(step.target or ""),
                    )
                except (ExecutionError, OSError, RuntimeError, ValueError) as error:
                    return StepResult(step.step_id, StepStatus.FAILED, str(error))
            return StepResult(
                step.step_id,
                StepStatus.INCONCLUSIVE,
                "No Windows UI Automation element inspector was configured.",
            )
        if step.kind is StepKind.FAIL:
            return StepResult(step.step_id, StepStatus.FAILED, step.message)
        return StepResult(step.step_id, StepStatus.SUCCEEDED, step.message)

    @staticmethod
    def _check_postcondition(step: WorkflowStep, allowed_root: Path | None) -> StepResult:
        if step.postcondition is PostconditionKind.PATH_EXISTS:
            return WorkflowRunner._run_path_step(
                WorkflowStep(
                    step.step_id,
                    step.name,
                    StepKind.VERIFY_PATH_EXISTS,
                    "Postcondition verified.",
                    step.target,
                ),
                allowed_root,
            )
        return StepResult(step.step_id, StepStatus.FAILED, "Postcondition was not met.")

    @staticmethod
    def _run_path_step(step: WorkflowStep, allowed_root: Path | None) -> StepResult:
        if allowed_root is None:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.INCONCLUSIVE,
                message="No authorized folder was provided for this path check.",
            )
        target_path = Path(step.target or "")
        if target_path.is_symlink():
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                message="The target must not be a symbolic link.",
            )
        target = target_path.resolve(strict=False)
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
        if not target.is_file():
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
