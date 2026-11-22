"""B1: run-events contract over real engine executions.

Events are produced by RunEventStream from genuine WorkflowRunner results
(with a fake desktop provider only where a controller provider would sit),
plus the worker-level delivery check through ui.workers.WorkflowWorker.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

from PySide6.QtCore import QThread

from controller.run_events import (
    FakeRunEventSource,
    RunEvent,
    RunEventKind,
    RunEventStream,
)
from engine.workflow import (
    StepKind,
    StepResult,
    StepStatus,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)
from ui.workers import WorkflowWorker


def two_step_workflow() -> Workflow:
    return Workflow(
        workflow_id="run-events-order",
        name="Run events order",
        steps=(
            WorkflowStep(step_id="s1", name="Note", kind=StepKind.REPORT, message="First."),
            WorkflowStep(step_id="s2", name="Done", kind=StepKind.REPORT, message="Second."),
        ),
    )


def run_through_stream(
    workflow: Workflow, **runner_kwargs: object
) -> tuple[object, tuple[tuple[str, str], ...], list[RunEvent]]:
    """Run the REAL engine through a stream; return (run, (kind, step) order, events)."""
    stream = RunEventStream(workflow)
    events: list[RunEvent] = list(stream.start())

    def on_step(step_result: StepResult) -> None:
        events.extend(stream.observe_step(step_result))

    runner = WorkflowRunner()
    run = runner.run(workflow, progress_callback=on_step, **runner_kwargs)
    events.extend(stream.observe_run(run))
    order = tuple((event.kind.value, event.step_id or "") for event in events)
    return run, order, events


def test_run_started_event_carries_workflow_identity() -> None:
    stream = RunEventStream(two_step_workflow())
    events = stream.start()

    assert len(events) == 1
    event = events[0]
    assert event.kind is RunEventKind.RUN_STARTED
    assert event.workflow_id == "run-events-order"
    assert event.run_id != ""
    assert event.created_at.tzinfo is not None
    assert stream.finished is False


def test_event_order_for_success_and_run_finished_stops_the_stream() -> None:
    run, order, events = run_through_stream(two_step_workflow())

    assert order == (
        ("RUN_STARTED", ""),
        ("STEP_STARTED", "s1"),
        ("STEP_SUCCEEDED", "s1"),
        ("STEP_STARTED", "s2"),
        ("STEP_SUCCEEDED", "s2"),
        ("RUN_FINISHED", ""),
    )
    sequences = [event.sequence for event in events]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)
    finished = events[-1]
    # Both steps are reports, so the run observed and performed nothing.
    assert finished.status == "OBSERVATION_ONLY"
    assert finished.engine_run_id == run.run_id


def test_event_order_for_failure_then_skipped_fill() -> None:
    workflow = Workflow(
        workflow_id="run-events-fail",
        name="Run events failure",
        steps=(
            WorkflowStep(step_id="s1", name="Stop", kind=StepKind.FAIL, message="stops now"),
            WorkflowStep(step_id="s2", name="Never", kind=StepKind.REPORT, message="never runs"),
        ),
    )
    _run, order, events = run_through_stream(workflow)

    assert order == (
        ("RUN_STARTED", ""),
        ("STEP_STARTED", "s1"),
        ("STEP_FAILED", "s1"),
        ("STEP_SKIPPED", "s2"),
        ("RUN_FINISHED", ""),
    )
    failed_event = events[2]
    assert failed_event.message == "stops now after 1 attempt(s)."
    skipped_event = events[3]
    assert "earlier step failed" in skipped_event.message
    finished = events[-1]
    assert finished.status == "FAILED"


def test_event_order_for_cancellation_marks_remaining_steps_cancelled() -> None:
    workflow = two_step_workflow()
    stream = RunEventStream(workflow)
    events: list[RunEvent] = list(stream.start())
    cancelled_now = False

    def cancel_check() -> bool:
        return cancelled_now

    def on_step(step_result: StepResult) -> None:
        nonlocal cancelled_now
        events.extend(stream.observe_step(step_result))
        # The user cancels once the first step has really completed.
        cancelled_now = True

    runner = WorkflowRunner()
    run = runner.run(workflow, progress_callback=on_step, cancel_check=cancel_check)
    events.extend(stream.observe_run(run))

    order = tuple((event.kind.value, event.step_id or "") for event in events)
    assert order == (
        ("RUN_STARTED", ""),
        ("STEP_STARTED", "s1"),
        ("STEP_SUCCEEDED", "s1"),
        ("STEP_CANCELLED", "s2"),
        ("RUN_FINISHED", ""),
    )
    assert events[-1].status == "CANCELLED"
    assert "cancelled" in events[3].message


def test_retry_reports_one_final_result_with_attempt_evidence() -> None:
    calls: list[int] = []

    class FlakyTyping:
        """Fake desktop provider: fails once, then really succeeds."""

        def type_text(self, target_json: str) -> StepResult:
            calls.append(len(calls) + 1)
            if calls == [1]:
                return StepResult("type", StepStatus.FAILED, "The window was not ready.")
            return StepResult("type", StepStatus.SUCCEEDED, "Typed the text.")

    target = json.dumps(
        {
            "window": {"title": "Stub window"},
            "element": {"automation_id": "okButton"},
            "text": "hello",
        }
    )
    workflow = Workflow(
        workflow_id="run-events-retry",
        name="Run events retry",
        steps=(
            WorkflowStep(
                step_id="type",
                name="Type",
                kind=StepKind.TYPE_TEXT,
                message="type",
                target=target,
                max_attempts=3,
            ),
            WorkflowStep(step_id="note", name="Note", kind=StepKind.REPORT, message="done"),
        ),
    )
    _run, order, events = run_through_stream(workflow, desktop_actions=FlakyTyping())

    assert order == (
        ("RUN_STARTED", ""),
        ("STEP_STARTED", "type"),
        ("STEP_SUCCEEDED", "type"),
        ("STEP_STARTED", "note"),
        ("STEP_SUCCEEDED", "note"),
        ("RUN_FINISHED", ""),
    )
    retry_event = events[2]
    assert "(attempt 2)" in retry_event.message
    assert any("attempt 1" in item for item in retry_event.evidence)


def test_stream_is_closed_after_run_finished() -> None:
    workflow = two_step_workflow()
    stream = RunEventStream(workflow)
    runner = WorkflowRunner()
    run = runner.run(workflow, progress_callback=None)

    events = list(stream.start())
    events.extend(stream.observe_run(run))
    assert stream.finished is True
    finished_events = [event for event in events if event.kind is RunEventKind.RUN_FINISHED]
    assert len(finished_events) == 1

    assert stream.start() == ()
    assert stream.observe_step(run.results[0]) == ()
    assert stream.observe_run(run) == ()
    assert stream.observe_failure("late failure") == ()


def _run_worker_in_thread(worker: WorkflowWorker) -> QThread:
    """Start the worker the way the pages do, and return the thread."""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    thread.start()
    return thread


def test_worker_delivers_run_events_in_order_and_stops(qtbot) -> None:
    def fake_run(workflow, allowed_root=None, cancel_check=None, progress_callback=None):
        time.sleep(0.05)
        if progress_callback is not None:
            progress_callback(StepResult("s1", StepStatus.SUCCEEDED, "First.", ("e1",)))
        # Suggests a run cancelled right before its second step: the engine
        # would really return one SKIPPED fill for it.
        return SimpleNamespace(
            run_id="engine-1",
            workflow_id=workflow.workflow_id,
            status=SimpleNamespace(value="SUCCEEDED"),
            results=(
                StepResult("s1", StepStatus.SUCCEEDED, "First.", ("e1",)),
                StepResult(
                    "s2", StepStatus.SKIPPED, "Skipped because the workflow was cancelled.", ()
                ),
            ),
            started_at=None,
            finished_at=None,
        )

    service = SimpleNamespace(run_workflow=fake_run)
    worker = WorkflowWorker(service, two_step_workflow())  # type: ignore[arg-type]
    delivered: list[tuple[str, str]] = []
    worker.run_event.connect(
        lambda event: delivered.append((event.kind.value, event.step_id or ""))
    )
    runs: list[object] = []
    worker.finished.connect(lambda run: runs.append(run))

    thread = _run_worker_in_thread(worker)
    try:
        qtbot.waitUntil(lambda: len(runs) == 1, timeout=10_000)

        assert delivered == [
            ("RUN_STARTED", ""),
            ("STEP_STARTED", "s1"),
            ("STEP_SUCCEEDED", "s1"),
            ("STEP_CANCELLED", "s2"),
            ("RUN_FINISHED", ""),
        ]
        # No late deliveries after the finish.
        qtbot.wait(100)
        assert len(delivered) == 5
    finally:
        worker.cancel()
        thread.quit()
        thread.wait(5000)


def test_worker_failure_emits_failed_run_finished(qtbot) -> None:
    from controller.service import WorkflowValidationError

    def broken_run(workflow, allowed_root=None, cancel_check=None, progress_callback=None):
        raise WorkflowValidationError("Something is not configured.")

    service = SimpleNamespace(run_workflow=broken_run)
    worker = WorkflowWorker(service, two_step_workflow())  # type: ignore[arg-type]
    kinds: list[str] = []
    statuses: list[str | None] = []

    def collect(event: RunEvent) -> None:
        kinds.append(event.kind.value)
        statuses.append(event.status)

    worker.run_event.connect(collect)
    failures: list[str] = []
    worker.failed.connect(lambda message: failures.append(message))

    thread = _run_worker_in_thread(worker)
    try:
        qtbot.waitUntil(lambda: len(failures) == 1, timeout=10_000)

        assert failures == ["Something is not configured."]
        assert kinds == ["RUN_STARTED", "RUN_FINISHED"]
        assert statuses == [None, "FAILED"]
    finally:
        worker.cancel()
        thread.quit()
        thread.wait(5000)


def test_fake_run_event_source_hands_out_scripted_batches_once(qtbot, tmp_path) -> None:
    workflow = two_step_workflow()
    fake = FakeRunEventSource(
        workflow,
        batches={},  # build real-looking defaults through the helper below
    )
    started = fake.start()
    steps = fake.observe_step(StepResult("s1", StepStatus.SUCCEEDED, "First.", ("e1",)))
    finished = fake.observe_run(
        SimpleNamespace(
            run_id="engine-1",
            status=SimpleNamespace(value="SUCCEEDED"),
            results=(),
        )
    )
    assert started == ()
    assert steps == ()
    assert finished == ()
    assert fake.finished is True

    scripted = FakeRunEventSource(
        workflow,
        batches={
            "start": (fake.event(RunEventKind.RUN_STARTED, message="The run started."),),
            "run": (
                fake.event(
                    RunEventKind.RUN_FINISHED,
                    message="The run finished.",
                    status="SUCCEEDED",
                    engine_run_id="engine-1",
                ),
            ),
        },
    )
    assert scripted.start()[0].kind is RunEventKind.RUN_STARTED
    assert scripted.observe_run(None)[0].kind is RunEventKind.RUN_FINISHED
    assert scripted.observe_failure("late") == ()
