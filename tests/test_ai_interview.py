"""Tests for bounded AI interview orchestration."""

from __future__ import annotations

import pytest

from ai.interview import InterviewSession
from ai.models import AnalysisRequest, ProviderDraft, ProviderQuestion
from ai.provider import FakeAnalysisProvider
from engine.errors import AIProviderError
from engine.workflow import StepKind, Workflow, WorkflowStep
from recorder.drafts import RawDraft


def request() -> AnalysisRequest:
    return AnalysisRequest(RawDraft("recording", ()))


def draft() -> ProviderDraft:
    return ProviderDraft(
        "goal",
        Workflow("workflow", "Workflow", (WorkflowStep("step", "Step", StepKind.REPORT, "Done"),)),
    )


def test_interview_exposes_question_then_approved_candidate() -> None:
    session = InterviewSession(
        FakeAnalysisProvider((ProviderQuestion("What is success?"), draft())), request()
    )

    first = session.start()
    second = session.answer("A report is visible.")

    assert first.question == "What is success?"
    assert first.complete is False
    assert second.complete is True
    assert second.draft == draft()


def test_interview_rejects_empty_answers_and_answers_after_completion() -> None:
    empty_session = InterviewSession(
        FakeAnalysisProvider((ProviderQuestion("Question"),)), request()
    )
    empty_session.start()
    with pytest.raises(AIProviderError, match="must not be empty"):
        empty_session.answer(" ")

    session = InterviewSession(FakeAnalysisProvider((draft(),)), request())
    session.start()

    with pytest.raises(AIProviderError, match="already complete"):
        session.answer("answer")
