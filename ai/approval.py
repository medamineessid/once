"""Explicit review and approval gate for AI workflow proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from engine.desktop import requires_desktop_approval
from engine.errors import WorkflowValidationError
from engine.replay import DESKTOP_INTERACTION_POLICY, ReplayExecutor
from engine.workflow import Workflow, WorkflowRunner

from .models import ProviderDraft


@dataclass(frozen=True)
class WorkflowPreview:
    """Human-readable proposal details shown before approval."""

    goal: str
    steps: tuple[str, ...]
    #: True when the previewed steps need the desktop approval gate before running.
    needs_desktop_approval: bool = False


@dataclass(frozen=True)
class ApprovedProposal:
    """A proposal that passed validation and explicit user approval."""

    workflow: Workflow
    approved_at: datetime


def preview_proposal(proposal: ProviderDraft) -> WorkflowPreview:
    """Validate and render a proposal without saving or executing it.

    The preview uses the same policy object as the desktop approval gate
    (`engine.replay.DESKTOP_INTERACTION_POLICY`), so what a reviewer is shown as
    allowed is exactly what the gate would allow. It still runs nothing: no
    provider, no popen, no window; approval remains a separate, explicit step.
    """
    WorkflowRunner.validate(proposal.workflow)
    replay_preview = ReplayExecutor(DESKTOP_INTERACTION_POLICY).preview(proposal.workflow)
    return WorkflowPreview(
        proposal.goal,
        tuple(f"{step_preview} source=AI inference" for step_preview in replay_preview.steps),
        needs_desktop_approval=requires_desktop_approval(proposal.workflow),
    )


def approve_proposal(proposal: ProviderDraft) -> ApprovedProposal:
    """Create the only proposal type accepted by the save/execution boundary."""
    try:
        WorkflowRunner.validate(proposal.workflow)
    except WorkflowValidationError:
        raise
    return ApprovedProposal(proposal.workflow, datetime.now(UTC))
