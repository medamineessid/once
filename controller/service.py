"""Qt-free services that connect the UI to the workflow engine."""

from __future__ import annotations

from pathlib import Path

from engine.errors import WorkflowValidationError
from engine.workflow import (
    StepKind,
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
    ) -> None:
        self._runner = runner or WorkflowRunner()
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

    def run_workflow(self, workflow: Workflow, allowed_root: Path | None = None) -> WorkflowRun:
        """Execute a workflow and persist its real outcome when history is configured."""
        run = self._runner.run(workflow, allowed_root=allowed_root)
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
