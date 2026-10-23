"""Pure review types and the explicit approval gate for agent changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from engine.errors import WorkflowValidationError

MAX_DIFF_CHARS: Final = 100_000
MAX_FILES: Final = 500


@dataclass(frozen=True)
class ChangeReview:
    """The reviewed, bounded diff an agent created on its separate branch."""

    proposal_id: str
    repo_path: str
    base_branch: str
    agent_branch: str
    base_commit: str
    agent_tip: str
    diff: str
    changed_files: tuple[str, ...]
    untracked_files: tuple[str, ...]
    truncated: bool

    def summary(self) -> str:
        """Return plain-language notes for the review screen."""
        count = len(self.changed_files)
        notes = []
        if count == 1:
            notes.append("The agent proposed changes to 1 file.")
        else:
            notes.append(f"The agent proposed changes to {count} files.")
        if self.untracked_files:
            notes.append(
                f"{len(self.untracked_files)} new file(s) are listed but not shown in the diff."
            )
        if self.truncated:
            notes.append("The diff is large and was shortened for display.")
        return "\n".join(notes)


@dataclass(frozen=True)
class ApprovedChange:
    """An agent change that passed the explicit approval gate.

    Constructible only through `approve_change`; the merge boundary accepts
    only this type.
    """

    proposal_id: str
    review: ChangeReview
    approved_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.review, ChangeReview):
            raise WorkflowValidationError("Only a reviewed change can be approved.")


def approve_change(review: object) -> ApprovedChange:
    """Create the only change type the merge boundary will apply."""
    if not isinstance(review, ChangeReview):
        raise WorkflowValidationError("Only a real review can be approved.")
    return ApprovedChange(review.proposal_id, review, datetime.now(UTC).isoformat())
