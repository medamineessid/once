"""Acceptance coverage for creating an automation in the shell editor.

A1 replacement (logged as AD-018): the old single test asserted that a row
showed the internal workflow id (`automation-<uuid>`); it now types a user
name into the editor header, saves, opens into review, runs, and checks My
automations, Activity, and the review page all show the chosen name.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from controller.service import WorkflowService
from ui.shell import MainWindow, ShellPages


def _make_window(qtbot, tmp_path) -> MainWindow:
    window = MainWindow(service=WorkflowService.for_app_data(tmp_path))
    qtbot.addWidget(window)
    window.show()
    return window


def _create_and_rename(window: MainWindow, qtbot, name: str) -> None:
    """Create a one-step automation and rename it through the editor header."""
    window._show_create_automation()
    qtbot.mouseClick(window.create_automation_page._scratch_button, Qt.MouseButton.LeftButton)
    assert window.workspace.currentWidget() is window.editor_page

    qtbot.mouseClick(window.editor_page._add_button, Qt.MouseButton.LeftButton)
    assert len(window.editor_page._session.workflow().steps) == 1

    name_input = window.editor_page._name_input
    name_input.setFocus()
    name_input.clear()
    qtbot.keyClicks(name_input, name)
    qtbot.keyClick(name_input, Qt.Key_Return)
    assert window.editor_page._session.workflow().name == name


def test_create_rename_save_lists_opens_runs_and_activity_shows_name(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    _create_and_rename(window, qtbot, "My test automation")
    qtbot.mouseClick(window.editor_page._save_button, Qt.MouseButton.LeftButton)

    assert window.workspace.currentIndex() == ShellPages.MY_AUTOMATIONS
    assert window.my_automations_page._workflow_list.count() == 1
    row = window.my_automations_page._workflow_list.itemWidget(
        window.my_automations_page._workflow_list.item(0)
    )
    assert row._name_label.text() == "My test automation"

    window.my_automations_page._workflow_list.setCurrentRow(0)
    qtbot.mouseClick(window.my_automations_page._open_button, Qt.MouseButton.LeftButton)
    assert window.workspace.currentWidget() is window.review_page
    assert window.review_page._goal_label.text() == "Goal: My test automation"

    window._show_page_automations()
    window.my_automations_page._workflow_list.setCurrentRow(0)
    qtbot.mouseClick(window.my_automations_page._run_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    qtbot.mouseClick(window.my_automations_page._run_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: "Run SUCCEEDED" in window.my_automations_page._details_label.text(),
        timeout=5000,
    )
    window._show_page_activity()
    assert window.activity_page._history_list.count() == 1
    first_activity = window.activity_page._history_list.itemWidget(
        window.activity_page._history_list.item(0)
    )
    assert first_activity is not None
    assert "My test automation" in first_activity._name_label.text()


def test_editor_rename_is_undoable_and_updates_the_field(qtbot, tmp_path) -> None:
    """The rename is a controller edit operation: Undo/Redo reverse it and
    the header field always reflects the current session name."""
    window = _make_window(qtbot, tmp_path)
    _create_and_rename(window, qtbot, "My test automation")

    qtbot.mouseClick(window.editor_page._undo_button, Qt.MouseButton.LeftButton)
    assert window.editor_page._session.workflow().name == "New automation"
    assert window.editor_page._name_input.text() == "New automation"

    qtbot.mouseClick(window.editor_page._redo_button, Qt.MouseButton.LeftButton)
    assert window.editor_page._session.workflow().name == "My test automation"
    assert window.editor_page._name_input.text() == "My test automation"


def test_clearing_the_name_keeps_previous_name_and_warns_inline(qtbot, tmp_path) -> None:
    """An empty name is never accepted: the previous name is preserved
    (modal-free inline warning) and nothing is renamed."""
    window = _make_window(qtbot, tmp_path)
    _create_and_rename(window, qtbot, "My test automation")

    name_input = window.editor_page._name_input
    name_input.setFocus()
    name_input.clear()
    qtbot.keyClick(name_input, Qt.Key_Return)

    assert window.editor_page._session.workflow().name == "My test automation"
    assert name_input.text() == "My test automation"
    assert window.editor_page._banner.isVisible()
    assert "needs a name" in window.editor_page._banner.body_text
