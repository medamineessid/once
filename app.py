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
import tempfile
from pathlib import Path

from PySide6.QtGui import QFont, QFontInfo
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QWidget

from controller.recording import RecordingService
from controller.service import WorkflowService
from controller.verifier_config import VerifierConfig, load_verifier_config
from engine.errors import StorageError
from ui.fonts import load_fonts
from ui.main_window import MainWindow
from ui.shell import MainWindow as ShellMainWindow

SMOKE_TEST_FLAG = "--smoke-test"
SHELL_FLAG = "--shell"
CLASSIC_FLAG = "--classic"
SCREENSHOT_FLAG = "--screenshot"
PAGE_FLAG = "--page"
DIAGNOSE_FLAG = "--diagnose"

_PAGE_WIDGETS = {
    "home": "home_page",
    "automations": "my_automations_page",
    "activity": "activity_page",
    "settings": "settings_page",
    "details": "review_page",
}
_PAGE_INDEX = {
    "home": 0,
    "automations": 1,
    "activity": 2,
    "settings": 3,
    "details": 4,
}
_APP_OWN_FLAGS = {
    SMOKE_TEST_FLAG,
    SHELL_FLAG,
    CLASSIC_FLAG,
    SCREENSHOT_FLAG,
    PAGE_FLAG,
    DIAGNOSE_FLAG,
}


def _flag_value(args: list[str], flag: str) -> str | None:
    """Return the value after ``flag``, or None when absent."""
    if flag not in args:
        return None
    index = args.index(flag)
    return args[index + 1] if index + 1 < len(args) else None


def _strip_app_args(args: list[str]) -> list[str]:
    """Drop Once's own flags and their values before Qt sees them."""
    cleaned: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in (SCREENSHOT_FLAG, PAGE_FLAG):
            skip_next = True
            continue
        if arg in _APP_OWN_FLAGS:
            continue
        cleaned.append(arg)
    return cleaned


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


def _app_data_dir() -> Path:
    """The session's application data directory (never edited by tests here)."""
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Once"


def build_window(
    args: list[str],
) -> tuple[QApplication, MainWindow, WorkflowService, RecordingService]:
    """Build the real application window exactly as the entry point wires it.

    Returns the Qt application, the window, and the two services behind the
    UI so callers (tests without an event loop) can drive and shut them down.
    Raises on failure exactly like the inline path used to, for main() to
    turn into a plain-language message.
    """
    smoke_test = SMOKE_TEST_FLAG in args
    use_shell = SHELL_FLAG in args
    capture = SCREENSHOT_FLAG in args or DIAGNOSE_FLAG in args
    qt_args = [sys.argv[0], *_strip_app_args(args)]

    app = build_application(qt_args)
    families = load_fonts()
    if "Inter" in families:
        app.setFont(QFont("Inter"))
    # Capture/diagnose runs use a throwaway data folder so the user's real
    # history and recordings are never touched by an automated run.
    app_data_dir = Path(tempfile.mkdtemp(prefix="once-capture-")) if capture else _app_data_dir()
    setup_logging(app_data_dir)
    logging.getLogger(__name__).info(
        "Once started (smoke_test=%s, shell=%s)", smoke_test, use_shell
    )
    service = WorkflowService.for_app_data(app_data_dir)
    try:
        recording_service = RecordingService(app_data_dir / "recordings")
        verifier_config, verifier_note = _load_verifier_setup(app_data_dir)
        # Default to the redesigned shell (Slice 8 CHECKPOINT 2 lifted by
        # explicit user request on 2026-11-02); the legacy window remains
        # reachable explicitly via --classic for one release cycle.
        window_cls = MainWindow if CLASSIC_FLAG in args else ShellMainWindow
        window = window_cls(
            service,
            recording_service,
            verifier_config=verifier_config,
            verifier_note=verifier_note,
            app_data_dir=app_data_dir,
        )
    except Exception:
        # The service opened its database; nothing else started, so close it
        # before failing upward so main() can explain and exit cleanly.
        service.close()
        raise
    return app, window, service, recording_service


def main(argv: list[str] | None = None) -> int:
    """Run Once and return the process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    smoke_test = SMOKE_TEST_FLAG in args
    app_data_dir = _app_data_dir()

    try:
        app, window, service, _recording_service = build_window(args)
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
    except StorageError as error:
        QMessageBox.critical(None, "Once cannot start", str(error))
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

    if DIAGNOSE_FLAG in args:
        page_name = _flag_value(args, PAGE_FLAG) or "home"
        _select_page(window, page_name)
        app.processEvents()
        _print_diagnostics(window, page_name)
        window.close()
        app.processEvents()
        service.close()
        return 0

    screenshot_path = _flag_value(args, SCREENSHOT_FLAG)
    if screenshot_path:
        _select_page(window, _flag_value(args, PAGE_FLAG) or "home")
        app.processEvents()
        QTest.qWait(800)
        window.grab().save(screenshot_path)
        app.processEvents()
        window.close()
        app.processEvents()
        service.close()
        print(f"Saved screenshot to {screenshot_path}")
        return 0

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


def _select_page(window: object, name: str) -> None:
    """Show one of the stacked pages by short name."""
    from ui.shell import ShellPages

    index = _PAGE_INDEX.get(name.casefold())
    if index is None:
        raise SystemExit(f"Unknown page {name!r}. Choose one of: {', '.join(_PAGE_INDEX)}")
    workspace = getattr(window, "workspace", None)
    if workspace is not None:
        workspace.setCurrentIndex(index)
    set_checked = getattr(getattr(window, "sidebar", None), "set_checked", None)
    if callable(set_checked):
        set_checked(index)
    _ = ShellPages


def _describe(label: str, widget: QWidget) -> None:
    font = widget.font()
    info = QFontInfo(font)
    text_value = getattr(widget, "text", None)
    text = text_value() if callable(text_value) else ""
    print(
        f"  {label:<22} family={info.family()!r} px={info.pixelSize()} "
        f"devicePixelRatio={widget.devicePixelRatioF():.2f} "
        f"text={text[:40]!r}"
    )


def _print_diagnostics(window: object, page_name: str) -> None:
    """Print real font/icon measurements for the visible page."""
    print(f"DIAGNOSE page={page_name}")
    workspace = getattr(window, "workspace", None)
    active = workspace.currentWidget() if workspace is not None else None
    scope = active if isinstance(active, QWidget) else window
    # Titles and micro-labels by object name on the active page.
    for object_name in ("pageTitle", "heroLine", "heroLineAccent", "heroMicro", "pageMicro"):
        widget = scope.findChild(QWidget, object_name)
        if widget is not None:
            _describe(object_name, widget)
    # Body text: the first QLabel that is not a known display object.
    known = {"pageTitle", "heroLine", "heroLineAccent", "heroMicro", "pageMicro"}
    for label in scope.findChildren(QLabel):
        if label.objectName() not in known and label.isVisible() and label.text():
            _describe("body", label)
            break
    # Sidebar label text lives on the painted SidebarItem itself.
    sidebar_button = window.findChild(QWidget, "sidebarHomeButton")
    if sidebar_button is not None:
        _describe("sidebarLabel", sidebar_button)
        icon_rect = getattr(sidebar_button, "icon_rect", None)
        text_rect = getattr(sidebar_button, "text_rect", None)
        if callable(icon_rect) and callable(text_rect):
            icon = icon_rect()
            text = text_rect()
            gap = text.left() - icon.right() - 1
            print(f"  {'sidebarIcon':<22} px={icon.width()}x{icon.height()} gap={gap}px")
    empty_icon = window.findChild(QWidget, "emptyIcon")
    if empty_icon is not None:
        print(f"  {'emptyStateIcon':<22} px={empty_icon.width()}x{empty_icon.height()}")


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
