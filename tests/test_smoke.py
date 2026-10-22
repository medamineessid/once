"""Step 1 smoke tests: imports, placeholder window and the entry point."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from engine.errors import (
    ExecutionError,
    OnceError,
    PlanError,
    RecoveryError,
    WorkflowValidationError,
)
from engine.models import IssueCode, OperationType, OpStatus, RunStatus, Severity
from ui.main_window import MainWindow

PROJECT_ROOT = Path(__file__).resolve().parents[1]

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


def test_main_window_shows_startup_label(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Once"
    label_texts = [label.text() for label in window.findChildren(QLabel)]
    assert "Once is starting up…" in label_texts


def test_app_smoke_test_exits_zero() -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"

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
