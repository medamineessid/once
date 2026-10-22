"""Tests for the Qt worker boundary around controller execution."""

from __future__ import annotations

from PySide6.QtCore import QThread
from pytestqt.qtbot import QtBot

from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.workers import WorkflowWorker


def test_worker_emits_completed_workflow(qtbot: QtBot) -> None:
    workflow = Workflow(
        "worker",
        "Worker",
        (WorkflowStep("step", "Step", StepKind.REPORT, "Done"),),
    )
    worker = WorkflowWorker(WorkflowService(), workflow)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    with qtbot.waitSignal(worker.finished, timeout=2000) as signal:
        thread.start()
    assert signal.args[0].status.value == "SUCCEEDED"
    thread.quit()
    thread.wait()


def test_worker_can_record_history_from_worker_thread(qtbot: QtBot, tmp_path) -> None:
    service = WorkflowService.for_app_data(tmp_path / "app-data")
    workflow = Workflow(
        "worker-history",
        "Worker history",
        (WorkflowStep("step", "Step", StepKind.REPORT, "Done"),),
    )
    worker = WorkflowWorker(service, workflow)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    with qtbot.waitSignal(worker.finished, timeout=2000):
        thread.start()
    thread.quit()
    thread.wait()

    assert service.history()[0].workflow_id == "worker-history"
    service.close()


def test_worker_emits_failure_for_invalid_workflow(qtbot: QtBot) -> None:
    workflow = Workflow(
        "worker",
        "Worker",
        (WorkflowStep("", "Invalid", StepKind.REPORT, "Invalid"),),
    )
    worker = WorkflowWorker(WorkflowService(), workflow)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    with qtbot.waitSignal(worker.failed, timeout=2000) as signal:
        thread.start()
    assert "workflow step needs an ID" in signal.args[0]
    thread.quit()
    thread.wait()
