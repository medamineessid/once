"""Provider protocol and deterministic fake implementation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
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


def _recorded_executable(action: RawDraftAction) -> str | None:
    """The executable path the recording captured for this action, if it has one.

    The recording is the only source of application identity: Once never maps a
    process name to an application it happens to know. Without a recorded path
    the observation is kept for review and no launch or close is proposed.
    """
    recorded = getattr(action, "executable", None)
    if isinstance(recorded, str) and recorded.strip():
        return recorded.strip()
    return None


def _step_for_action(action: RawDraftAction, index: int, launched: set[str]) -> WorkflowStep:
    """Turn one observation into a validated engine step deterministically."""
    step_id = f"observation-{action.sequence}"
    name = f"Observation {index}"
    executable = _recorded_executable(action)
    if action.source_event is RecordedEventKind.WINDOW_OPEN and executable is not None:
        if executable not in launched:
            launched.add(executable)
            return WorkflowStep(
                step_id,
                name,
                StepKind.LAUNCH_APPLICATION,
                f"Launch {Path(executable).stem}.",
                target=json.dumps({"executable": executable}),
            )
        return WorkflowStep(
            step_id,
            name,
            StepKind.REPORT,
            f"{action.description} The application is already part of this draft.",
        )
    if action.source_event is RecordedEventKind.WINDOW_CLOSE and executable is not None:
        if executable in launched:
            return WorkflowStep(
                step_id,
                name,
                StepKind.CLOSE_APPLICATION,
                f"Close {Path(executable).stem}.",
                target=json.dumps({"executable": executable}),
            )
        return WorkflowStep(
            step_id,
            name,
            StepKind.REPORT,
            (
                f"{action.description} This draft does not launch "
                f"{Path(executable).stem}, so nothing is allowed to close it."
            ),
        )
    return WorkflowStep(step_id, name, StepKind.REPORT, action.description)
