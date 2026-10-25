"""Policy-gated replay for the smallest safe supported action set."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import ExecutionError
from .workflow import (
    BrowserActions,
    CancelCheck,
    DesktopActions,
    ProgressCallback,
    StepKind,
    StepResult,
    StepStatus,
    UIElementInspector,
    WindowInspector,
    Workflow,
    WorkflowRun,
    WorkflowRunner,
    WorkflowStatus,
)


@dataclass(frozen=True)
class ReplayPolicy:
    """Allowlist and bounds for deterministic replay."""

    allowed_kinds: frozenset[StepKind] = frozenset(
        {
            StepKind.INSPECT_PATH,
            StepKind.VERIFY_PATH_EXISTS,
            StepKind.INSPECT_WINDOW,
            StepKind.INSPECT_UI_ELEMENT,
            StepKind.VERIFY_FILE_TEXT,
            StepKind.WAIT_WINDOW,
        }
    )
    max_steps: int = 20


#: Read-only inspection and waiting, runnable without mutating anything.
READ_ONLY_POLICY = ReplayPolicy()

#: Desktop interaction kinds that mutate the desktop and therefore require an
#: explicit, recorded approval of the exact workflow before they may run.
MUTATING_DESKTOP_KINDS: frozenset[StepKind] = frozenset(
    {
        StepKind.LAUNCH_APPLICATION,
        StepKind.CLICK_UI_ELEMENT,
        StepKind.TYPE_TEXT,
        StepKind.PRESS_SHORTCUT,
        StepKind.LAUNCH_BROWSER,
        StepKind.NAVIGATE_BROWSER,
        StepKind.INTERACT_PAGE_ELEMENT,
    }
)

#: Read-only page steps that need the browser provider but never mutate it.
BROWSER_READ_KINDS: frozenset[StepKind] = frozenset(
    {StepKind.INSPECT_PAGE, StepKind.FIND_PAGE_ELEMENT, StepKind.WAIT_PAGE}
)

#: Cross-application policy: read-only steps plus approved desktop/browser
#: mutations. The same approval gate covers both surfaces.
DESKTOP_INTERACTION_POLICY = ReplayPolicy(
    allowed_kinds=frozenset(
        {
            StepKind.INSPECT_PATH,
            StepKind.VERIFY_PATH_EXISTS,
            StepKind.INSPECT_WINDOW,
            StepKind.INSPECT_UI_ELEMENT,
            StepKind.VERIFY_FILE_TEXT,
            StepKind.WAIT_WINDOW,
        }
        | MUTATING_DESKTOP_KINDS
        | BROWSER_READ_KINDS
    )
)


@dataclass(frozen=True)
class ReplayPreview:
    """A user-facing description of replay permission and expected outcomes."""

    workflow_id: str
    steps: tuple[str, ...]
    executable: bool


class ReplayExecutor:
    """Execute only policy-approved, read-only workflow actions."""

    def __init__(self, policy: ReplayPolicy | None = None) -> None:
        self._policy = policy or ReplayPolicy()
        self._runner = WorkflowRunner()

    def validate(self, workflow: Workflow) -> None:
        """Reject unsupported or oversized replay requests before execution."""
        WorkflowRunner.validate(workflow)
        if len(workflow.steps) > self._policy.max_steps:
            raise ExecutionError("Replay contains too many steps.")
        unsupported = [
            step.kind.value
            for step in workflow.steps
            if step.kind not in self._policy.allowed_kinds
        ]
        if unsupported:
            raise ExecutionError(
                f"Replay does not allow these step kinds: {', '.join(unsupported)}."
            )

    def preview(self, workflow: Workflow) -> ReplayPreview:
        """Describe every step without reading or changing the target."""
        WorkflowRunner.validate(workflow)
        return ReplayPreview(
            workflow.workflow_id,
            tuple(
                f"{step.step_id}: action={step.kind.value} "
                f"target={step.target or 'none'} permission="
                f"{'ALLOWED' if step.kind in self._policy.allowed_kinds else 'UNSUPPORTED'} "
                f"expected={step.message}"
                for step in workflow.steps
            ),
            len(workflow.steps) <= self._policy.max_steps
            and all(step.kind in self._policy.allowed_kinds for step in workflow.steps),
        )

    def execute(
        self,
        workflow: Workflow,
        *,
        allowed_root: Path | None,
        dry_run: bool = False,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
        window_inspector: WindowInspector | None = None,
        ui_element_inspector: UIElementInspector | None = None,
        desktop_actions: DesktopActions | None = None,
        browser_actions: BrowserActions | None = None,
    ) -> WorkflowRun:
        """Preview or execute the allowlisted read-only actions."""
        self.validate(workflow)
        if dry_run:
            from datetime import UTC, datetime
            from uuid import uuid4

            now = datetime.now(UTC)
            results = tuple(
                StepResult(
                    step.step_id,
                    StepStatus.SUCCEEDED,
                    f"Dry run: would inspect {step.target}.",
                )
                for step in workflow.steps
            )
            return WorkflowRun(
                str(uuid4()),
                workflow.workflow_id,
                WorkflowStatus.SUCCEEDED,
                results,
                now,
                datetime.now(UTC),
            )
        return self._runner.run(
            workflow,
            allowed_root=allowed_root,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            window_inspector=window_inspector,
            ui_element_inspector=ui_element_inspector,
            desktop_actions=desktop_actions,
            browser_actions=browser_actions,
        )
