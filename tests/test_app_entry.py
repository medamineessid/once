"""Tests for the application entry point plumbing (logging, startup failure).

These tests never touch the real user data directory: only tmp_path and
monkeys are used. Qt is not started, so the tests run fast everywhere.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from app import main


def test_setup_logging_writes_a_rotating_utf8_file(tmp_path: Path) -> None:
    from app import setup_logging

    log_path = setup_logging(tmp_path)
    logging.getLogger("once.test").info("entry-point logging works")
    for handler in logging.getLogger().handlers[:]:
        handler.flush()
    # remove our handler again so other tests are unaffected
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if "once.log" in str(getattr(handler, "baseFilename", "")):
            root.removeHandler(handler)
            handler.close()

    content = log_path.read_text(encoding="utf-8")
    assert "entry-point logging works" in content
    assert log_path.name == "once.log"
    assert log_path.parent.name == "logs"


def test_startup_failure_over_an_unusable_data_directory_is_explained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LOCALAPPDATA pointing at a plain file yields a message, not a traceback."""
    from PySide6.QtWidgets import QMessageBox

    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(blocker))
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: messages.append(str(a)))
    exit_code = main(["--smoke-test"])
    assert exit_code == 1
    assert messages, "the user must see why the app cannot start"
    assert "data folder" in messages[0]
    # nothing was created inside the blocker file
    assert blocker.is_file()


def test_corrupt_database_explains_itself_and_is_never_silently_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupted once.db fails clearly; the user's data file is left untouched."""
    from PySide6.QtWidgets import QMessageBox

    isolation = tmp_path / "appdata-root"
    (isolation / "Once").mkdir(parents=True)
    database = isolation / "Once" / "once.db"
    database.write_bytes(b"this file was created by an angry deity\x00" * 16)
    original_bytes = database.read_bytes()
    monkeypatch.setenv("LOCALAPPDATA", str(isolation))
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: messages.append(str(a)))

    exit_code = main(["--smoke-test"])

    assert exit_code == 1
    assert messages, "the user must be told why the app cannot start"
    assert "history database" in messages[0]
    assert "left" in messages[0]  # the data was NOT silently replaced
    assert database.read_bytes() == original_bytes


def test_smoke_test_against_a_missing_database_directory_writes_no_recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real -smoke-test run over an isolated LOCALAPPDATA stays successful."""
    isolation = tmp_path / "appdata-root"
    monkeypatch.setenv("LOCALAPPDATA", str(isolation))
    monkeypatch.setattr(sys, "argv", ["Once", "--smoke-test"])
    exit_code = main(["--smoke-test"])
    assert exit_code == 0
    assert (isolation / "Once" / "once.db").is_file()
    assert (isolation / "Once" / "logs" / "once.log").is_file()


def test_smoke_test_with_shell_flag_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The --shell flag launches the redesigned shell window and smoke-test exits 0."""
    isolation = tmp_path / "appdata-root-shell"
    monkeypatch.setenv("LOCALAPPDATA", str(isolation))
    exit_code = main(["--shell", "--smoke-test"])
    assert exit_code == 0
    assert (isolation / "Once" / "once.db").is_file()
