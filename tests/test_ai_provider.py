"""Tests for provider-independent AI proposal handling."""

from __future__ import annotations

import pytest

from ai.gemini import GeminiProvider
from ai.models import AnalysisRequest, ProviderDraft, ProviderQuestion
from ai.provider import FakeAnalysisProvider, deterministic_demo_provider
from engine.errors import AIProviderError
from recorder.drafts import RawDraft


def request() -> AnalysisRequest:
    return AnalysisRequest(RawDraft("recording", ()))


def test_fake_provider_returns_bounded_question_then_validated_draft() -> None:
    provider = deterministic_demo_provider()

    question = provider.analyze(request())
    draft = provider.analyze(request())

    assert isinstance(question, ProviderQuestion)
    assert isinstance(draft, ProviderDraft)
    assert draft.workflow.steps[0].kind.value == "REPORT"


def test_fake_provider_rejects_unbounded_interview() -> None:
    provider = FakeAnalysisProvider((ProviderQuestion("Question"),))

    with pytest.raises(AIProviderError, match="question limit"):
        provider.analyze(AnalysisRequest(request().draft, tuple("123456")))


def test_gemini_is_disabled_by_default() -> None:
    with pytest.raises(AIProviderError, match="disabled"):
        GeminiProvider("not-used").analyze(request())
