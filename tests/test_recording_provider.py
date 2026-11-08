"""Tests for the safe local recording analysis provider."""

from __future__ import annotations

import json

from ai.models import AnalysisRequest, ProviderDraft
from ai.provider import deterministic_recording_provider
from engine.workflow import StepKind, WorkflowRunner
from recorder.drafts import RawDraft, RawDraftAction, build_raw_draft
from recorder.models import RecordedEvent, RecordedEventKind, Recording, UIElementInfo


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
    exe = r"C:\Program Files\Example\app.exe"
    draft = _draft(
        (
            RawDraftAction(
                1,
                "An app.exe window opened: Example App.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="app.exe",
                window_title="Example App",
                executable_path=exe,
            ),
            RawDraftAction(
                2,
                "The app.exe window closed: Example App.",
                RecordedEventKind.WINDOW_CLOSE,
                process_name="app.exe",
                window_title="Example App",
                executable_path=exe,
            ),
        )
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    kinds = [step.kind for step in proposal.workflow.steps]
    targets = [step.target for step in proposal.workflow.steps]
    assert kinds == [StepKind.LAUNCH_APPLICATION, StepKind.CLOSE_APPLICATION]
    assert json.loads(targets[0]) == {"executable": exe}
    assert json.loads(targets[1]) == {"executable": exe}


def test_unknown_processes_stay_report_observations() -> None:
    draft = _draft(
        (
            RawDraftAction(
                1,
                "An unrecorded window opened.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="unknown.exe",
                window_title="Unknown Window",
            ),
        )
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    kinds = [step.kind for step in proposal.workflow.steps]
    assert kinds == [StepKind.REPORT]
    assert "executable path not recorded" in proposal.workflow.steps[0].message


def test_close_without_a_launch_stays_a_report() -> None:
    exe = r"C:\Program Files\Example\app.exe"
    draft = _draft(
        (
            RawDraftAction(
                1,
                "The app.exe window closed: Example App.",
                RecordedEventKind.WINDOW_CLOSE,
                process_name="app.exe",
                window_title="Example App",
                executable_path=exe,
            ),
        )
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    step = proposal.workflow.steps[0]
    assert step.kind is StepKind.REPORT
    assert "does not launch" in step.message


def test_repeated_launches_collapse_into_one_launch() -> None:
    exe = r"C:\Program Files\Example\app.exe"
    draft = _draft(
        (
            RawDraftAction(
                1,
                "An app.exe window opened: Example App.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="app.exe",
                window_title="Example App",
                executable_path=exe,
            ),
            RawDraftAction(
                2,
                "An app.exe window opened: another window.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="app.exe",
                window_title="another window",
                executable_path=exe,
            ),
        )
    )

    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))

    kinds = [step.kind for step in proposal.workflow.steps]
    assert kinds == [StepKind.LAUNCH_APPLICATION, StepKind.REPORT]


def test_semantic_click_type_and_shortcut_events_map_to_replayable_steps() -> None:
    exe = r"C:\Program Files\Example\app.exe"
    events = (
        RecordedEvent(
            1,
            1_000,
            RecordedEventKind.WINDOW_OPEN,
            window_title="Example App",
            process_name="app.exe",
            executable_path=exe,
        ),
        RecordedEvent(
            2,
            2_000,
            RecordedEventKind.MOUSE_CLICK,
            x=120,
            y=80,
            window_title="Example App",
            process_name="app.exe",
            executable_path=exe,
            element=UIElementInfo(
                control_type="Button",
                name="Compute",
                automation_id="btnCompute",
                class_name="Button",
            ),
        ),
        RecordedEvent(
            3,
            3_000,
            RecordedEventKind.TEXT_INPUT,
            text="42",
            window_title="Example App",
            process_name="app.exe",
            executable_path=exe,
            element=UIElementInfo(
                control_type="Edit",
                name="Input",
                automation_id="txtInput",
                class_name="Edit",
            ),
        ),
        RecordedEvent(
            4,
            4_000,
            RecordedEventKind.KEY_PRESS,
            key="enter",
            window_title="Example App",
            process_name="app.exe",
            executable_path=exe,
        ),
        RecordedEvent(
            5,
            5_000,
            RecordedEventKind.WINDOW_CLOSE,
            window_title="Example App",
            process_name="app.exe",
            executable_path=exe,
        ),
    )

    draft = build_raw_draft(Recording("capture-semantic", 1_000, events))
    proposal = deterministic_recording_provider().analyze(AnalysisRequest(draft))
    WorkflowRunner.validate(proposal.workflow)

    kinds = [step.kind for step in proposal.workflow.steps]
    assert kinds == [
        StepKind.LAUNCH_APPLICATION,
        StepKind.CLICK_UI_ELEMENT,
        StepKind.TYPE_TEXT,
        StepKind.PRESS_SHORTCUT,
        StepKind.CLOSE_APPLICATION,
    ]
    click_target = json.loads(proposal.workflow.steps[1].target)
    assert click_target == {
        "interaction": "invoke",
        "element": {
            "automation_id": "btnCompute",
            "class_name": "Button",
            "control_type": "Button",
        },
        "window": {"title": "Example App"},
    }
    type_target = json.loads(proposal.workflow.steps[2].target)
    assert type_target["text"] == "42"
    assert type_target["window"] == {"title": "Example App"}
    shortcut_target = json.loads(proposal.workflow.steps[3].target)
    assert shortcut_target == {
        "keys": "enter",
        "window": {"title": "Example App"},
    }
