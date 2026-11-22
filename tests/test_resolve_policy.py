"""Unit tests for the ambiguity and safety policy (written before the code)."""

from __future__ import annotations

from engine.resolve import (
    Candidate,
    Clue,
    ClueKind,
    ResolutionContext,
    ResolutionDecision,
    ResolutionReason,
    SafetyClass,
    TargetDescriptor,
    resolve,
)
from engine.resolve.models import Surface


def _button(candidate_id: str, name: str, *, enabled: bool = True) -> Candidate:
    return Candidate(candidate_id, (Clue(ClueKind.NAME, name, "name"),), enabled=enabled)


def _descriptor(
    name: str,
    *,
    safety: SafetyClass = SafetyClass.REVERSIBLE,
    position_hint: tuple[int, int] | None = None,
) -> TargetDescriptor:
    return TargetDescriptor(
        surface=Surface.WEB,
        clues=(Clue(ClueKind.NAME, name, "name"),),
        safety=safety,
        position_hint=position_hint,
    )


INTERACTIVE = ResolutionContext(unattended=False)
UNATTENDED = ResolutionContext(unattended=True)


def test_one_clear_reversible_winner_is_resolved() -> None:
    result = resolve(_descriptor("Save"), (_button("save", "Save"),), INTERACTIVE)

    assert result.decision is ResolutionDecision.RESOLVED
    assert result.reason is ResolutionReason.SCORE_CLEAR
    assert result.chosen is not None and result.chosen.candidate_id == "save"


def test_equal_candidates_ask_a_person_and_stop_when_unattended() -> None:
    candidates = (_button("a", "Save"), _button("b", "Save"))

    asked = resolve(_descriptor("Save"), candidates, INTERACTIVE)
    stopped = resolve(_descriptor("Save"), candidates, UNATTENDED)

    assert asked.decision is ResolutionDecision.ASK_USER
    assert asked.reason is ResolutionReason.AMBIGUOUS
    assert asked.chosen is None
    assert stopped.decision is ResolutionDecision.STOP
    assert stopped.chosen is None


def test_a_weak_winner_is_not_acted_on() -> None:
    # A contains-match alone is 20 points: below MIN_CONFIDENCE.
    result = resolve(_descriptor("Sav"), (_button("save", "Save now"),), INTERACTIVE)

    assert result.decision is ResolutionDecision.ASK_USER
    assert result.reason is ResolutionReason.LOW_CONFIDENCE


def test_no_candidate_stops_instead_of_guessing() -> None:
    for context in (INTERACTIVE, UNATTENDED):
        result = resolve(_descriptor("Save"), (), context)

        assert result.decision is ResolutionDecision.STOP
        assert result.reason is ResolutionReason.NO_CANDIDATE
        assert result.chosen is None
        assert "could not be found" in result.explanation


def test_a_destructive_step_is_never_auto_picked() -> None:
    strong = _descriptor("Delete", safety=SafetyClass.DESTRUCTIVE)
    candidates = (_button("delete", "Delete"),)

    interactive = resolve(strong, candidates, INTERACTIVE)
    unattended = resolve(strong, candidates, UNATTENDED)

    assert interactive.decision is ResolutionDecision.ASK_USER
    assert interactive.reason is ResolutionReason.DESTRUCTIVE_CONFIRMATION_REQUIRED
    assert interactive.chosen is None
    assert interactive.best is not None and interactive.best.candidate.candidate_id == "delete"
    assert unattended.decision is ResolutionDecision.STOP
    assert unattended.chosen is None


def test_a_destructive_step_with_no_candidate_stops() -> None:
    result = resolve(_descriptor("Delete", safety=SafetyClass.DESTRUCTIVE), (), INTERACTIVE)

    assert result.decision is ResolutionDecision.STOP


def test_a_narrow_gap_is_treated_as_ambiguous() -> None:
    """One candidate shares the label, another the role: a person decides."""
    descriptor = TargetDescriptor(
        surface=Surface.WEB,
        clues=(
            Clue(ClueKind.NAME, "Save", "name"),
            Clue(ClueKind.LABEL_TEXT, "Invoice 7", "label"),
            Clue(ClueKind.ROLE, "button", "role"),
        ),
        safety=SafetyClass.READ_ONLY,
    )
    candidates = (
        Candidate(
            "labelled",
            (
                Clue(ClueKind.NAME, "Save", "name"),
                Clue(ClueKind.LABEL_TEXT, "Invoice 7", "label"),
            ),
        ),
        Candidate(
            "roled",
            (Clue(ClueKind.NAME, "Save", "name"), Clue(ClueKind.ROLE, "button", "role")),
        ),
    )

    result = resolve(descriptor, candidates, INTERACTIVE)

    # 70 (name + label + bonus) versus 60 (name + role + bonus): a gap of 10 is
    # below CLEAR_GAP, so the resolver asks instead of choosing.
    assert result.decision is ResolutionDecision.ASK_USER
    assert result.reason is ResolutionReason.AMBIGUOUS
    assert result.best is not None


def test_duplicates_that_differ_only_by_position_ask_instead_of_picking() -> None:
    """A list where the item moved is not permission to pick the other twin."""
    descriptor = TargetDescriptor(
        surface=Surface.DESKTOP,
        clues=(
            Clue(ClueKind.NAME, "Beta", "name"),
            Clue(ClueKind.ROLE, "list item", "role"),
            Clue(ClueKind.ORDINAL, "1", "ordinal"),
        ),
        safety=SafetyClass.READ_ONLY,
    )
    twins = (
        Candidate(
            "first", (Clue(ClueKind.NAME, "Beta", "name"), Clue(ClueKind.ROLE, "list item", "r"))
        ),
        Candidate(
            "second",
            (
                Clue(ClueKind.NAME, "Beta", "name"),
                Clue(ClueKind.ROLE, "list item", "role"),
                Clue(ClueKind.ORDINAL, "1", "ordinal"),
            ),
        ),
    )

    result = resolve(descriptor, twins, INTERACTIVE)

    assert result.decision is ResolutionDecision.ASK_USER
    assert result.reason is ResolutionReason.AMBIGUOUS


def test_disabled_candidates_are_not_chosen() -> None:
    candidates = (_button("disabled", "Save", enabled=False),)

    result = resolve(_descriptor("Save"), candidates, INTERACTIVE)

    assert result.decision is not ResolutionDecision.RESOLVED
    assert result.chosen is None


def test_explanation_names_the_intent_and_no_internal_identifiers() -> None:
    result = resolve(
        _descriptor("Save", safety=SafetyClass.READ_ONLY),
        (_button("save", "Save"),),
        INTERACTIVE,
        intent="Save the invoice",
    )

    assert "Save the invoice" in result.explanation
    for internal in ("Candidate(", "ClueKind", "SafetyClass", "ResolutionDecision"):
        assert internal not in result.explanation
