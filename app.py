"""Application entry point for Once.

Builds the Qt application and shows the main window. File-system work belongs
to the engine package; this module only wires the UI together.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from controller.service import WorkflowService
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
    window = MainWindow(WorkflowService.for_app_data(app_data_dir))
    window.show()

    if smoke_test:
        # Construct the real window, flush pending Qt work, then leave without
        # waiting for a user to close the window. Any initialisation failure
        # raises and produces a non-zero exit status.
        app.processEvents()
        window.close()
        app.processEvents()
        return 0

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
