"""B3: a proposal preview must speak the same policy as the desktop gate.

`preview_proposal` used a bare `ReplayExecutor()` (read-only policy), so a
desktop automation the approval panel would happily gate was previewed as
UNSUPPORTED. It now previews with `DESKTOP_INTERACTION_POLICY` - the same
object `approve_desktop_workflow` validates with - and still executes nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from ai.approval import preview_proposal
from ai.models import ProviderDraft
from engine.errors import WorkflowValidationError
from engine.replay import DESKTOP_INTERACTION_POLICY, READ_ONLY_POLICY
from engine.workflow import StepKind, Workflow, WorkflowStep

APP_TARGET = json.dumps({"executable": str(sys.executable)})


WINDOW = {"title": "Once demo", "class_name": "DemoWindowClass"}
ELEMENT = {"class_name": "DemoEditClass", "control_type": "Edit"}

#: One valid, bounded target for each kind these tests exercise.
VALID_TARGETS: dict[StepKind, str] = {
    StepKind.VERIFY_PATH_EXISTS: "C:/work/result.txt",
    StepKind.INSPECT_PATH: "C:/work/result.txt",
    StepKind.VERIFY_FILE_TEXT: json.dumps({"path": "C:/work/result.txt", "contains": "invoice"}),
    StepKind.LAUNCH_APPLICATION: APP_TARGET,
    StepKind.TYPE_TEXT: json.dumps({"window": WINDOW, "element": ELEMENT, "text": "hello"}),
}


def proposal_of(*steps: WorkflowStep) -> ProviderDraft:
    return ProviderDraft("Recorded goal", Workflow("proposal", "Proposal", steps))


def step_of(kind: StepKind, *, step_id: str = "s") -> WorkflowStep:
    return WorkflowStep(step_id, kind.value, kind, "Expected outcome.", VALID_TARGETS.get(kind))


def permissions(preview_steps: tuple[str, ...]) -> list[str]:
    return [text.split("permission=", 1)[1].split(" ", 1)[0] for text in preview_steps]


@pytest.mark.parametrize("kind", sorted(VALID_TARGETS))
def test_every_previewed_kind_is_allowed_exactly_when_the_gate_allows_it(
    kind: StepKind,
) -> None:
    preview = preview_proposal(proposal_of(step_of(kind)))

    expected = "ALLOWED" if kind in DESKTOP_INTERACTION_POLICY.allowed_kinds else "UNSUPPORTED"
    assert permissions(preview.steps) == [expected]


def test_the_preview_now_follows_the_desktop_policy_not_the_read_only_one() -> None:
    assert StepKind.LAUNCH_APPLICATION in DESKTOP_INTERACTION_POLICY.allowed_kinds
    assert StepKind.LAUNCH_APPLICATION not in READ_ONLY_POLICY.allowed_kinds

    preview = preview_proposal(proposal_of(step_of(StepKind.LAUNCH_APPLICATION)))

    assert permissions(preview.steps) == ["ALLOWED"]


def test_a_read_only_proposal_needs_no_desktop_approval() -> None:
    preview = preview_proposal(proposal_of(step_of(StepKind.VERIFY_PATH_EXISTS)))

    assert preview.needs_desktop_approval is False


def test_a_mutating_proposal_says_desktop_approval_is_required() -> None:
    preview = preview_proposal(proposal_of(step_of(StepKind.TYPE_TEXT)))

    assert permissions(preview.steps) == ["ALLOWED"]
    assert preview.needs_desktop_approval is True


@pytest.mark.parametrize("kind", [StepKind.FAIL, StepKind.REPORT])
def test_a_kind_outside_the_gate_policy_stays_unsupported(kind: StepKind) -> None:
    preview = preview_proposal(proposal_of(step_of(kind)))

    assert permissions(preview.steps) == ["UNSUPPORTED"]
    assert preview.needs_desktop_approval is False


def test_previewing_a_launch_starts_no_process(monkeypatch) -> None:
    """Previewing must never execute: no Popen, no window, no provider."""

    def must_not_launch(*args: object, **kwargs: object) -> subprocess.Popen:
        raise AssertionError("preview_proposal must never start a process")

    monkeypatch.setattr(subprocess, "Popen", must_not_launch)

    preview = preview_proposal(proposal_of(step_of(StepKind.LAUNCH_APPLICATION)))

    assert permissions(preview.steps) == ["ALLOWED"]
    assert preview.steps[0].endswith("source=AI inference")


def test_an_invalid_proposal_is_rejected_before_any_preview() -> None:
    draft = proposal_of(
        step_of(StepKind.REPORT, step_id="dup"), step_of(StepKind.REPORT, step_id="dup")
    )

    with pytest.raises(WorkflowValidationError):
        preview_proposal(draft)
