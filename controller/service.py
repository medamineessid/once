"""Qt-free services that connect the UI to the workflow engine."""

from __future__ import annotations

from engine.workflow import (
    StepKind,
    Workflow,
    WorkflowRun,
    WorkflowRunner,
    WorkflowStep,
)


class WorkflowService:
    """Create and execute the currently supported local workflow definitions."""

    def __init__(self, runner: WorkflowRunner | None = None) -> None:
        self._runner = runner or WorkflowRunner()

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
        return self._runner.run(self.demo_workflow())
