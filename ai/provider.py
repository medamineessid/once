"""Provider protocol and deterministic fake implementation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

from engine.errors import AIProviderError, WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowRunner, WorkflowStep
from recorder.drafts import RawDraftAction
from recorder.models import RecordedEventKind

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
    """Return a local provider that maps observations into engine step drafts."""

    class RecordingProvider:
        def analyze(self, request: AnalysisRequest) -> ProviderDraft:
            steps: list[WorkflowStep] = []
            launched: set[str] = set()
            for index, action in enumerate(request.draft.actions, start=1):
                steps.append(_step_for_action(action, index, launched))
            workflow = Workflow(
                workflow_id=f"recording-{request.draft.recording_id}",
                name="Recorded task draft",
                steps=tuple(steps)
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


#: Recorded process names the engine's application registry knows, keyed
#: case-insensitively. Unknown processes stay review-only observations.
PROCESS_TO_APPLICATION: dict[str, str] = {
    "code.exe": "vscode",
    "notepad.exe": "notepad",
    "chrome.exe": "chrome",
}


def _step_for_action(action: RawDraftAction, index: int, launched: set[str]) -> WorkflowStep:
    """Turn one observation into a validated engine step deterministically."""
    step_id = f"observation-{action.sequence}"
    name = f"Observation {index}"
    if action.source_event is RecordedEventKind.WINDOW_OPEN:
        application = _application_for_process(action.process_name)
        if application is not None and application not in launched:
            launched.add(application)
            return WorkflowStep(
                step_id,
                name,
                StepKind.LAUNCH_APPLICATION,
                f"Launch {application}.",
                target=json.dumps({"application": application}),
            )
        if application is not None:
            return WorkflowStep(
                step_id,
                name,
                StepKind.REPORT,
                f"{action.description} The application is already part of this draft.",
            )
        return WorkflowStep(step_id, name, StepKind.REPORT, action.description)
    if action.source_event is RecordedEventKind.WINDOW_CLOSE:
        application = _application_for_process(action.process_name)
        if application is not None and application in launched:
            return WorkflowStep(
                step_id,
                name,
                StepKind.CLOSE_APPLICATION,
                f"Close {application}.",
                target=json.dumps({"application": application}),
            )
        if application is not None:
            return WorkflowStep(
                step_id,
                name,
                StepKind.REPORT,
                (
                    f"{action.description} This draft does not launch "
                    f"{application}, so nothing is allowed to close it."
                ),
            )
        return WorkflowStep(step_id, name, StepKind.REPORT, action.description)
    return WorkflowStep(step_id, name, StepKind.REPORT, action.description)


def _application_for_process(process_name: str | None) -> str | None:
    """Map a recorded process name to an allow-listed application name."""
    if not process_name:
        return None
    return PROCESS_TO_APPLICATION.get(process_name.strip().lower())
