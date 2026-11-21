"""The run controls a person can actually reach: Stop, and Run again."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.components.footer import RUNNING, StatusFooter
from ui.shell import MainWindow, ShellPages


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _saved_workflow() -> Workflow:
    return Workflow(
        "notepad-note",
        "Write a note in Notepad",
        (
            WorkflowStep(
                "report",
                "Note the task",
                StepKind.REPORT,
                "Open Notepad, type once test, close it.",
            ),
        ),
    )


def _window(qtbot, tmp_path):
    service = WorkflowService.for_app_data(tmp_path)
    window = MainWindow(service=service)
    qtbot.addWidget(window)
    window.show()
    return window, service


def test_stop_button_is_visible_only_while_a_run_is_live(qtbot) -> None:
    _app()
    footer = StatusFooter()
    qtbot.addWidget(footer)
    footer.show()

    assert footer.stop_button.isHidden() is True
    footer.set_state(RUNNING)
    assert footer.stop_button.isHidden() is False
    footer.set_state("Ready")
    assert footer.stop_button.isHidden() is True


def test_stop_cancels_the_live_automation_worker(qtbot, tmp_path) -> None:
    window, _service = _window(qtbot, tmp_path)

    class FakeWorker:
        def __init__(self) -> None:
            self.cancelled = 0

        def cancel(self) -> None:
            self.cancelled += 1

    worker = FakeWorker()
    window.my_automations_page._worker = worker
    window.status_footer.set_state(RUNNING)

    window.status_footer.stop_button.click()

    assert worker.cancelled == 1


def test_stop_with_no_run_does_nothing(qtbot, tmp_path) -> None:
    window, _service = _window(qtbot, tmp_path)

    window.status_footer.stop_requested.emit()

    assert window.my_automations_page.worker is None


def test_a_page_run_drives_the_footer_state(qtbot, tmp_path) -> None:
    window, _service = _window(qtbot, tmp_path)

    window.my_automations_page.run_state_changed.emit(True)
    assert window.status_footer.state == RUNNING

    window.my_automations_page.run_state_changed.emit(False)
    assert window.status_footer.state == "Ready"


def test_run_again_opens_the_saved_automation_on_its_own_page(qtbot, tmp_path) -> None:
    window, service = _window(qtbot, tmp_path)
    service.save(_saved_workflow())
    service.run_workflow(_saved_workflow())
    window.activity_page.refresh()
    window._show_page(ShellPages.ACTIVITY)

    row = window.activity_page._history_list.itemWidget(window.activity_page._history_list.item(0))
    row.rerun_button.click()

    assert window.workspace.currentIndex() == ShellPages.MY_AUTOMATIONS
    page = window.my_automations_page
    assert page._workflow_list.count() == 1
    # The repeat run itself starts on the automations page and finishes.
    qtbot.waitUntil(lambda: page.worker is None, timeout=10000)
    assert window.status_footer.state == "Ready"


def test_run_again_says_so_when_the_automation_was_deleted(qtbot, tmp_path) -> None:
    window, service = _window(qtbot, tmp_path)
    # A run whose workflow file no longer exists, as after deleting the draft.
    service.run_demo()
    window.activity_page.refresh()
    window._show_page(ShellPages.ACTIVITY)

    row = window.activity_page._history_list.itemWidget(window.activity_page._history_list.item(0))
    row.rerun_button.click()

    assert window.workspace.currentIndex() == ShellPages.ACTIVITY
    assert window.banner.isVisible() is True
    assert "cannot run again" in window.banner.body_text
