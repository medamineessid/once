"""Tests for the safe local recording analysis provider."""

from __future__ import annotations

from ai.models import AnalysisRequest, ProviderDraft
from ai.provider import deterministic_recording_provider
from recorder.drafts import RawDraft, RawDraftAction
from recorder.models import RecordedEventKind


def test_recording_provider_creates_reviewable_observation_steps() -> None:
    draft = RawDraft(
        "capture-1",
        (
            RawDraftAction(1, "Click at (10, 20).", RecordedEventKind.MOUSE_CLICK),
            RawDraftAction(2, "Key press observed.", RecordedEventKind.KEY_PRESS),
        ),
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    assert isinstance(proposal, ProviderDraft)
    assert proposal.workflow.workflow_id == "recording-capture-1"
    assert [step.message for step in proposal.workflow.steps] == [
        "Click at (10, 20).",
        "Key press observed.",
    ]
