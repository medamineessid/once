"""Connected local-first recording-to-proposal flow tests."""

from __future__ import annotations

from ai.approval import approve_proposal, preview_proposal
from ai.interview import InterviewSession
from ai.models import AnalysisRequest, ProviderDraft, ProviderQuestion
from ai.provider import FakeAnalysisProvider
from controller.recording import RecordingService
from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from integrations.recorder import EventSink
from recorder.drafts import build_raw_draft
from recorder.models import RecordedEvent, RecordedEventKind
from storage.database import connect
from storage.history import ExecutionHistory


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
