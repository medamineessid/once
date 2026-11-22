"""Score observed candidates against a recorded target descriptor.

Weights are integers so a score can be explained to a person as a sum of
named pieces of evidence. Only the best clue per descriptor group counts, so
clues copied from one node cannot add up; every further independent group that
agrees adds a fixed agreement bonus.
"""

from __future__ import annotations

import math
import unicodedata

from .models import (
    APPSCOPE_KINDS,
    POSITION_HINT_TOLERANCE_PX,
    TEXT_KINDS,
    Candidate,
    Clue,
    ClueKind,
    EvaluatedCandidate,
    TargetDescriptor,
)

#: Points for an exact match of one clue kind.
EXACT_WEIGHTS: dict[ClueKind, int] = {
    ClueKind.AUTOMATION_ID: 50,
    ClueKind.DOM_ID: 50,
    ClueKind.NAME: 35,
    ClueKind.LABEL_TEXT: 25,
    ClueKind.ROLE: 15,
    ClueKind.CONTAINER_TEXT: 15,
    ClueKind.ORDINAL: 10,
    ClueKind.POSITION: 5,
}

#: Points for a partial (contains) match of one human-text clue.
CONTAINS_WEIGHTS: dict[ClueKind, int] = {
    ClueKind.NAME: 20,
    ClueKind.LABEL_TEXT: 15,
    ClueKind.CONTAINER_TEXT: 10,
}

#: Bonus for each additional independent group that also agrees.
AGREEMENT_BONUS = 10


def normalise_text(value: str) -> str:
    """Normalise text for matching only; the original is kept for reports.

    Unicode compatibility forms and accents are folded, case is folded, and
    whitespace is collapsed, so "  Save   Invoice " equals "save invoice".
    Translation is *not* normalised away: "Edit" never matches "Bearbeiten".
    """
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_accents.casefold().split())


def _group_key(clue: Clue) -> str:
    return clue.group or clue.kind.value


def _clue_points(descriptor_clue: Clue, candidate_clue: Clue) -> int:
    """Points this candidate clue earns for one descriptor clue, or 0."""
    if descriptor_clue.kind is not candidate_clue.kind:
        return 0
    expected = normalise_text(descriptor_clue.value)
    actual = normalise_text(candidate_clue.value)
    if not expected or not actual:
        return 0
    if expected == actual:
        return EXACT_WEIGHTS.get(descriptor_clue.kind, 0)
    if descriptor_clue.kind in TEXT_KINDS and expected in actual:
        return CONTAINS_WEIGHTS.get(descriptor_clue.kind, 0)
    return 0


def _app_scope_disagrees(descriptor: TargetDescriptor, candidate: Candidate) -> bool:
    """True when the candidate provably belongs to another app or site."""
    for kind in APPSCOPE_KINDS:
        expected = {normalise_text(clue.value) for clue in descriptor.clues if clue.kind is kind}
        actual = {normalise_text(clue.value) for clue in candidate.clues if clue.kind is kind}
        if expected and actual and not (expected & actual):
            return True
    return False


def _position_bonus(descriptor: TargetDescriptor, candidate: Candidate, score: int) -> int:
    """A recorded point may break a tie, never make a match on its own."""
    if score <= 0 or descriptor.position_hint is None or candidate.position is None:
        return 0
    expected_x, expected_y = descriptor.position_hint
    actual_x, actual_y = candidate.position
    distance = math.hypot(actual_x - expected_x, actual_y - expected_y)
    if distance > POSITION_HINT_TOLERANCE_PX:
        return 0
    return EXACT_WEIGHTS[ClueKind.POSITION]


def _score_one(descriptor: TargetDescriptor, candidate: Candidate) -> EvaluatedCandidate:
    best_per_group: dict[str, int] = {}
    kinds_per_group: dict[str, ClueKind] = {}
    for descriptor_clue in descriptor.clues:
        if descriptor_clue.kind in APPSCOPE_KINDS:
            continue
        points = max(
            (_clue_points(descriptor_clue, candidate_clue) for candidate_clue in candidate.clues),
            default=0,
        )
        if points <= 0:
            continue
        group = _group_key(descriptor_clue)
        if points > best_per_group.get(group, 0):
            best_per_group[group] = points
            kinds_per_group[group] = descriptor_clue.kind
    matched_groups = len(best_per_group)
    semantic = sum(best_per_group.values())
    score = semantic + max(0, matched_groups - 1) * AGREEMENT_BONUS
    score += _position_bonus(descriptor, candidate, semantic)
    return EvaluatedCandidate(
        candidate=candidate,
        score=score,
        matched_groups=matched_groups,
        matched_kinds=tuple(kinds_per_group[group] for group in sorted(best_per_group)),
    )


def score_candidates(
    descriptor: TargetDescriptor, candidates: tuple[Candidate, ...]
) -> tuple[EvaluatedCandidate, ...]:
    """Return every plausible candidate, best first, in a deterministic order."""
    scored = [
        _score_one(descriptor, candidate)
        for candidate in candidates
        if not _app_scope_disagrees(descriptor, candidate)
    ]
    scored.sort(key=lambda entry: (-entry.score, entry.candidate.candidate_id))
    return tuple(scored)
