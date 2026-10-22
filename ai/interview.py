"""Bounded provider-driven interview orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from engine.errors import AIProviderError

from .models import AnalysisRequest, ProviderDraft, ProviderQuestion
from .provider import MAX_INTERVIEW_TURNS, AnalysisProvider


@dataclass(frozen=True)
class InterviewState:
    """Immutable snapshot suitable for display by a UI."""

    conversation: tuple[str, ...]
    question: str | None
    draft: ProviderDraft | None
    complete: bool


class InterviewSession:
    """Coordinate a bounded question/answer loop without executing workflows."""

    def __init__(self, provider: AnalysisProvider, request: AnalysisRequest) -> None:
        self._provider = provider
        self._request = request
        self._conversation: list[str] = list(request.conversation)
        self._state = InterviewState(tuple(self._conversation), None, None, False)

    @property
    def state(self) -> InterviewState:
        """Return the current immutable interview snapshot."""
        return self._state

    def start(self) -> InterviewState:
        """Ask the provider for the first bounded proposal."""
        return self._advance()

    def answer(self, text: str) -> InterviewState:
        """Record one answer and request the next proposal."""
        if self._state.complete:
            raise AIProviderError("The interview is already complete.")
        if not text.strip():
            raise AIProviderError("Interview answers must not be empty.")
        if len(self._conversation) >= MAX_INTERVIEW_TURNS * 2:
            raise AIProviderError("The AI interview reached its question limit.")
        self._conversation.append(text)
        return self._advance()

    def _advance(self) -> InterviewState:
        response = self._provider.analyze(
            AnalysisRequest(
                self._request.draft,
                tuple(self._conversation),
                self._request.keyframe_paths,
            )
        )
        if isinstance(response, ProviderQuestion):
            self._conversation.append(response.text)
            self._state = InterviewState(tuple(self._conversation), response.text, None, False)
        else:
            self._state = InterviewState(tuple(self._conversation), None, response, True)
        return self._state
