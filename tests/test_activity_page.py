"""Read-only activity-history wiring tests (UI migration slice 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from storage.database import connect
from storage.history import ExecutionHistory
from ui.pages.activity import ActivityPage


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def make_service(tmp_path: Path) -> WorkflowService:
    return WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))


def second_workflow() -> Workflow:
    return Workflow(
        workflow_id="demo-local-workflow-2",
        name="Second demo workflow",
        steps=(
            WorkflowStep(
                step_id="inspect-2",
                name="Inspect workflow",
                kind=StepKind.REPORT,
                message="Second workflow definition accepted.",
            ),
        ),
    )


def test_activity_page_lists_history_runs(qtbot, tmp_path):
    service = make_service(tmp_path)
    service.run_demo()
    service.run_demo()
    page = ActivityPage()
    qtbot.addWidget(page)

    page.set_service(service)

    assert page._history_list is not None
    assert page._history_list.count() == 2
    first_item = page._history_list.item(0)
    assert first_item is not None
    assert "demo-local-workflow" in first_item.text()


def test_details_label_matches_selected_run(qtbot, tmp_path):
    service = make_service(tmp_path)
    service.run_demo()
    service.run_workflow(second_workflow())
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(service)

    page._history_list.setCurrentRow(0)

    details = page._details_label.text()
    assert details.startswith("demo-local-workflow-2")
    # The run only reported, so it says so in plain language.
    assert "Observation only — nothing was performed" in details
    assert "Step 1: Note only" in details
    assert "inspect-2" not in details

    page._history_list.setCurrentRow(1)
    oldest_details = page._details_label.text()
    assert oldest_details != details
    assert oldest_details.startswith("demo-local-workflow")
    assert "demo-local-workflow-2" not in oldest_details
    assert "2 steps" in oldest_details


def test_empty_history_shows_placeholder(qtbot, tmp_path):
    service = make_service(tmp_path)
    page = ActivityPage()
    qtbot.addWidget(page)

    page.set_service(service)

    assert page._history_list is not None
    assert page._history_list.count() == 0
    assert page._details_label.text() == "Select a run to see details."


def test_set_service_none_clears_list(qtbot, tmp_path):
    service = make_service(tmp_path)
    service.run_demo()
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(service)

    page.set_service(None)

    assert page._history_list is not None
    assert page._history_list.count() == 0


def test_refresh_picks_up_new_runs(qtbot, tmp_path):
    service = make_service(tmp_path)
    service.run_demo()
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(service)

    service.run_demo()
    page.refresh()

    assert page._history_list is not None
    assert page._history_list.count() == 2


def test_selection_change_clears_details_when_nothing_selected(qtbot, tmp_path):
    service = make_service(tmp_path)
    service.run_demo()
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(service)

    page._history_list.setCurrentRow(0)
    page._history_list.setCurrentRow(-1)

    assert page._details_label.text() == "Select a run to see details."


def test_shell_injects_service_into_activity_page(qtbot, tmp_path):
    from ui.shell import MainWindow

    service = make_service(tmp_path)
    window = MainWindow(service=service)
    qtbot.addWidget(window)

    assert window.activity_page._service is service


def test_run_row_shows_duration_failure_reason_and_run_again(qtbot, tmp_path):
    """Each history row answers: how long, why it stopped, and can I repeat it."""
    service = make_service(tmp_path)
    folder = tmp_path / "notes"
    folder.mkdir()
    failing = Workflow(
        workflow_id="save-a-note",
        name="Save a note",
        steps=(
            WorkflowStep(
                step_id="check-saved-file",
                name="Check the saved file",
                kind=StepKind.VERIFY_PATH_EXISTS,
                message="Check the saved file exists.",
                target=str(folder / "today.txt"),
            ),
        ),
    )
    run = service.run_workflow(failing, allowed_root=folder)
    assert run.status.value == "FAILED"

    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(service)
    row = page._history_list.itemWidget(page._history_list.item(0))

    caption = row._caption.text()
    assert "took " in caption
    assert "Stopped: " in caption
    # The internal attempt counter is not part of a user-facing reason.
    assert "attempt(s)" not in caption
    assert row.rerun_button.text() == "Run again"
    assert row.rerun_button.isEnabled() is True


def test_run_again_emits_the_workflow_id(qtbot, tmp_path):
    service = make_service(tmp_path)
    service.run_demo()
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(service)
    requested: list[str] = []
    page.rerun_requested.connect(requested.append)

    row = page._history_list.itemWidget(page._history_list.item(0))
    row.rerun_button.click()

    assert requested == ["demo-local-workflow"]
