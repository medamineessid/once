"""Connected local-first recording-to-proposal flow tests."""

from __future__ import annotations

import json
import sys

import pytest

from ai.approval import approve_proposal, preview_proposal
from ai.interview import InterviewSession
from ai.models import AnalysisRequest, ProviderDraft, ProviderQuestion
from ai.provider import FakeAnalysisProvider
from controller.recording import RecordingService
from controller.service import WorkflowService
from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, StepResult, StepStatus, Workflow, WorkflowStep
from integrations.recorder import EventSink
from recorder.drafts import build_raw_draft
from recorder.models import RecordedEvent, RecordedEventKind
from storage.database import connect
from storage.history import ExecutionHistory

APP_TARGET = json.dumps({"executable": str(sys.executable)})


class FakeRecorder:
    def __init__(self, sink: EventSink) -> None:
        self._sink = sink

    def start(self) -> None:
        self._sink.append(RecordedEvent(1, 1, RecordedEventKind.MOUSE_CLICK, x=4, y=5))

    def stop(self) -> None:
        return None


def test_recording_to_approved_proposal(tmp_path) -> None:
    recordings = RecordingService(tmp_path / "recordings", recorder_factory=FakeRecorder)
    recordings.start("journey")
    recordings.stop()
    recording = recordings.load("journey")

    workflow = Workflow(
        "journey-workflow",
        "Journey workflow",
        (
            WorkflowStep(
                "summary",
                "Summary",
                StepKind.VERIFY_PATH_EXISTS,
                "Recorded result exists.",
                str(tmp_path / "result.txt"),
            ),
        ),
    )
    (tmp_path / "result.txt").write_text("done", encoding="utf-8")
    provider = FakeAnalysisProvider(
        (ProviderQuestion("What confirms success?"), ProviderDraft("Goal", workflow))
    )
    interview = InterviewSession(provider, AnalysisRequest(build_raw_draft(recording)))

    assert interview.start().question == "What confirms success?"
    proposal = interview.answer("The result is visible.").draft
    assert proposal is not None
    preview = preview_proposal(proposal)
    approved = approve_proposal(proposal)

    assert preview.goal == "Goal"
    assert preview.steps == (
        "summary: action=VERIFY_PATH_EXISTS "
        f"target={tmp_path / 'result.txt'} permission=ALLOWED "
        "expected=Recorded result exists. source=AI inference",
    )
    assert approved.workflow == workflow

    history = ExecutionHistory(connect(tmp_path / "history.db"))
    run = WorkflowService(history=history).run_approved(approved, allowed_root=tmp_path)

    assert run.status.value == "SUCCEEDED"
    assert history.list_runs()[0].run.workflow_id == "journey-workflow"


def test_unapproved_proposal_cannot_be_saved_or_executed(tmp_path) -> None:
    service = WorkflowService(workflow_directory=tmp_path / "workflows")
    workflow = Workflow(
        "unapproved",
        "Unapproved",
        (WorkflowStep("step", "Step", StepKind.REPORT, "Not approved"),),
    )

    with pytest.raises(WorkflowValidationError, match="explicitly approved"):
        service.save_approved(workflow)  # type: ignore[arg-type]
    with pytest.raises(WorkflowValidationError, match="explicitly approved"):
        service.run_approved(workflow)  # type: ignore[arg-type]


class FakeLaunchCloseDesktopActions:
    """Minimal desktop provider fake: records launch/close targets only."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def launch_application(self, target_json: str) -> StepResult:
        self.calls.append(("LAUNCH_APPLICATION", target_json))
        return StepResult("", StepStatus.SUCCEEDED, "The application was launched.")

    def close_application(self, target_json: str) -> StepResult:
        self.calls.append(("CLOSE_APPLICATION", target_json))
        return StepResult("", StepStatus.SUCCEEDED, "The application windows were closed.")


class WindowRecordingStub:
    """Recorder fake: emits VS Code open then close observations."""

    def __init__(self, sink: EventSink) -> None:
        self._sink = sink

    def start(self) -> None:
        self._sink.append(
            RecordedEvent(
                1,
                10,
                RecordedEventKind.WINDOW_OPEN,
                process_name="Code.exe",
                window_title="Visual Studio Code",
                executable_path=str(sys.executable),
                executable_sha256="",
            )
        )
        self._sink.append(
            RecordedEvent(
                2,
                20,
                RecordedEventKind.WINDOW_CLOSE,
                process_name="Code.exe",
                window_title="Visual Studio Code",
                executable_path=str(sys.executable),
                executable_sha256="",
            )
        )

    def stop(self) -> None:
        return None


def test_recorded_vscode_open_close_replays_unapproved_free(tmp_path) -> None:
    """Record -> draft -> launch/close steps -> approval -> deterministic replay."""
    from ai.provider import deterministic_recording_provider
    from engine.desktop import approve_desktop_workflow
    from engine.workflow import StepStatus

    service = RecordingService(tmp_path / "recordings", recorder_factory=WindowRecordingStub)
    service.start("vscode-demo")
    recording = service.stop()

    proposal = deterministic_recording_provider().analyze(
        AnalysisRequest(build_raw_draft(recording))
    )
    assert [step.kind for step in proposal.workflow.steps] == [
        StepKind.LAUNCH_APPLICATION,
        StepKind.CLOSE_APPLICATION,
    ]

    approval = approve_desktop_workflow(proposal.workflow)
    desktop = FakeLaunchCloseDesktopActions()
    app = WorkflowService(
        history=ExecutionHistory(connect(tmp_path / "history.db")), desktop_actions=desktop
    )
    run = app.run_desktop_approved(approval, cancel_check=lambda: False)

    assert run.status.value == "SUCCEEDED"
    assert [(kind, target) for kind, target in desktop.calls] == [
        ("LAUNCH_APPLICATION", APP_TARGET),
        ("CLOSE_APPLICATION", APP_TARGET),
    ]
    assert [result.status for result in run.results] == [StepStatus.SUCCEEDED, StepStatus.SUCCEEDED]
