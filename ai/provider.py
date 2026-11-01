"""Provider protocol and deterministic fake implementation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from engine.errors import AIProviderError, WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowRunner, WorkflowStep

from .models import AnalysisRequest, ProviderDraft, ProviderQuestion, ProviderResponse

MAX_INTERVIEW_TURNS = 5


class AnalysisProvider(Protocol):
    """Analyze a recording and return one bounded question or draft."""

    def analyze(self, request: AnalysisRequest) -> ProviderResponse:
        """Return a proposal without executing any workflow step."""


class FakeAnalysisProvider:
    """Deterministic provider used by tests and offline demonstrations."""

    def __init__(self, responses: Sequence[ProviderResponse]) -> None:
        self._responses = tuple(responses)
        self._index = 0

    def analyze(self, request: AnalysisRequest) -> ProviderResponse:
        """Return the next configured response and reject unbounded interviews."""
        if len(request.conversation) > MAX_INTERVIEW_TURNS:
            raise AIProviderError("The AI interview reached its question limit.")
        if self._index >= len(self._responses):
            raise AIProviderError("The fake provider has no response configured.")
        response = self._responses[self._index]
        self._index += 1
        if isinstance(response, ProviderDraft):
            try:
                WorkflowRunner.validate(response.workflow)
            except WorkflowValidationError as error:
                raise AIProviderError("The provider returned an invalid workflow draft.") from error
        return response


def deterministic_demo_provider() -> FakeAnalysisProvider:
    """Return an offline provider that proposes a real, validated workflow."""
    return FakeAnalysisProvider(
        (
            ProviderQuestion("What result should confirm that this task succeeded?"),
            ProviderDraft(
                goal="Record the observed task",
                workflow=Workflow(
                    "recorded-task",
                    "Recorded task",
                    (
                        WorkflowStep(
                            "summary",
                            "Summarize observation",
                            StepKind.REPORT,
                            "Review the recorded task before approval.",
                        ),
                    ),
                ),
            ),
        ),
    )


def deterministic_recording_provider() -> AnalysisProvider:
    """Return a local provider that turns observations into safe report steps."""

    class RecordingProvider:
        def analyze(self, request: AnalysisRequest) -> ProviderDraft:
            steps = tuple(
                WorkflowStep(
                    step_id=f"observation-{action.sequence}",
                    name=f"Observation {index}",
                    kind=StepKind.REPORT,
                    message=action.description,
                )
                for index, action in enumerate(request.draft.actions, start=1)
            )
            workflow = Workflow(
                workflow_id=f"recording-{request.draft.recording_id}",
                name="Recorded task draft",
                steps=steps
                or (
                    WorkflowStep(
                        step_id="observation-empty",
                        name="No actions captured",
                        kind=StepKind.REPORT,
                        message="No usable actions were captured. Record the task again.",
                    ),
                ),
            )
            WorkflowRunner.validate(workflow)
            return ProviderDraft(
                goal="Review the recorded observations and turn them into safe steps.",
                workflow=workflow,
            )

    return RecordingProvider()
