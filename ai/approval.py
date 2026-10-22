"""Explicit review and approval gate for AI workflow proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from engine.errors import WorkflowValidationError
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
    return WorkflowPreview(
        proposal.goal,
        tuple(
            f"{step.step_id}: {step.name} [{step.kind.value}] "
            f"target={step.target or 'none'} attempts={step.max_attempts} "
            f"postcondition={step.postcondition.value if step.postcondition else 'none'}"
            for step in proposal.workflow.steps
        ),
    )


def approve_proposal(proposal: ProviderDraft) -> ApprovedProposal:
    """Create the only proposal type accepted by the save/execution boundary."""
    try:
        WorkflowRunner.validate(proposal.workflow)
    except WorkflowValidationError:
        raise
    return ApprovedProposal(proposal.workflow, datetime.now(UTC))
