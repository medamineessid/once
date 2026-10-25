"""Application entry point for Once.

Builds the Qt application and shows the main window. File-system work belongs
to the engine package; this module only wires the UI together.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from controller.recording import RecordingService
from controller.service import WorkflowService
from controller.verifier_config import VerifierConfig, load_verifier_config
from ui.main_window import MainWindow
from ui.shell import MainWindow as ShellMainWindow

SMOKE_TEST_FLAG = "--smoke-test"
SHELL_FLAG = "--shell"


def setup_logging(app_data_dir: Path) -> Path:
    """Install a rotating UTF-8 log file and exception hook for the session.

    File contents are never logged; only event messages are. The directory is
    created on demand so a first run works before any database exists.
    """
    logs_dir = Path(app_data_dir) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "once.log"
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    def _log_unraised(kind, value, trace) -> None:
        root.error("Unhandled %s: %s", kind.__name__, value)
        sys.__excepthook__(kind, value, trace)

    sys.excepthook = _log_unraised
    return log_path


def build_application(argv: list[str] | None = None) -> QApplication:
    """Return the single QApplication instance, creating it if necessary."""
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication(argv if argv is not None else sys.argv)


def main(argv: list[str] | None = None) -> int:
    """Run Once and return the process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    smoke_test = SMOKE_TEST_FLAG in args
    use_shell = SHELL_FLAG in args
    qt_args = [sys.argv[0], *(arg for arg in args if arg not in (SMOKE_TEST_FLAG, SHELL_FLAG))]

    app = build_application(qt_args)
    app_data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Once"
    try:
        setup_logging(app_data_dir)
        logging.getLogger(__name__).info(
            "Once started (smoke_test=%s, shell=%s)", smoke_test, use_shell
        )
        service = WorkflowService.for_app_data(app_data_dir)
        recording_service = RecordingService(app_data_dir / "recordings")
        verifier_config, verifier_note = _load_verifier_setup(app_data_dir)
        window_cls = ShellMainWindow if use_shell else MainWindow
        window = window_cls(
            service,
            recording_service,
            verifier_config=verifier_config,
            verifier_note=verifier_note,
            app_data_dir=app_data_dir,
        )
    except OSError as error:
        # The app data directory cannot be used (missing, a file instead of a
        # folder, denied). Nothing else can work, so explain it plainly.
        QMessageBox.critical(
            None,
            "Once cannot start",
            f"Once could not create its data folder at {app_data_dir}. "
            f"Reason: {error}. Choose a writable location and start Once again.",
        )
        return 1
    except sqlite3.DatabaseError as error:
        # The history database exists but cannot be opened (corrupt or written
        # by incompatible tooling). The user's data is never deleted or
        # replaced; explain and leave the file exactly as it is.
        QMessageBox.critical(
            None,
            "Once cannot start",
            f"Once could not open its history database at {app_data_dir / 'once.db'}. "
            f"Reason: {error}. No data was removed: the file was left unchanged. "
            "Back it up, then repair or move it aside, and start Once again.",
        )
        return 1
    window.show()

    if smoke_test:
        # Construct the real window, flush pending Qt work, then leave without
        # waiting for a user to close the window. Any initialisation failure
        # raises and produces a non-zero exit status.
        app.processEvents()
        window.close()
        app.processEvents()
        service.close()
        return 0

    exit_code = app.exec()
    service.close()
    return exit_code


def _load_verifier_setup(app_data_dir: Path) -> tuple[VerifierConfig | None, str | None]:
    """Load the configured checker; return a note for a visibly invalid setup."""
    try:
        return load_verifier_config(app_data_dir), None
    except Exception as error:  # one untrusted config file: show the problem, never crash
        return (
            None,
            f"The acceptance checker configuration could not be used: {error} "
            "Fix the file and restart Once; no acceptance checks are configured this session.",
        )


if __name__ == "__main__":
    raise SystemExit(main())
