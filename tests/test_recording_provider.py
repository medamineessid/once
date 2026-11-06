"""Tests for the safe local recording analysis provider."""

from __future__ import annotations

import json

from ai.models import AnalysisRequest, ProviderDraft
from ai.provider import deterministic_recording_provider
from engine.workflow import StepKind, WorkflowRunner
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


def _draft(actions: tuple[RawDraftAction, ...]) -> RawDraft:
    return RawDraft("capture-2", actions)


def test_window_observations_map_to_launch_and_close_steps() -> None:
    draft = _draft(
        (
            RawDraftAction(
                1,
                "A Code.exe window opened: Visual Studio Code.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="Code.exe",
                window_title="Visual Studio Code",
            ),
            RawDraftAction(
                2,
                "The Code.exe window closed: Visual Studio Code.",
                RecordedEventKind.WINDOW_CLOSE,
                process_name="Code.exe",
                window_title="Visual Studio Code",
            ),
        )
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    kinds = [step.kind for step in proposal.workflow.steps]
    targets = [step.target for step in proposal.workflow.steps]
    assert kinds == [StepKind.LAUNCH_APPLICATION, StepKind.CLOSE_APPLICATION]
    assert json.loads(targets[0]) == {"application": "vscode"}
    assert json.loads(targets[1]) == {"application": "vscode"}


def test_charmap_window_observations_map_to_launch_and_close_steps() -> None:
    """Classic unpackaged apps like charmap give a launch pid that owns its windows."""
    draft = _draft(
        (
            RawDraftAction(
                1,
                "A charmap.exe window opened: Table des caractères.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="charmap.exe",
                window_title="Table des caractères",
            ),
            RawDraftAction(
                2,
                "The charmap.exe window closed: Table des caractères.",
                RecordedEventKind.WINDOW_CLOSE,
                process_name="charmap.exe",
                window_title="Table des caractères",
            ),
        )
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    kinds = [step.kind for step in proposal.workflow.steps]
    targets = [step.target for step in proposal.workflow.steps]
    assert kinds == [StepKind.LAUNCH_APPLICATION, StepKind.CLOSE_APPLICATION]
    assert json.loads(targets[0]) == {"application": "charmap"}
    assert json.loads(targets[1]) == {"application": "charmap"}
    WorkflowRunner.validate(proposal.workflow)


def test_unknown_processes_stay_report_observations() -> None:
    draft = _draft(
        (
            RawDraftAction(
                1,
                "A spotify.exe window opened: Spotify.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="spotify.exe",
                window_title="Spotify",
            ),
        )
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    kinds = [step.kind for step in proposal.workflow.steps]
    assert kinds == [StepKind.REPORT]


def test_close_without_a_launch_stays_a_report() -> None:
    draft = _draft(
        (
            RawDraftAction(
                1,
                "The Code.exe window closed: Visual Studio Code.",
                RecordedEventKind.WINDOW_CLOSE,
                process_name="Code.exe",
                window_title="Visual Studio Code",
            ),
        )
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    step = proposal.workflow.steps[0]
    assert step.kind is StepKind.REPORT
    assert "does not launch" in step.message


def test_repeated_launches_collapse_into_one_launch() -> None:
    draft = _draft(
        (
            RawDraftAction(
                1,
                "A Code.exe window opened: Visual Studio Code.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="Code.exe",
                window_title="Visual Studio Code",
            ),
            RawDraftAction(
                2,
                "A Code.exe window opened: another window.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="Code.exe",
                window_title="another window",
            ),
        )
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    kinds = [step.kind for step in proposal.workflow.steps]
    assert kinds == [StepKind.LAUNCH_APPLICATION, StepKind.REPORT]
