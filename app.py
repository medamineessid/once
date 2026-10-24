"""Application entry point for Once.

Builds the Qt application and shows the main window. File-system work belongs
to the engine package; this module only wires the UI together.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from controller.recording import RecordingService
from controller.service import WorkflowService
from controller.verifier_config import VerifierConfig, load_verifier_config
from ui.main_window import MainWindow

SMOKE_TEST_FLAG = "--smoke-test"


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
    qt_args = [sys.argv[0], *(arg for arg in args if arg != SMOKE_TEST_FLAG)]

    app = build_application(qt_args)
    app_data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Once"
    service = WorkflowService.for_app_data(app_data_dir)
    recording_service = RecordingService(app_data_dir / "recordings")
    verifier_config, verifier_note = _load_verifier_setup(app_data_dir)
    window = MainWindow(
        service,
        recording_service,
        verifier_config=verifier_config,
        verifier_note=verifier_note,
        app_data_dir=app_data_dir,
    )
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
