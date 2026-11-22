"""Immutable value types for target resolution.

This package is deliberately pure: it imports nothing from ``engine`` runtime
code, never touches the filesystem, the OS, Qt or the network. It scores
candidate elements that an adapter *observed* and decides whether an action may
be taken, must be confirmed by a person, or must stop.

See ``docs/SMART_REPLAY.md`` for the design this implements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

#: A candidate must reach this score before any action may be taken.
MIN_CONFIDENCE = 30
#: The winner must beat the runner-up by at least this many points.
CLEAR_GAP = 20
#: A recorded point may only break a tie between candidates that already
#: matched on a semantic clue, and only within this distance in pixels.
POSITION_HINT_TOLERANCE_PX = 50


class Surface(StrEnum):
    """Which provider family may answer a resolution request."""

    WEB = "WEB"
    DESKTOP = "DESKTOP"


class ClueKind(StrEnum):
    """Independent kinds of evidence about a target element."""

    DOM_ID = "DOM_ID"
    AUTOMATION_ID = "AUTOMATION_ID"
    ROLE = "ROLE"
    NAME = "NAME"
    LABEL_TEXT = "LABEL_TEXT"
    CONTAINER_TEXT = "CONTAINER_TEXT"
    DOMAIN = "DOMAIN"
    PROCESS = "PROCESS"
    ORDINAL = "ORDINAL"
    POSITION = "POSITION"


#: Clues that identify the application; a mismatch disqualifies a candidate.
APPSCOPE_KINDS: frozenset[ClueKind] = frozenset({ClueKind.DOMAIN, ClueKind.PROCESS})

#: Clues whose values are human text and are compared after normalisation.
TEXT_KINDS: frozenset[ClueKind] = frozenset(
    {ClueKind.NAME, ClueKind.LABEL_TEXT, ClueKind.CONTAINER_TEXT}
)


class SafetyClass(StrEnum):
    """What an action can do to the user's data, set by the approved workflow."""

    READ_ONLY = "READ_ONLY"
    REVERSIBLE = "REVERSIBLE"
    DESTRUCTIVE = "DESTRUCTIVE"


class ResolutionDecision(StrEnum):
    """What the resolver allows to happen next."""

    RESOLVED = "RESOLVED"
    ASK_USER = "ASK_USER"
    STOP = "STOP"


class ResolutionReason(StrEnum):
    """Why the resolver reached its decision (data, not UI text)."""

    SCORE_CLEAR = "SCORE_CLEAR"
    AMBIGUOUS = "AMBIGUOUS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NO_CANDIDATE = "NO_CANDIDATE"
    DESTRUCTIVE_CONFIRMATION_REQUIRED = "DESTRUCTIVE_CONFIRMATION_REQUIRED"


@dataclass(frozen=True)
class Clue:
    """One piece of evidence, tagged with the source group it came from.

    ``group`` marks where the value was read from. Clues sharing a group are
    treated as one piece of evidence, so copying five clues out of a single DOM
    node cannot inflate a candidate's score.
    """

    kind: ClueKind
    value: str
    group: str


@dataclass(frozen=True)
class Candidate:
    """One element an adapter observed on the live surface."""

    candidate_id: str
    clues: tuple[Clue, ...]
    ordinal: int = 0
    enabled: bool = True
    position: tuple[int, int] | None = None

    @property
    def label(self) -> str:
        """Return the most human-meaningful description of this candidate."""
        for kind in (ClueKind.NAME, ClueKind.LABEL_TEXT, ClueKind.AUTOMATION_ID, ClueKind.DOM_ID):
            for clue in self.clues:
                if clue.kind is kind and clue.value.strip():
                    return clue.value.strip()
        return "the element"


@dataclass(frozen=True)
class TargetDescriptor:
    """What a recorded step meant, expressed as independent clues."""

    surface: Surface
    clues: tuple[Clue, ...]
    safety: SafetyClass
    position_hint: tuple[int, int] | None = None


@dataclass(frozen=True)
class ResolutionContext:
    """Who is watching the run, which decides whether asking is possible."""

    unattended: bool = False


@dataclass(frozen=True)
class EvaluatedCandidate:
    """One candidate with its score and the evidence that produced it.

    ``score`` orders candidates and includes positional evidence.
    ``identity_score`` counts only identity evidence (id, name, label, container,
    role); the clear-gap decision uses it so that a mere position cannot make a
    candidate look decisively better than its twin.
    """

    candidate: Candidate
    score: int
    identity_score: int
    matched_groups: int
    matched_kinds: tuple[ClueKind, ...] = ()


@dataclass(frozen=True)
class Resolution:
    """The resolver's decision plus everything needed to explain it."""

    decision: ResolutionDecision
    reason: ResolutionReason
    explanation: str
    chosen: Candidate | None = None
    best: EvaluatedCandidate | None = None
    evaluated: tuple[EvaluatedCandidate, ...] = field(default_factory=tuple)

    @property
    def may_act(self) -> bool:
        """True only when the caller is allowed to perform the action."""
        return self.decision is ResolutionDecision.RESOLVED and self.chosen is not None
