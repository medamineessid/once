"""Closing the window mid-run must cancel and join the worker thread.

The close event asks the run to stop cooperatively (worker cancel flag ->
engine cancel_check at the next step boundary), quits the thread's event
loop, and joins it within a bounded wait (ui.workers.cancel_and_join,
AD-015 rationale: destroying a running QThread aborts the process).
"""

from __future__ import annotations

import time
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.shell import MainWindow, ShellPages


def slow_run_factory(recorder: list[str]):
    """A fake service.run_workflow that runs briefly and honors cancel."""

    def fake_run_workflow(workflow, cancel_check=None, progress_callback=None):
        recorder.append("start")
        deadline = time.perf_counter() + 0.25
        while time.perf_counter() < deadline and not (cancel_check and cancel_check()):
            time.sleep(0.01)
        if cancel_check and cancel_check():
            recorder.append("cancelled")
            return SimpleNamespace(status=SimpleNamespace(value="CANCELLED"))
        recorder.append("finished")
        return SimpleNamespace(status=SimpleNamespace(value="SUCCEEDED"))

    return fake_run_workflow


def _saved_workflow() -> Workflow:
    return Workflow(
        workflow_id="close-cancel-demo",
        name="Cancellable demo",
        steps=(
            WorkflowStep(
                step_id="s1",
                name="List",
                kind=StepKind.REPORT,
                message="Listed.",
            ),
        ),
    )


def test_close_during_demo_cancels_and_joins_thread(qtbot, tmp_path, monkeypatch):
    window = MainWindow(service=WorkflowService.for_app_data(tmp_path / "appdata"))
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(30)
    recorder: list[str] = []
    monkeypatch.setattr(window._service, "run_workflow", slow_run_factory(recorder))

    QTest.mouseClick(window.home_page._demo_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.status_footer.state == "Running…", timeout=5000)

    window.close()

    # closeEvent joined the thread inside its bound: refs are cleared now.
    assert window._demo_thread is None
    assert "cancelled" in recorder
    assert window.isVisible() is False


def test_close_during_automation_run_cancels_and_joins_thread(qtbot, tmp_path, monkeypatch):
    service = WorkflowService.for_app_data(tmp_path / "appdata")
    service.save(_saved_workflow())
    window = MainWindow(service=service)
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(30)
    window._show_page(ShellPages.MY_AUTOMATIONS)
    page = window.my_automations_page
    page.refresh()
    page._workflow_list.setCurrentRow(0)
    recorder: list[str] = []
    monkeypatch.setattr(service, "run_workflow", slow_run_factory(recorder))

    QTest.mouseClick(page._run_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(page._run_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page._thread is not None, timeout=5000)

    window.close()

    assert page._thread is None
    assert page._worker is None
    assert "cancelled" in recorder
    assert window.isVisible() is False


def test_close_with_no_run_is_harmless(qtbot, tmp_path):
    """Close without any run must not touch threads or fail."""
    window = MainWindow(service=WorkflowService.for_app_data(tmp_path / "appdata"))
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(30)

    window.close()

    assert window._demo_thread is None
    assert window.my_automations_page._thread is None
    assert window.isVisible() is False
