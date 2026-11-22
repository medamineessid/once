"""Unit tests for clue scoring in the pure resolver.

Written before ``engine/resolve`` existed; every test here must fail with an
import error until the package is implemented.
"""

from __future__ import annotations

from engine.resolve import (
    Candidate,
    Clue,
    ClueKind,
    SafetyClass,
    TargetDescriptor,
    score_candidates,
)
from engine.resolve.models import Surface


def _descriptor(*clues: Clue, safety: SafetyClass = SafetyClass.REVERSIBLE) -> TargetDescriptor:
    return TargetDescriptor(surface=Surface.WEB, clues=clues, safety=safety)


def test_exact_id_scores_highest_and_matches_the_right_candidate() -> None:
    descriptor = _descriptor(
        Clue(ClueKind.DOM_ID, "save-invoice", "id"),
        Clue(ClueKind.ROLE, "button", "role"),
        Clue(ClueKind.NAME, "Save", "name"),
    )
    candidates = (
        Candidate("right", (Clue(ClueKind.DOM_ID, "save-invoice", "id"),)),
        Candidate("wrong", (Clue(ClueKind.DOM_ID, "cancel-invoice", "id"),)),
    )

    scored = score_candidates(descriptor, candidates)

    assert scored[0].candidate.candidate_id == "right"
    assert scored[0].score >= 50


def test_candidate_with_no_matching_clue_scores_zero() -> None:
    descriptor = _descriptor(Clue(ClueKind.NAME, "Save", "name"))
    candidates = (Candidate("other", (Clue(ClueKind.NAME, "Delete", "name"),)),)

    scored = score_candidates(descriptor, candidates)

    assert scored[0].score == 0
    assert scored[0].matched_groups == 0


def test_name_matching_is_normalised_for_case_and_whitespace() -> None:
    descriptor = _descriptor(Clue(ClueKind.NAME, "  Save   Invoice ", "name"))
    candidates = (Candidate("save", (Clue(ClueKind.NAME, "save invoice", "name"),)),)

    scored = score_candidates(descriptor, candidates)

    assert scored[0].score == 35


def test_two_clues_from_the_same_group_count_once() -> None:
    """Clues copied from one node are one piece of evidence, not two."""
    descriptor = _descriptor(
        Clue(ClueKind.NAME, "Save", "name"),
        Clue(ClueKind.NAME, "Save invoice", "name"),
    )
    candidates = (Candidate("save", (Clue(ClueKind.NAME, "Save", "name"),)),)

    scored = score_candidates(descriptor, candidates)

    assert scored[0].score == 35
    assert scored[0].matched_groups == 1


def test_independent_groups_add_an_agreement_bonus() -> None:
    descriptor = _descriptor(
        Clue(ClueKind.NAME, "Save", "name"),
        Clue(ClueKind.ROLE, "button", "role"),
        Clue(ClueKind.LABEL_TEXT, "Invoice 7", "label"),
    )
    candidates = (
        Candidate(
            "save",
            (
                Clue(ClueKind.NAME, "Save", "name"),
                Clue(ClueKind.ROLE, "button", "role"),
                Clue(ClueKind.LABEL_TEXT, "Invoice 7", "label"),
            ),
        ),
    )

    scored = score_candidates(descriptor, candidates)

    # 35 (name) + 15 (role) + 25 (label) + 2 * 10 (two extra independent groups)
    assert scored[0].score == 95
    assert scored[0].matched_groups == 3


def test_candidate_in_another_domain_is_discarded() -> None:
    descriptor = TargetDescriptor(
        surface=Surface.WEB,
        clues=(Clue(ClueKind.NAME, "Save", "name"), Clue(ClueKind.DOMAIN, "example.com", "app")),
        safety=SafetyClass.REVERSIBLE,
    )
    candidates = (
        Candidate("ours", (Clue(ClueKind.NAME, "Save", "name"),)),
        Candidate(
            "advert",
            (Clue(ClueKind.NAME, "Save", "name"), Clue(ClueKind.DOMAIN, "ads.example.net", "app")),
        ),
    )

    scored = score_candidates(descriptor, candidates)

    assert [entry.candidate.candidate_id for entry in scored] == ["ours"]


def test_position_hint_only_breaks_a_tie_between_otherwise_equal_candidates() -> None:
    descriptor = TargetDescriptor(
        surface=Surface.WEB,
        clues=(Clue(ClueKind.ROLE, "button", "role"),),
        safety=SafetyClass.READ_ONLY,
        position_hint=(10, 10),
    )
    candidates = (
        Candidate("near", (Clue(ClueKind.ROLE, "button", "role"),), position=(12, 14)),
        Candidate("far", (Clue(ClueKind.ROLE, "button", "role"),), position=(400, 600)),
    )

    scored = score_candidates(descriptor, candidates)

    assert scored[0].candidate.candidate_id == "near"
    assert scored[0].score - scored[1].score == 5


def test_position_never_creates_a_candidate_that_matched_nothing() -> None:
    descriptor = TargetDescriptor(
        surface=Surface.WEB,
        clues=(Clue(ClueKind.NAME, "Save", "name"),),
        safety=SafetyClass.READ_ONLY,
        position_hint=(0, 0),
    )
    candidates = (Candidate("only", (Clue(ClueKind.ROLE, "button", "role"),), position=(0, 0)),)

    scored = score_candidates(descriptor, candidates)

    assert scored[0].score == 0


def test_a_candidate_in_a_different_row_is_discarded() -> None:
    """A shared button name inside another invoice is the wrong row, not a tie."""
    descriptor = _descriptor(
        Clue(ClueKind.NAME, "Edit", "name"),
        Clue(ClueKind.CONTAINER_TEXT, "Invoice 1042", "container"),
    )
    candidates = (
        Candidate(
            "wanted",
            (
                Clue(ClueKind.NAME, "Edit", "name"),
                Clue(ClueKind.CONTAINER_TEXT, "Invoice 1042", "container"),
            ),
        ),
        Candidate(
            "other-row",
            (
                Clue(ClueKind.NAME, "Edit", "name"),
                Clue(ClueKind.CONTAINER_TEXT, "Invoice 1099", "container"),
            ),
        ),
    )

    scored = score_candidates(descriptor, candidates)

    assert [entry.candidate.candidate_id for entry in scored] == ["wanted"]


def test_a_role_and_ordinal_alone_are_not_identity_evidence() -> None:
    """Position may order candidates but must never make one look identified."""
    descriptor = _descriptor(
        Clue(ClueKind.ROLE, "button", "role"), Clue(ClueKind.ORDINAL, "1", "ordinal")
    )
    candidates = (
        Candidate(
            "second",
            (Clue(ClueKind.ROLE, "button", "role"), Clue(ClueKind.ORDINAL, "1", "ordinal")),
        ),
    )

    scored = score_candidates(descriptor, candidates)

    assert scored[0].score > 0
    assert scored[0].identity_score == 15


def test_a_name_clue_never_matches_a_different_translation() -> None:
    descriptor = _descriptor(Clue(ClueKind.NAME, "Edit", "name"))
    candidates = (Candidate("german", (Clue(ClueKind.NAME, "Bearbeiten", "name"),)),)

    scored = score_candidates(descriptor, candidates)

    assert scored[0].score == 0
