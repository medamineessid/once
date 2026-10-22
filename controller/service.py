"""Qt-free services that connect the UI to the workflow engine."""

from __future__ import annotations

from engine.workflow import (
    StepKind,
    Workflow,
    WorkflowRun,
    WorkflowRunner,
    WorkflowStep,
)
from storage.history import ExecutionHistory


class WorkflowService:
    """Create and execute the currently supported local workflow definitions."""

    def __init__(
        self,
        runner: WorkflowRunner | None = None,
        history: ExecutionHistory | None = None,
    ) -> None:
        self._runner = runner or WorkflowRunner()
        self._history = history

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

    def run_workflow(self, workflow: Workflow) -> WorkflowRun:
        """Execute a workflow and persist its real outcome when history is configured."""
        run = self._runner.run(workflow)
        if self._history is not None:
            self._history.record(run)
        return run
