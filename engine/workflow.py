"""Deterministic orchestration of declarative workflow steps."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
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
    LAUNCH_APPLICATION = "LAUNCH_APPLICATION"
    WAIT_WINDOW = "WAIT_WINDOW"
    CLICK_UI_ELEMENT = "CLICK_UI_ELEMENT"
    TYPE_TEXT = "TYPE_TEXT"
    PRESS_SHORTCUT = "PRESS_SHORTCUT"
    VERIFY_FILE_TEXT = "VERIFY_FILE_TEXT"


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
    timeout_seconds: float = 30.0


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

#: Per-step wait/launch bound; keeps desktop interactions from running unbounded.
MIN_STEP_TIMEOUT_SECONDS = 0.5
MAX_STEP_TIMEOUT_SECONDS = 60.0
DEFAULT_STEP_TIMEOUT_SECONDS = 30.0

MAX_ARGUMENT_COUNT = 16
MAX_ARGUMENT_LENGTH = 200
MAX_TEXT_FILE_BYTES = 65_536

ALLOWED_SHORTCUTS: tuple[str, ...] = (
    "ctrl+s",
    "ctrl+a",
    "ctrl+c",
    "ctrl+v",
    "ctrl+x",
    "ctrl+z",
    "ctrl+y",
    "enter",
    "escape",
    "tab",
)

ALLOWED_INTERACTIONS: frozenset[str] = frozenset({"invoke", "toggle", "select"})

#: Step kinds that require a desktop interaction provider (OS/adapter layer).
DESKTOP_PROVIDER_KINDS = frozenset(
    {
        StepKind.LAUNCH_APPLICATION,
        StepKind.WAIT_WINDOW,
        StepKind.CLICK_UI_ELEMENT,
        StepKind.TYPE_TEXT,
        StepKind.PRESS_SHORTCUT,
    }
)

#: Application names the launch action may use without an explicit path.
#: The registry expands these to full executables; no other name is accepted.
KNOWN_APPLICATIONS: frozenset[str] = frozenset({"notepad"})


class DesktopActions:
    """Adapter contract for the desktop interaction provider.

    Every method receives the fully validated JSON target of one step and
    returns a deterministic StepResult; providers must fail closed through
    FAILED/INCONCLUSIVE results instead of raising for expected refusals.
    """

    def launch_application(self, target_json: str) -> StepResult:
        raise NotImplementedError

    def wait_window(self, target_json: str, timeout_seconds: float) -> StepResult:
        raise NotImplementedError

    def click_element(self, target_json: str) -> StepResult:
        raise NotImplementedError

    def type_text(self, target_json: str) -> StepResult:
        raise NotImplementedError

    def press_shortcut(self, target_json: str) -> StepResult:
        raise NotImplementedError


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


def _load_target(step: WorkflowStep, target: str | None) -> dict:
    """Parse a step's JSON target, rejecting empty or non-object targets."""
    if not target:
        raise WorkflowValidationError(f"Step {step.step_id} needs a target.")
    try:
        parsed = json.loads(target)
    except json.JSONDecodeError as error:
        raise WorkflowValidationError(f"Step {step.step_id} has an invalid target.") from error
    if not isinstance(parsed, dict):
        raise WorkflowValidationError(f"Step {step.step_id} target must be a JSON object.")
    return parsed


def _validate_element_identity(step: WorkflowStep, element: object) -> None:
    if not isinstance(element, dict) or not set(element).issubset(
        {"automation_id", "control_type", "class_name"}
    ):
        raise WorkflowValidationError(f"Step {step.step_id} has unknown element target fields.")
    for field in ("automation_id", "control_type"):
        if not isinstance(element.get(field), str) or not element[field].strip():
            raise WorkflowValidationError(f"Step {step.step_id} needs an element {field}.")
    if "class_name" in element and not isinstance(element["class_name"], str):
        raise WorkflowValidationError(f"Step {step.step_id} has an invalid element class name.")


def _validate_element_target(step: WorkflowStep, target: object, allowed: frozenset[str]) -> None:
    unknown = set(target) - allowed
    if unknown:
        raise WorkflowValidationError(
            f"Step {step.step_id} has unknown target fields: {', '.join(sorted(unknown))}."
        )
    _validate_window_identity(step, target.get("window"))
    _validate_element_identity(step, target.get("element"))


def _require_bounded_string(step: WorkflowStep, container: object, field: str) -> str:
    value = container.get(field) if isinstance(container, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise WorkflowValidationError(f"Step {step.step_id} needs a {field}.")
    if len(value) > MAX_TEXT_LENGTH:
        raise WorkflowValidationError(f"Step {step.step_id} {field} is too long.")
    return value


def _validate_launch_target(step: WorkflowStep) -> None:
    target = _load_target(step, step.target)
    unknown = set(target) - {"application", "executable", "arguments"}
    if unknown:
        raise WorkflowValidationError(
            f"Step {step.step_id} has unknown launch fields: {', '.join(sorted(unknown))}."
        )
    application = target.get("application")
    executable = target.get("executable")
    if (application is None) == (executable is None):
        raise WorkflowValidationError(
            f"Step {step.step_id} needs exactly one of application or executable."
        )
    if application is not None:
        if not isinstance(application, str) or not application.strip():
            raise WorkflowValidationError(
                f"Step {step.step_id} application name must be a non-empty string."
            )
        if len(application) > 64 or application.lower() not in {
            name.lower() for name in KNOWN_APPLICATIONS
        }:
            raise WorkflowValidationError(
                f"Step {step.step_id} names an application the registry does not allow: "
                f"{application}."
            )
    else:
        if not isinstance(executable, str) or not executable.strip():
            raise WorkflowValidationError(
                f"Step {step.step_id} executable must be a non-empty string."
            )
        if len(executable) > 260:
            raise WorkflowValidationError(f"Step {step.step_id} executable path is too long.")
        executable_path = Path(executable)
        if not executable_path.is_absolute():
            raise WorkflowValidationError(
                f"Step {step.step_id} executable must be an absolute path."
            )
        if executable_path.suffix.lower() != ".exe":
            raise WorkflowValidationError(
                f"Step {step.step_id} executable must be a .exe application."
            )
        if any(part == ".." for part in executable_path.parts):
            raise WorkflowValidationError(
                f"Step {step.step_id} executable path must not traverse parent folders."
            )
    arguments = target.get("arguments", [])
    if not isinstance(arguments, list) or len(arguments) > MAX_ARGUMENT_COUNT:
        raise WorkflowValidationError(
            f"Step {step.step_id} must pass at most {MAX_ARGUMENT_COUNT} arguments as a list."
        )
    for argument in arguments:
        if not isinstance(argument, str) or not argument:
            raise WorkflowValidationError(
                f"Step {step.step_id} arguments must be non-empty strings."
            )
        if len(argument) > MAX_ARGUMENT_LENGTH:
            raise WorkflowValidationError(
                f"Step {step.step_id} arguments must be at most {MAX_ARGUMENT_LENGTH} characters."
            )


def _validate_click_target(step: WorkflowStep) -> None:
    target = _load_target(step, step.target)
    _validate_element_target(step, target, {"window", "element", "interaction"} | frozenset())
    interaction = target.get("interaction", "invoke")
    if interaction not in ALLOWED_INTERACTIONS:
        raise WorkflowValidationError(
            f"Step {step.step_id} interaction must be one of: "
            f"{', '.join(sorted(ALLOWED_INTERACTIONS))}."
        )


def _validate_type_target(step: WorkflowStep) -> None:
    target = _load_target(step, step.target)
    _validate_element_target(step, target, {"window", "element", "text"})
    text = target.get("text")
    if not isinstance(text, str) or not text:
        raise WorkflowValidationError(f"Step {step.step_id} needs text to enter.")
    if len(text) > MAX_TEXT_LENGTH:
        raise WorkflowValidationError(f"Step {step.step_id} text is too long.")


def _validate_shortcut_target(step: WorkflowStep) -> None:
    target = _load_target(step, step.target)
    unknown = set(target) - {"window", "keys"}
    if unknown:
        raise WorkflowValidationError(
            f"Step {step.step_id} has unknown shortcut fields: {', '.join(sorted(unknown))}."
        )
    _validate_window_identity(step, target.get("window"))
    keys = target.get("keys")
    if not isinstance(keys, str) or keys.strip().lower() not in ALLOWED_SHORTCUTS:
        raise WorkflowValidationError(
            f"Step {step.step_id} only allows these key combinations: "
            f"{', '.join(ALLOWED_SHORTCUTS)}."
        )


def _validate_verify_file_text_target(step: WorkflowStep) -> None:
    target = _load_target(step, step.target)
    unknown = set(target) - {"path", "contains"}
    if unknown:
        raise WorkflowValidationError(
            f"Step {step.step_id} has unknown text-verification fields: "
            f"{', '.join(sorted(unknown))}."
        )
    path_value = target.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise WorkflowValidationError(f"Step {step.step_id} needs a path to verify.")
    if len(path_value) > 260:
        raise WorkflowValidationError(f"Step {step.step_id} path is too long.")
    if not Path(path_value).is_absolute():
        raise WorkflowValidationError(f"Step {step.step_id} path must be absolute.")
    if any(part == ".." for part in Path(path_value).parts):
        raise WorkflowValidationError(
            f"Step {step.step_id} path must not traverse parent folders."
        )
    _require_bounded_string(step, target, "contains")


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
            if not isinstance(step.timeout_seconds, (int, float)) or isinstance(
                step.timeout_seconds, bool
            ):
                raise WorkflowValidationError(
                    f"Step {step.step_id} timeout_seconds must be a number."
                )
            if not MIN_STEP_TIMEOUT_SECONDS <= step.timeout_seconds <= MAX_STEP_TIMEOUT_SECONDS:
                raise WorkflowValidationError(
                    f"Step {step.step_id} timeout_seconds must be between "
                    f"{MIN_STEP_TIMEOUT_SECONDS} and {MAX_STEP_TIMEOUT_SECONDS}."
                )
            if step.postcondition is not None and not isinstance(
                step.postcondition, PostconditionKind
            ):
                raise WorkflowValidationError(f"Step {step.step_id} has an unknown postcondition.")
            if step.postcondition is not None and step.kind in (
                StepKind.LAUNCH_APPLICATION,
                StepKind.WAIT_WINDOW,
                StepKind.CLICK_UI_ELEMENT,
                StepKind.TYPE_TEXT,
                StepKind.PRESS_SHORTCUT,
                StepKind.VERIFY_FILE_TEXT,
            ):
                raise WorkflowValidationError(
                    f"Step {step.step_id} cannot carry a postcondition; its target "
                    "is not a plain path. Use a separate VERIFY_PATH_EXISTS or "
                    "VERIFY_FILE_TEXT step instead."
                )
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
            if step.kind is StepKind.LAUNCH_APPLICATION:
                _validate_launch_target(step)
            if step.kind is StepKind.WAIT_WINDOW:
                _validate_window_target(step)
            if step.kind is StepKind.CLICK_UI_ELEMENT:
                _validate_click_target(step)
            if step.kind is StepKind.TYPE_TEXT:
                _validate_type_target(step)
            if step.kind is StepKind.PRESS_SHORTCUT:
                _validate_shortcut_target(step)
            if step.kind is StepKind.VERIFY_FILE_TEXT:
                _validate_verify_file_text_target(step)
            step_ids.add(step.step_id)
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
        desktop_actions: DesktopActions | None = None,
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
                desktop_actions,
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
        desktop_actions: DesktopActions | None = None,
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
            if (
                window_inspector is None
                and ui_element_inspector is None
                and desktop_actions is None
            ):
                result = self._run_once(step, allowed_root)
            else:
                result = self._run_once(
                    step, allowed_root, window_inspector, ui_element_inspector, desktop_actions
                )
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
        desktop_actions: DesktopActions | None = None,
    ) -> StepResult:
        if step.kind in (StepKind.INSPECT_PATH, StepKind.VERIFY_PATH_EXISTS):
            return self._run_path_step(step, allowed_root)
        if step.kind is StepKind.VERIFY_FILE_TEXT:
            return self._run_file_text_step(step, allowed_root)
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
        if step.kind in DESKTOP_PROVIDER_KINDS:
            if desktop_actions is None:
                return StepResult(
                    step.step_id,
                    StepStatus.INCONCLUSIVE,
                    "No desktop interaction provider was configured, so this action "
                    "could not run. Nothing was changed on the desktop.",
                )
            try:
                return self._run_desktop_step(step, desktop_actions)
            except (ExecutionError, OSError, RuntimeError, ValueError) as error:
                return StepResult(step.step_id, StepStatus.FAILED, str(error))
        if step.kind is StepKind.FAIL:
            return StepResult(step.step_id, StepStatus.FAILED, step.message)
        return StepResult(step.step_id, StepStatus.SUCCEEDED, step.message)

    @staticmethod
    def _run_desktop_step(step: WorkflowStep, actions: DesktopActions) -> StepResult:
        """Dispatch one desktop interaction to the provider for its exact kind."""
        if actions is None:  # pragma: no cover - guarded by caller
            raise AssertionError("desktop_actions must exist here.")
        if step.kind is StepKind.LAUNCH_APPLICATION:
            result = actions.launch_application(step.target or "")
        elif step.kind is StepKind.WAIT_WINDOW:
            result = actions.wait_window(step.target or "", step.timeout_seconds)
        elif step.kind is StepKind.CLICK_UI_ELEMENT:
            result = actions.click_element(step.target or "")
        elif step.kind is StepKind.TYPE_TEXT:
            result = actions.type_text(step.target or "")
        else:
            result = actions.press_shortcut(step.target or "")
        return replace(result, step_id=step.step_id)

    def _run_file_text_step(self, step: WorkflowStep, allowed_root: Path | None) -> StepResult:
        """Read-only check that a bounded text file inside the authorized root contains text."""
        if allowed_root is None:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.INCONCLUSIVE,
                message="No authorized folder was provided for this text check.",
            )
        parsed = json.loads(step.target or "{}")
        target_path = Path(parsed["path"])
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
        if target.stat().st_size > MAX_TEXT_FILE_BYTES:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                message=f"The file is larger than the {MAX_TEXT_FILE_BYTES} byte evidence bound.",
            )
        expected = parsed["contains"]
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                message=f"The file could not be read for verification: {error}",
            )
        if expected not in content:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                message=f"The expected text does not appear in {target.name}.",
                evidence=(f"contains={expected}", f"path={target}", "match=false"),
            )
        return StepResult(
            step_id=step.step_id,
            status=StepStatus.VERIFIED,
            message=step.message,
            evidence=(f"contains={expected}", f"path={target}", "match=true"),
        )

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
