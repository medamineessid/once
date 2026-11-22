"""Decide what may happen: act, ask a person, or stop safely.

The rules here are the safety contract of smart replay (docs/SMART_REPLAY.md
§6, §10). They are deliberately boring and total: every combination of scores,
safety class and attendance produces exactly one decision, and the only input
that can produce ``RESOLVED`` is a reversible-or-read-only step with a single
clear winner.
"""

from __future__ import annotations

from .models import (
    CLEAR_GAP,
    MIN_CONFIDENCE,
    EvaluatedCandidate,
    Resolution,
    ResolutionContext,
    ResolutionDecision,
    ResolutionReason,
    SafetyClass,
    TargetDescriptor,
)


def _step_name(intent: str) -> str:
    """Quote the user's intent for an explanation, or say "the target".

    Plain ASCII quotes: the same sentence is logged to a UTF-8 file, printed on
    a console and persisted, and typographic quotes have already turned into
    replacement characters on a cp1252 console.
    """
    cleaned = intent.strip()
    return f'"{cleaned}"' if cleaned else "the target"


def _explain(
    decision: ResolutionDecision,
    reason: ResolutionReason,
    *,
    best: EvaluatedCandidate | None,
    second_score: int | None,
    intent: str,
) -> str:
    name = _step_name(intent)
    if reason is ResolutionReason.NO_CANDIDATE:
        return f"Nothing was clicked: {name} could not be found in the current view."
    if reason is ResolutionReason.DESTRUCTIVE_CONFIRMATION_REQUIRED:
        return (
            f"Once needs confirmation first: {name} deletes or changes data, "
            "so it is never chosen automatically."
        )
    if reason is ResolutionReason.LOW_CONFIDENCE and best is not None:
        return (
            f"Once did not act: {name} was only a partial match "
            f"(score {best.identity_score}, needed {MIN_CONFIDENCE})."
        )
    if reason is ResolutionReason.AMBIGUOUS and best is not None:
        return (
            f"Once needs a person to choose: {name} matched more than one element "
            f"(best score {best.identity_score}, next candidate {second_score})."
        )
    if best is not None:
        return (
            f"Found {best.candidate.label} for {name} "
            f"(score {best.identity_score}, next candidate {second_score or 0})."
        )
    # Unreachable in practice; kept so a bug cannot silently produce a success.
    return f"Once did not act on {name}."


def decide(
    evaluated: tuple[EvaluatedCandidate, ...],
    descriptor: TargetDescriptor,
    context: ResolutionContext,
    *,
    intent: str = "",
) -> Resolution:
    """Return the one decision the evidence and the safety class allow."""
    usable = tuple(entry for entry in evaluated if entry.candidate.enabled)
    if not usable:
        return Resolution(
            decision=ResolutionDecision.STOP,
            reason=ResolutionReason.NO_CANDIDATE,
            explanation=_explain(
                ResolutionDecision.STOP,
                ResolutionReason.NO_CANDIDATE,
                best=None,
                second_score=None,
                intent=intent,
            ),
            evaluated=evaluated,
        )

    best = usable[0]
    second = usable[1] if len(usable) > 1 else None
    # Ordering may use position; the decision may not. Two identical rows differ
    # only by ordinal, and that must ask rather than pick.
    second_score = second.identity_score if second is not None else None
    confident = best.identity_score >= MIN_CONFIDENCE
    gap_clear = second is None or (best.identity_score - second.identity_score) >= CLEAR_GAP
    clear_winner = confident and gap_clear

    if descriptor.safety is SafetyClass.DESTRUCTIVE:
        reason = ResolutionReason.DESTRUCTIVE_CONFIRMATION_REQUIRED
        decision = ResolutionDecision.STOP if context.unattended else ResolutionDecision.ASK_USER
        return Resolution(
            decision=decision,
            reason=reason,
            explanation=_explain(
                decision, reason, best=best, second_score=second_score, intent=intent
            ),
            best=best,
            evaluated=evaluated,
        )

    if clear_winner:
        return Resolution(
            decision=ResolutionDecision.RESOLVED,
            reason=ResolutionReason.SCORE_CLEAR,
            explanation=_explain(
                ResolutionDecision.RESOLVED,
                ResolutionReason.SCORE_CLEAR,
                best=best,
                second_score=second_score,
                intent=intent,
            ),
            chosen=best.candidate,
            best=best,
            evaluated=evaluated,
        )

    reason = ResolutionReason.AMBIGUOUS if confident else ResolutionReason.LOW_CONFIDENCE
    decision = ResolutionDecision.STOP if context.unattended else ResolutionDecision.ASK_USER
    return Resolution(
        decision=decision,
        reason=reason,
        explanation=_explain(decision, reason, best=best, second_score=second_score, intent=intent),
        best=best,
        evaluated=evaluated,
    )
