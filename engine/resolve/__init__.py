"""Pure, OS-free target resolution for smart replay.

``resolve()`` scores independently-recorded clues against the candidates an
adapter observed and returns one of three decisions: RESOLVED (act),
ASK_USER (a person confirms) or STOP (do nothing). It never guesses, never
auto-picks a destructive step, and never reads coordinates as a primary clue.
"""

from __future__ import annotations

from .models import (
    CLEAR_GAP,
    MIN_CONFIDENCE,
    Candidate,
    Clue,
    ClueKind,
    EvaluatedCandidate,
    Resolution,
    ResolutionContext,
    ResolutionDecision,
    ResolutionReason,
    SafetyClass,
    Surface,
    TargetDescriptor,
)
from .resolver import resolve
from .scoring import normalise_text, score_candidates

__all__ = [
    "CLEAR_GAP",
    "MIN_CONFIDENCE",
    "Candidate",
    "Clue",
    "ClueKind",
    "EvaluatedCandidate",
    "Resolution",
    "ResolutionContext",
    "ResolutionDecision",
    "ResolutionReason",
    "SafetyClass",
    "Surface",
    "TargetDescriptor",
    "normalise_text",
    "resolve",
    "score_candidates",
]
