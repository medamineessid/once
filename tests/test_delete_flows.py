"""Delete flows: one run, clear all, automations, and in-progress refusal."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from controller.service import WorkflowService
from engine.errors import StorageError
from engine.workflow import (
    StepKind,
    Workflow,
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
)
from storage.database import connect
from storage.history import ExecutionHistory
from ui.components.delete_confirm import (
    DeleteChoice,
    DeleteConfirmDialog,
    automation_delete_message,
)
from ui.pages.activity import ActivityPage
from ui.pages.home import HomePage
from ui.pages.my_automations import MyAutomationsPage
from ui.pages.review import ReviewPage


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def make_workflow(workflow_id: str = "delete-workflow", name: str = "Delete me") -> Workflow:
    return Workflow(
        workflow_id=workflow_id,
        name=name,
        steps=(WorkflowStep("report", "Report", StepKind.REPORT, "Recorded"),),
    )


def make_service(tmp_path: Path) -> WorkflowService:
    connection = connect(tmp_path / "once.db")
    return WorkflowService(
        history=ExecutionHistory(connection),
        workflow_directory=tmp_path / "workflows",
        layout_connection=connection,
    )


def make_running_run(workflow_id: str = "delete-workflow") -> WorkflowRun:
    now = datetime.now(UTC)
    return WorkflowRun(
        run_id="running-run",
        workflow_id=workflow_id,
        status=WorkflowStatus.RUNNING,
        results=(),
        started_at=now,
        finished_at=now,
    )


def confirm_with(monkeypatch: pytest.MonkeyPatch, *, delete_runs: bool) -> None:
    monkeypatch.setattr(
        DeleteConfirmDialog,
        "ask",
        lambda self: DeleteChoice(True, delete_runs),
    )


# --- Storage and controller ---------------------------------------------------


def test_delete_one_run_removes_only_that_run_and_its_steps(tmp_path) -> None:
    service = make_service(tmp_path)
    workflow = make_workflow()
    first = service.run_workflow(workflow)
    second = service.run_workflow(workflow)

    service.delete_run(first.run_id)

    assert [run.run_id for run in service.history()] == [second.run_id]
    connection = sqlite3.connect(tmp_path / "once.db")
    remaining_steps = connection.execute(
        "SELECT COUNT(*) FROM workflow_step_results WHERE run_id = ?", (first.run_id,)
    ).fetchone()[0]
    connection.close()
    assert remaining_steps == 0


def test_clear_all_runs_removes_every_run_and_step(tmp_path) -> None:
    service = make_service(tmp_path)
    service.run_workflow(make_workflow())
    service.run_workflow(make_workflow())

    removed = service.clear_runs()

    assert removed == 2
    assert service.history() == ()
    connection = sqlite3.connect(tmp_path / "once.db")
    remaining_steps = connection.execute("SELECT COUNT(*) FROM workflow_step_results").fetchone()[0]
    connection.close()
    assert remaining_steps == 0


def test_delete_running_run_is_refused(tmp_path) -> None:
    service = make_service(tmp_path)
    service._history.record(make_running_run())

    with pytest.raises(StorageError, match="still in progress"):
        service.delete_run("running-run")
    with pytest.raises(StorageError, match="still in progress"):
        service.clear_runs()
    assert [run.run_id for run in service.history()] == ["running-run"]


def test_delete_automation_with_its_runs(tmp_path) -> None:
    service = make_service(tmp_path)
    workflow = make_workflow()
    saved = service.save(workflow)
    service.run_workflow(workflow)
    service.save_layout(workflow.workflow_id, {"report": (1.0, 2.0)}, {"report": "note"})
    assert service.load_layout(workflow.workflow_id).record is not None

    service.delete_automation(workflow.workflow_id, delete_runs=True)

    assert not saved.exists()
    assert service.list_saved() == ()
    assert service.history() == ()
    assert service.load_layout(workflow.workflow_id).record is None


def test_delete_automation_can_keep_its_runs(tmp_path) -> None:
    service = make_service(tmp_path)
    workflow = make_workflow()
    saved = service.save(workflow)
    run = service.run_workflow(workflow)

    service.delete_automation(workflow.workflow_id, delete_runs=False)

    assert not saved.exists()
    assert [item.run_id for item in service.history()] == [run.run_id]


def test_delete_automation_refuses_a_name_outside_the_data_folder(tmp_path) -> None:
    service = make_service(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(StorageError, match="not valid"):
        service.delete_automation("../outside", delete_runs=True)

    assert outside.exists()


# --- Confirmation dialog ------------------------------------------------------


def test_confirm_dialog_shows_cancel_delete_and_defaults_to_runs(qtbot) -> None:
    dialog = DeleteConfirmDialog(
        automation_delete_message("Open and Close File Explorer", 5), runs_count=5
    )
    qtbot.addWidget(dialog)

    labels = {button.text() for button in dialog.buttons()}
    assert {"Cancel", "Delete"} <= labels
    assert dialog.text() == (
        "Delete 'Open and Close File Explorer' and its 5 runs? This cannot be undone."
    )
    assert dialog.runs_checkbox is not None
    assert dialog.runs_checkbox.isChecked()


def test_confirm_dialog_has_no_runs_checkbox_without_history(qtbot) -> None:
    dialog = DeleteConfirmDialog(automation_delete_message("Empty automation", 0))
    qtbot.addWidget(dialog)

    assert dialog.runs_checkbox is None
    assert dialog.text() == "Delete 'Empty automation'? This cannot be undone."


# --- Activity ----------------------------------------------------------------


def test_activity_delete_button_removes_one_run_and_refreshes(qtbot, tmp_path, monkeypatch) -> None:
    service = make_service(tmp_path)
    service.run_workflow(make_workflow())
    service.run_workflow(make_workflow())
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(service)
    confirm_with(monkeypatch, delete_runs=True)

    item = page._history_list.item(0)
    row = page._history_list.itemWidget(item)
    QTest.mouseClick(row.delete_button, Qt.MouseButton.LeftButton)

    assert len(service.history()) == 1
    assert page._history_list.count() == 1


def test_activity_clear_all_removes_every_run_and_shows_empty_state(
    qtbot, tmp_path, monkeypatch
) -> None:
    service = make_service(tmp_path)
    service.run_workflow(make_workflow())
    service.run_workflow(make_workflow())
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(service)
    confirm_with(monkeypatch, delete_runs=True)

    QTest.mouseClick(page._clear_all_button, Qt.MouseButton.LeftButton)

    assert service.history() == ()
    assert page._history_list.count() == 0
    assert page._history_list.isHidden()
    assert not page._empty_state.isHidden()
    assert not page._clear_all_button.isEnabled()


def test_activity_disables_delete_for_a_running_run(qtbot, tmp_path) -> None:
    service = make_service(tmp_path)
    service._history.record(make_running_run())
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(service)

    item = page._history_list.item(0)
    row = page._history_list.itemWidget(item)

    assert not row.delete_button.isEnabled()
    assert not page._clear_all_button.isEnabled()


# --- Home --------------------------------------------------------------------


def test_home_delete_button_removes_a_run_and_shows_empty_state(
    qtbot, tmp_path, monkeypatch
) -> None:
    service = make_service(tmp_path)
    service.run_workflow(make_workflow())
    page = HomePage()
    qtbot.addWidget(page)
    page.set_service(service)
    confirm_with(monkeypatch, delete_runs=True)

    buttons = page.findChildren(QPushButton, "deleteRunButton")
    assert len(buttons) == 1
    QTest.mouseClick(buttons[0], Qt.MouseButton.LeftButton)

    assert service.history() == ()
    assert page.findChildren(QPushButton, "deleteRunButton") == []
    assert not page._activity_empty.isHidden()


# --- My automations ----------------------------------------------------------


def test_my_automations_delete_with_runs_removes_both(qtbot, tmp_path, monkeypatch) -> None:
    service = make_service(tmp_path)
    workflow = make_workflow()
    saved = service.save(workflow)
    service.run_workflow(workflow)
    page = MyAutomationsPage()
    qtbot.addWidget(page)
    page.set_service(service)
    page.show()
    page._workflow_list.setCurrentRow(0)
    confirm_with(monkeypatch, delete_runs=True)

    QTest.mouseClick(page._delete_button, Qt.MouseButton.LeftButton)

    assert page._workflow_list.count() == 0
    assert "No saved automations" in page._details_label.text()
    assert not saved.exists()
    assert service.history() == ()


def test_my_automations_delete_can_keep_runs(qtbot, tmp_path, monkeypatch) -> None:
    service = make_service(tmp_path)
    workflow = make_workflow()
    saved = service.save(workflow)
    service.run_workflow(workflow)
    page = MyAutomationsPage()
    qtbot.addWidget(page)
    page.set_service(service)
    page.show()
    page._workflow_list.setCurrentRow(0)
    confirm_with(monkeypatch, delete_runs=False)

    QTest.mouseClick(page._delete_button, Qt.MouseButton.LeftButton)

    assert not saved.exists()
    assert len(service.history()) == 1


# --- Automation details and shell --------------------------------------------


def test_automation_details_delete_removes_the_saved_file(qtbot, tmp_path, monkeypatch) -> None:
    service = make_service(tmp_path)
    workflow = make_workflow()
    saved = service.save(workflow)
    page = ReviewPage()
    qtbot.addWidget(page)
    page.set_service(service)
    page.show()
    page.show_workflow(service.load(saved))
    deleted: list[bool] = []
    page.automation_deleted.connect(lambda: deleted.append(True))
    confirm_with(monkeypatch, delete_runs=False)

    assert page._delete_button.isVisible()
    QTest.mouseClick(page._delete_button, Qt.MouseButton.LeftButton)

    assert deleted == [True]
    assert not saved.exists()


def test_shell_returns_to_the_refreshed_list_after_deleting_details(
    qtbot, tmp_path, monkeypatch
) -> None:
    from ui.shell import MainWindow

    service = make_service(tmp_path)
    workflow = make_workflow()
    service.save(workflow)
    window = MainWindow(service=service)
    qtbot.addWidget(window)
    window._open_workflow(tmp_path / "workflows" / f"{workflow.workflow_id}.json")
    confirm_with(monkeypatch, delete_runs=True)

    QTest.mouseClick(window.review_page._delete_button, Qt.MouseButton.LeftButton)

    assert window.workspace.currentWidget() is window.my_automations_page
    assert window.my_automations_page._workflow_list.count() == 0
