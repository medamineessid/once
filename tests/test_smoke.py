"""Step 1 smoke tests: imports, placeholder window and the entry point."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QListWidget, QPushButton
from pytestqt.qtbot import QtBot

from controller.recording import RecordingService
from controller.service import WorkflowService
from engine.errors import (
    ExecutionError,
    OnceError,
    PlanError,
    RecoveryError,
    WorkflowValidationError,
)
from engine.models import IssueCode, OperationType, OpStatus, RunStatus, Severity
from recorder.models import RecordedEvent, RecordedEventKind
from ui.main_window import MainWindow

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeRecorder:
    def __init__(self, sink) -> None:
        self._sink = sink

    def start(self) -> None:
        self._sink.append(RecordedEvent(1, 1, RecordedEventKind.MOUSE_CLICK, x=1, y=2))

    def stop(self) -> None:
        return None


EXPECTED_ISSUE_CODES = {
    "NAME_EMPTY",
    "NAME_INVALID_CHARS",
    "NAME_RESERVED",
    "NAME_TRAILING_DOT_OR_SPACE",
    "NAME_TOO_LONG",
    "PATH_TOO_LONG",
    "DEST_EXISTS",
    "DEST_DUPLICATE_IN_PLAN",
    "SOURCE_MISSING",
    "SOURCE_CHANGED",
    "SOURCE_NOT_REGULAR_FILE",
    "SOURCE_IS_LINK",
    "DEST_PARENT_MISSING",
    "CROSS_VOLUME_MOVE_UNSUPPORTED",
    "CYCLE_DETECTED",
    "NO_CHANGE",
    "CASE_ONLY_RENAME",
    "PERMISSION_DENIED",
    "FILE_IN_USE",
    "DEPENDENCY_FAILED",
    "CANCELLED_BY_USER",
    "UNEXPECTED_OS_ERROR",
}


def test_engine_enums_match_specification() -> None:
    assert {member.value for member in OperationType} == {
        "CREATE_FOLDER",
        "RENAME",
        "MOVE",
        "COPY",
    }
    assert {member.value for member in Severity} == {"INFO", "WARNING", "ERROR"}
    assert {member.value for member in OpStatus} == {
        "PENDING",
        "IN_PROGRESS",
        "DONE",
        "FAILED",
        "SKIPPED",
        "UNDONE",
        "UNDO_REFUSED",
        "UNDO_FAILED",
        "UNKNOWN",
    }
    assert {member.value for member in RunStatus} == {
        "RUNNING",
        "COMPLETED",
        "COMPLETED_WITH_ERRORS",
        "CANCELLED",
        "INTERRUPTED",
        "UNDONE",
        "PARTIALLY_UNDONE",
    }
    assert {member.value for member in IssueCode} == EXPECTED_ISSUE_CODES


def test_error_hierarchy_is_rooted_in_once_error() -> None:
    for error_type in (
        WorkflowValidationError,
        PlanError,
        ExecutionError,
        RecoveryError,
    ):
        assert issubclass(error_type, OnceError)
    assert issubclass(OnceError, Exception)


def test_main_window_shows_workflow_controls(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Once"
    label_texts = [label.text() for label in window.findChildren(QLabel)]
    assert "Choose a saved workflow or run the local demo." in label_texts
    assert "Run local demo" in [button.text() for button in window.findChildren(QPushButton)]
    assert window.findChildren(QListWidget)


def test_main_window_runs_demo_workflow(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    demo_button = next(
        button for button in window.findChildren(QPushButton) if button.text() == "Run local demo"
    )
    qtbot.mouseClick(demo_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: (
            "SUCCEEDED: 2 steps recorded" in [label.text() for label in window.findChildren(QLabel)]
        ),
        timeout=2000,
    )

    assert "SUCCEEDED: 2 steps recorded" in [label.text() for label in window.findChildren(QLabel)]


def test_main_window_creates_and_saves_workflow_from_form(qtbot: QtBot, tmp_path) -> None:
    service = WorkflowService(workflow_directory=tmp_path / "workflows")
    window = MainWindow(service)
    qtbot.addWidget(window)
    edits = window.findChildren(QLineEdit)
    edits[0].setText("Invoices")
    edits[1].setText("Report extraction")
    edits[2].setText("Extraction completed")

    create_button = next(
        button
        for button in window.findChildren(QPushButton)
        if button.text() == "Create workflow from form"
    )
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert (tmp_path / "workflows" / "invoices.json").exists()
    assert any(
        list_widget.count() == 1 and list_widget.item(0).text() == "invoices.json"
        for list_widget in window.findChildren(QListWidget)
    )


def test_main_window_displays_each_step_result(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    demo_button = next(
        button for button in window.findChildren(QPushButton) if button.text() == "Run local demo"
    )
    qtbot.mouseClick(demo_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: any(
            result_list.count() == 2 and "inspect: SUCCEEDED" in result_list.item(0).text()
            for result_list in window.findChildren(QListWidget)
        ),
        timeout=2000,
    )

    result_lists = window.findChildren(QListWidget)
    assert any(
        result_list.count() == 2 and "inspect: SUCCEEDED" in result_list.item(0).text()
        for result_list in result_lists
    )


def test_main_window_reorders_and_removes_draft_steps(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    edits = window.findChildren(QLineEdit)
    add_button = next(
        button
        for button in window.findChildren(QPushButton)
        if button.text() == "Add step to draft"
    )
    edits[1].setText("First")
    edits[2].setText("first")
    qtbot.mouseClick(add_button, Qt.MouseButton.LeftButton)
    edits[1].setText("Second")
    edits[2].setText("second")
    qtbot.mouseClick(add_button, Qt.MouseButton.LeftButton)

    draft_list = next(
        list_widget for list_widget in window.findChildren(QListWidget) if list_widget.count() == 2
    )
    draft_list.setCurrentRow(1)
    move_up = next(
        button for button in window.findChildren(QPushButton) if button.text() == "Move step up"
    )
    qtbot.mouseClick(move_up, Qt.MouseButton.LeftButton)
    assert draft_list.item(0).text().endswith("Second (REPORT)")

    remove = next(
        button for button in window.findChildren(QPushButton) if button.text() == "Remove step"
    )
    qtbot.mouseClick(remove, Qt.MouseButton.LeftButton)
    assert draft_list.count() == 1


def test_main_window_reviews_analyzes_and_approves_recording(qtbot: QtBot, tmp_path) -> None:
    service = WorkflowService(workflow_directory=tmp_path / "workflows")
    recording_service = RecordingService(tmp_path / "recordings", recorder_factory=FakeRecorder)
    window = MainWindow(service, recording_service)
    qtbot.addWidget(window)

    buttons = {button.text(): button for button in window.findChildren(QPushButton)}
    qtbot.mouseClick(buttons["Record"], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(buttons["Stop recording"], Qt.MouseButton.LeftButton)

    recording_list = next(
        widget for widget in window.findChildren(QListWidget) if widget.count() == 1
    )
    recording_list.setCurrentRow(0)
    qtbot.mouseClick(buttons["Analyze selected recording (offline)"], Qt.MouseButton.LeftButton)
    answer = window.findChildren(QLineEdit)[-1]
    answer.setText("The result is visible.")
    qtbot.mouseClick(buttons["Submit answer"], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(buttons["Approve and save proposal"], Qt.MouseButton.LeftButton)

    assert (tmp_path / "workflows" / "recorded-task.json").exists()


def test_app_smoke_test_exits_zero(tmp_path) -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["LOCALAPPDATA"] = str(tmp_path / "localappdata")

    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "app.py"), "--smoke-test"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
