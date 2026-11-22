"""Entry point for one resolution: score the candidates, then decide."""

from __future__ import annotations

from .models import (
    Candidate,
    Resolution,
    ResolutionContext,
    ResolutionDecision,
    TargetDescriptor,
)
from .policy import decide
from .scoring import score_candidates


def resolve(
    descriptor: TargetDescriptor,
    candidates: tuple[Candidate, ...],
    context: ResolutionContext,
    *,
    intent: str = "",
) -> Resolution:
    """Return the resolution for one step against the currently observed surface.

    The caller (an adapter-driven engine) performs the action only when
    ``resolution.may_act`` is true, and reports ``resolution.explanation``
    unchanged so the run report and the Activity page say the same thing.
    """
    evaluated = score_candidates(descriptor, candidates)
    resolution = decide(evaluated, descriptor, context, intent=intent)
    if resolution.decision is ResolutionDecision.RESOLVED and resolution.chosen is None:
        raise AssertionError("A resolved decision must carry the chosen candidate.")
    return resolution
