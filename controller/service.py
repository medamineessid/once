"""Qt-free services that connect the UI to the workflow engine."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ai.approval import ApprovedProposal
from engine.errors import WorkflowValidationError
from engine.replay import ReplayExecutor, ReplayPreview
from engine.workflow import (
    StepKind,
    StepResult,
    WindowInspector,
    Workflow,
    WorkflowRun,
    WorkflowRunner,
    WorkflowStep,
)
from storage.database import connect
from storage.history import ExecutionHistory
from storage.workflows import load_workflow, save_workflow


class WorkflowService:
    """Create and execute the currently supported local workflow definitions."""

    def __init__(
        self,
        runner: WorkflowRunner | None = None,
        history: ExecutionHistory | None = None,
        workflow_directory: Path | None = None,
        window_inspector: WindowInspector | None = None,
    ) -> None:
        self._runner = runner or WorkflowRunner()
        self._replay = ReplayExecutor()
        if window_inspector is None:
            from integrations.windows_automation import PywinautoWindowInspector

            self._window_inspector = PywinautoWindowInspector().inspect
        else:
            self._window_inspector = window_inspector
        self._history = history
        self._workflow_directory = workflow_directory
        if workflow_directory is not None:
            workflow_directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_app_data(cls, app_data_dir: Path) -> WorkflowService:
        """Create a service backed by the application's local data directory."""
        workflow_directory = app_data_dir / "workflows"
        workflow_directory.mkdir(parents=True, exist_ok=True)
        history = ExecutionHistory(connect(app_data_dir / "once.db"))
        return cls(history=history, workflow_directory=workflow_directory)

    @staticmethod
    def demo_workflow() -> Workflow:
        """Return a visible, deterministic workflow used by the first UI milestone."""
        return Workflow(
            workflow_id="demo-local-workflow",
            name="Local workflow foundation demo",
            steps=(
                WorkflowStep(
                    step_id="inspect",
                    name="Inspect workflow",
                    kind=StepKind.REPORT,
                    message="Workflow definition accepted.",
                ),
                WorkflowStep(
                    step_id="record",
                    name="Record controlled result",
                    kind=StepKind.REPORT,
                    message="Controlled result recorded locally.",
                ),
            ),
        )

    def run_demo(self) -> WorkflowRun:
        """Execute the demo through the same service path used by future workflows."""
        return self.run_workflow(self.demo_workflow())

    def run_workflow(
        self,
        workflow: Workflow,
        allowed_root: Path | None = None,
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[StepResult], None] | None = None,
    ) -> WorkflowRun:
        """Execute a workflow and persist its real outcome when history is configured."""
        run = self._runner.run(
            workflow,
            allowed_root=allowed_root,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )
        if self._history is not None:
            self._history.record(run)
        return run

    def save(self, workflow: Workflow, path: Path | None = None) -> Path:
        """Validate and save a workflow through the storage boundary."""
        if self._workflow_directory is None and path is None:
            raise WorkflowValidationError("Workflow storage is not configured.")
        destination = path or self._workflow_directory / f"{workflow.workflow_id}.json"
        save_workflow(workflow, destination)
        return destination

    def save_approved(self, proposal: ApprovedProposal) -> Path:
        """Save only a proposal that passed the explicit approval gate."""
        if not isinstance(proposal, ApprovedProposal):
            raise WorkflowValidationError("Only an explicitly approved proposal can be saved.")
        return self.save(proposal.workflow)

    def run_approved(
        self,
        proposal: ApprovedProposal,
        allowed_root: Path | None = None,
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[StepResult], None] | None = None,
    ) -> WorkflowRun:
        """Execute only a proposal that passed the explicit approval gate."""
        if not isinstance(proposal, ApprovedProposal):
            raise WorkflowValidationError("Only an explicitly approved proposal can run.")
        return self.run_replay(
            proposal.workflow,
            allowed_root=allowed_root,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )

    def preview_replay(self, workflow: Workflow) -> ReplayPreview:
        """Return a policy check and readable preview without executing."""
        return self._replay.preview(workflow)

    def run_replay(
        self,
        workflow: Workflow,
        allowed_root: Path | None,
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[StepResult], None] | None = None,
        window_inspector: WindowInspector | None = None,
    ) -> WorkflowRun:
        """Execute and persist only actions allowed by the replay policy."""
        run = self._replay.execute(
            workflow,
            allowed_root=allowed_root,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            window_inspector=window_inspector or self._window_inspector,
        )
        if self._history is not None:
            self._history.record(run)
        return run

    def list_saved(self) -> tuple[Path, ...]:
        """Return saved workflow files in deterministic order."""
        if self._workflow_directory is None:
            return ()
        return tuple(
            sorted(self._workflow_directory.glob("*.json"), key=lambda item: item.name.casefold())
        )

    @staticmethod
    def load(path: Path) -> Workflow:
        """Load one validated workflow through the storage boundary."""
        return load_workflow(path)

    def history(self) -> tuple[WorkflowRun, ...]:
        """Return persisted executions, newest first."""
        if self._history is None:
            return ()
        return tuple(record.run for record in self._history.list_runs())

    def close(self) -> None:
        """Release controller-owned persistence resources."""
        if self._history is not None:
            self._history.close()
            self._history = None
