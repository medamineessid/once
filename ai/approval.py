"""Explicit review and approval gate for AI workflow proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from engine.errors import WorkflowValidationError
from engine.replay import ReplayExecutor
from engine.workflow import Workflow, WorkflowRunner

from .models import ProviderDraft


@dataclass(frozen=True)
class WorkflowPreview:
    """Human-readable proposal details shown before approval."""

    goal: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class ApprovedProposal:
    """A proposal that passed validation and explicit user approval."""

    workflow: Workflow
    approved_at: datetime


def preview_proposal(proposal: ProviderDraft) -> WorkflowPreview:
    """Validate and render a proposal without saving or executing it."""
    WorkflowRunner.validate(proposal.workflow)
    replay_preview = ReplayExecutor().preview(proposal.workflow)
    return WorkflowPreview(
        proposal.goal,
        tuple(f"{step_preview} source=AI inference" for step_preview in replay_preview.steps),
    )


def approve_proposal(proposal: ProviderDraft) -> ApprovedProposal:
    """Create the only proposal type accepted by the save/execution boundary."""
    try:
        WorkflowRunner.validate(proposal.workflow)
    except WorkflowValidationError:
        raise
    return ApprovedProposal(proposal.workflow, datetime.now(UTC))
