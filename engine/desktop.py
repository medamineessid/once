"""Explicit approval gate for desktop-automation workflows.

A workflow that contains desktop-mutating steps becomes runnable only through
a `DesktopApproval` produced by `approve_desktop_workflow`. The gate reuses the
same policy allowlist that the executor applies at runtime, so approval and
execution cannot disagree about which step kinds are permitted, and no other
code path can construct the approval type.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from engine.errors import WorkflowValidationError
from engine.replay import (
    DESKTOP_INTERACTION_POLICY,
    MUTATING_DESKTOP_KINDS,
    ReplayExecutor,
    ReplayPolicy,
)
from engine.workflow import MAX_WORKFLOW_STEPS, StepKind, Workflow

MAX_DESKTOP_STEPS = 20

#: Policy used at desktop approval and execution time: allows all desktop/read
#: steps plus non-executing REPORT observation steps so recorded drafts with
#: observation-only steps can run and report PARTIALLY_PERFORMED honestly.
DESKTOP_EXECUTION_POLICY = ReplayPolicy(
    allowed_kinds=DESKTOP_INTERACTION_POLICY.allowed_kinds | frozenset({StepKind.REPORT}),
    max_steps=MAX_WORKFLOW_STEPS,
)


@dataclass(frozen=True)
class DesktopApproval:
    """A human-approved desktop workflow; the only input the executor accepts."""

    workflow: Workflow
    approved_at: datetime


def approve_desktop_workflow(
    workflow: Workflow, *, allow_observations: bool = False
) -> DesktopApproval:
    """Validate and approve one desktop workflow for exactly these steps."""
    if not isinstance(workflow, Workflow):
        raise WorkflowValidationError("Only a real desktop workflow can be approved.")
    policy = DESKTOP_EXECUTION_POLICY if allow_observations else DESKTOP_INTERACTION_POLICY
    executor = ReplayExecutor(policy)
    executor.validate(workflow)
    return DesktopApproval(workflow, datetime.now(UTC))


def mutating_kind_names(workflow: Workflow) -> tuple[str, ...]:
    """Return the mutating step kinds a desktop workflow contains, for the UI."""
    return tuple(step.kind.value for step in workflow.steps if step.kind in MUTATING_DESKTOP_KINDS)


def requires_desktop_approval(workflow: Workflow) -> bool:
    """True when any step mutates the desktop instead of only inspecting it."""
    return any(
        isinstance(step.kind, StepKind) and step.kind in MUTATING_DESKTOP_KINDS
        for step in workflow.steps
    )
