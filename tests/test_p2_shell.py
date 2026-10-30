"""P2 shell tests: layout system, keyboard, demo run outcomes, honest states.

A control counts as WORKING only when a test clicks it and asserts an
observable effect.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QListWidget

from controller.service import WorkflowService
from engine.errors import OnceError
from ui.shell import MainWindow, ShellPages


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


@pytest.fixture
def window(qtbot, app):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(30)
    return window


def _grid_sizes() -> list[tuple[int, int]]:
    return [(1280, 800), (1366, 768), (1920, 1080)]


# --- Layout system -------------------------------------------------------------------
def test_window_minimum_size_is_960x600(window):
    assert window.minimumSize().width() == 960
    assert window.minimumSize().height() == 600


def test_sidebar_is_flush_left_full_height(window):
    origin = window.sidebar.mapTo(window, QPoint(0, 0))
    assert origin.x() == 0
    assert origin.y() == 0
    side_panel = window.sidebar.parentWidget()
    assert side_panel.height() >= window.centralWidget().height() - 1


def test_banner_sits_above_the_workspace(qtbot, window):
    window.banner.show()
    qtbot.wait(30)
    banner_top = window.banner.mapTo(window, QPoint(0, 0)).y()
    workspace_top = window.workspace.mapTo(window, QPoint(0, 0)).y()
    assert banner_top < workspace_top
    assert window.banner.parentWidget() is not window.workspace


def test_status_footer_lives_in_the_sidebar(window):
    assert window.status_footer.parentWidget() is window.sidebar.parentWidget()
    assert window.status_footer.state == "Ready"


@pytest.mark.parametrize("width_height", [(1280, 800), (1366, 768), (1920, 1080)])
def test_pages_show_no_clipped_text_or_horizontal_overflow(qtbot, app, width_height):
    """The whole shell must stay usable at these three laptop overrides."""
    width, height = width_height
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.resize(width, height)
    QApplication.processEvents()
    pages = (
        window.home_page,
        window.my_automations_page,
        window.activity_page,
        window.settings_page,
        window.create_automation_page,
    )
    for page in pages:
        window.workspace.setCurrentWidget(page)
        QApplication.processEvents()
        qtbot.wait(10)
        for list_view in page.findChildren(QListWidget):
            assert list_view.horizontalScrollBar().maximum() == 0, (
                f"{type(page).__name__}: a list scrolled horizontally"
            )
        for label in page.findChildren(QLabel):
            if label.isVisible() and not label.wordWrap():
                assert label.sizeHint().width() <= label.width() + 2, (
                    f"{type(page).__name__}: '{label.text()[:40]}' was clipped"
                )


def test_pages_follow_the_page_template(qtbot, window):
    """Every page: bold title plus one lighter guiding line."""
    secondary_names = {"pageDescription", "pageSubtitle", "questionLabel"}
    pages = (
        window.home_page,
        window.my_automations_page,
        window.activity_page,
        window.settings_page,
        window.create_automation_page,
    )
    for page in pages:
        titles = [w for w in page.findChildren(QLabel) if w.objectName() == "pageTitle"]
        assert titles, f"{type(page).__name__} has no page title"
        secondary = [w for w in page.findChildren(QLabel) if w.objectName() in secondary_names]
        assert secondary, f"{type(page).__name__} has no guiding line"


# --- Keyboard ---------------------------------------------------------------------------
def test_ctrl_1_through_4_switch_pages(qtbot, window):
    bindings = (
        (Qt.Key_1, ShellPages.HOME),
        (Qt.Key_2, ShellPages.MY_AUTOMATIONS),
        (Qt.Key_3, ShellPages.ACTIVITY),
        (Qt.Key_4, ShellPages.SETTINGS),
    )
    for key, page in bindings:
        QTest.keyClick(window, key, Qt.ControlModifier)
        qtbot.wait(30)
        assert window.workspace.currentIndex() == page


def test_ctrl_n_is_deliberately_not_bound(qtbot, window):
    """Create-with-editor wiring (Ctrl+N) lands in P4; the shell must not fake it."""
    for shortcut in window.findChildren(QShortcut):
        assert shortcut.key() != QKeySequence("Ctrl+N")
    window._show_page(ShellPages.SETTINGS)
    QTest.keyClick(window, Qt.Key_N, Qt.ControlModifier)
    qtbot.wait(30)
    assert window.workspace.currentIndex() == ShellPages.SETTINGS


# --- Demo run outcomes -------------------------------------------------------------------
def test_first_time_user_can_run_demo_and_see_it_recorded(qtbot, tmp_path):
    """P2 first-time acceptance: run the demo, see the outcome and its record.

    The create/save automation leg of first-time acceptance arrives with the
    visual editor (P4): the shell honestly answers typed descriptions on a
    banner instead of fabricating a workflow.
    """
    window = MainWindow(service=WorkflowService.for_app_data(tmp_path / "appdata"))
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(30)
    service = window._service

    QTest.mouseClick(window.home_page._demo_button, Qt.MouseButton.LeftButton)
    assert window.status_footer.state == "Running…"

    qtbot.waitUntil(lambda: len(service.history()) == 1, timeout=30_000)
    qtbot.waitUntil(lambda: window.status_footer.state == "Ready", timeout=30_000)

    assert window.banner.isVisible()
    assert "finished" in window.banner.title_text.casefold()

    home = window.home_page
    assert len(home._activity_rows) == 1
    texts = " | ".join(label.text() for label in home._activity_rows[0].findChildren(QLabel))
    assert "Succeeded" in texts

    window._show_page(ShellPages.ACTIVITY)
    page = window.activity_page
    assert page._history_list.count() == 1
    item = page._history_list.item(0)
    assert item.data(Qt.UserRole) == "demo-local-workflow"
    row = page._history_list.itemWidget(item)
    assert row is not None
    assert "Succeeded" in " ".join(label.text() for label in row.findChildren(QLabel))


def test_failed_demo_run_shows_attention_and_banner(qtbot, tmp_path, monkeypatch):
    window = MainWindow(service=WorkflowService.for_app_data(tmp_path / "appdata"))
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(30)

    def boom(workflow, allowed_root=None, cancel_check=None, progress_callback=None):
        raise OnceError("Injected demo failure.")

    monkeypatch.setattr(window._service, "run_workflow", boom)

    QTest.mouseClick(window.home_page._demo_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.status_footer.state == "Needs attention", timeout=30_000)
    qtbot.waitUntil(lambda: window._demo_thread is None, timeout=30_000)
    assert window.banner.isVisible()
    assert "Injected demo failure." in window.banner.body_text
    assert "failed" in window.banner.title_text.casefold()


def test_double_run_request_starts_exactly_one_demo(qtbot, tmp_path):
    """A second click while a run is in flight must not start another run."""
    window = MainWindow(service=WorkflowService.for_app_data(tmp_path / "appdata"))
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(30)

    QTest.mouseClick(window.home_page._demo_button, Qt.MouseButton.LeftButton)
    assert window.status_footer.state == "Running…"
    QTest.mouseClick(window.home_page._demo_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: len(window._service.history()) == 1, timeout=30_000)
    qtbot.waitUntil(lambda: window._demo_thread is None, timeout=30_000)
    assert len(window._service.history()) == 1
    assert window.status_footer.state == "Ready"


# --- Settings inline acceptance-checker editor -------------------------------------------
def minimal_acceptance_setup(tmp_path: Path) -> tuple[Path, tuple[str, ...]]:
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({"invoice_number": "INV-1", "total": 100.0}), encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            [
                {
                    "case_id": "inv-1",
                    "input_file": str(invoice),
                    "expected": {"total": {"value": 100.0, "mode": "exact", "required": True}},
                }
            ]
        ),
        encoding="utf-8",
    )
    return cases, (sys.executable, "{input}")


def test_verifier_configuration_saves_through_the_inline_panel(qtbot, window, tmp_path):
    """The panel performs a real save; the page reports it on its banner."""
    from controller.verifier_config import load_verifier_config

    page = window.settings_page
    configured_flags: list[bool] = []
    page.verifier_configured.connect(lambda: configured_flags.append(True))
    data_dir = tmp_path / "appdata"
    page.configure(app_data_dir=data_dir, verifier_config=None)
    cases_path, argv = minimal_acceptance_setup(tmp_path)
    # Navigate the real sidebar switch so the page (and its banner) is on
    # screen; asserts below check Qt visibility, which needs a current page.
    qtbot.mouseClick(window.sidebar._settings_button, Qt.MouseButton.LeftButton)

    page._configure_verifier()

    assert page._verifier_panel.isVisible()
    panel = page._verifier_panel
    panel._cases_path.setText(str(cases_path))
    panel._arguments.setPlainText("\n".join(argv))
    panel._timeout.setValue(10.0)
    panel._worktree_root.setText(str(tmp_path / "worktrees"))

    QTest.mouseClick(panel._save_button, Qt.MouseButton.LeftButton)

    assert configured_flags == [True]
    assert "saved" in page._banner.title_text.casefold()
    assert not panel.isVisible()
    reload_from_disk = load_verifier_config(data_dir)
    assert reload_from_disk is not None
    assert reload_from_disk.argv == argv
    assert reload_from_disk.timeout_seconds == 10.0


def test_verifier_configuration_without_data_folder_uses_banner(qtbot, window):
    """No data folder: explain on the page banner; never open a blocking modal."""
    page = window.settings_page
    page.configure(app_data_dir=None, verifier_config=None)
    # Click into Settings so the page is the current (visible) workspace page.
    qtbot.mouseClick(window.sidebar._settings_button, Qt.MouseButton.LeftButton)

    page._configure_verifier()

    assert page._banner.isVisible()
    assert "data folder" in page._banner.body_text.casefold()
    assert not page._verifier_panel.isVisible()
