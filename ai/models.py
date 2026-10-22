"""Contracts for AI-assisted analysis and interview proposals."""

from __future__ import annotations

from dataclasses import dataclass

from engine.workflow import Workflow
from recorder.drafts import RawDraft


@dataclass(frozen=True)
class AnalysisRequest:
    """Bounded local data supplied to an analysis provider."""

    draft: RawDraft
    conversation: tuple[str, ...] = ()
    keyframe_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderQuestion:
    """A question the UI should present to the user."""

    text: str


@dataclass(frozen=True)
class ProviderDraft:
    """A validated workflow proposal returned by a provider."""

    goal: str
    workflow: Workflow


ProviderResponse = ProviderQuestion | ProviderDraft
