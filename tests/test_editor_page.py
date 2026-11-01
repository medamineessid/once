"""Acceptance coverage for creating an automation in the shell editor.

A1 replacement (logged as AD-018): the old single test asserted that a row
showed the internal workflow id (`automation-<uuid>`); it now types a user
name into the editor header, saves, opens into review, runs, and checks My
automations, Activity, and the review page all show the chosen name.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from controller.service import WorkflowService
from engine.workflow import StepKind, StepResult, StepStatus, Workflow, WorkflowStep
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


def test_editor_actions_have_visible_button_styles(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    window._show_editor()

    assert window.editor_page._add_button.objectName() == "primaryActionButton"
    assert window.editor_page._undo_button.objectName() == "secondaryActionButton"
    assert window.editor_page._redo_button.objectName() == "secondaryActionButton"
    assert window.editor_page._save_button.objectName() == "primaryActionButton"
    assert window.editor_page._run_button.objectName() == "primaryActionButton"


def test_editor_run_requires_a_saved_definition(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    window._show_editor()
    qtbot.mouseClick(window.editor_page._add_button, Qt.MouseButton.LeftButton)

    qtbot.mouseClick(window.editor_page._run_button, Qt.MouseButton.LeftButton)

    assert window.editor_page._banner.isVisible()
    assert window.editor_page._banner.title_text == "Save before running"
    assert window._editor_thread is None


def test_saved_editor_definition_runs_and_refreshes_activity(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    _create_and_rename(window, qtbot, "Run from editor")
    qtbot.mouseClick(window.editor_page._save_button, Qt.MouseButton.LeftButton)
    saved_path = window._service.list_saved()[0]
    workflow = window._service.load(saved_path)
    window.editor_page.open_workflow(workflow)
    window._show_page(ShellPages.EDITOR)

    qtbot.mouseClick(window.editor_page._run_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._editor_thread is None, timeout=10_000)

    assert "finished successfully" in window.editor_page._banner.body_text
    assert len(window._service.history()) == 1
    window._show_page_activity()
    assert window.activity_page._history_list.count() == 1


def test_editor_shows_existing_desktop_approval_gate(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    workflow = Workflow(
        "desktop-workflow",
        "Desktop task",
        (
            WorkflowStep(
                "step-1",
                "Type a value",
                StepKind.TYPE_TEXT,
                "Type a value",
                target=(
                    '{"window":{"title":"Notepad"},"element":{"class_name":"Edit"},"text":"value"}'
                ),
            ),
        ),
    )
    window.editor_page.open_workflow(workflow)
    window._show_page(ShellPages.EDITOR)

    qtbot.mouseClick(window.editor_page._run_button, Qt.MouseButton.LeftButton)

    assert window.editor_page._approval_panel.isVisible()
    assert "TYPE_TEXT" in window.editor_page._approval_details.text()
    assert window._editor_thread is None


def test_editor_shows_step_result_and_evidence_in_inspector(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    window._show_editor()
    qtbot.mouseClick(window.editor_page._add_button, Qt.MouseButton.LeftButton)
    window.editor_page._canvas.select_node("step-1")

    result = StepResult(
        "step-1",
        StepStatus.SUCCEEDED,
        "The report was created.",
        ("rows=3", "redacted=true"),
    )
    window.editor_page.show_step_result(result)

    assert window.editor_page._canvas.nodes["step-1"].status == "SUCCEEDED"
    assert "Run status: SUCCEEDED" in window.editor_page._inspector.summary_text
    assert "redacted=true" in window.editor_page._inspector.summary_text


def test_empty_editor_add_step_button_creates_an_editable_node(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    window._show_editor()

    assert len(window.editor_page._session.workflow().steps) == 0
    qtbot.mouseClick(window.editor_page._add_button, Qt.MouseButton.LeftButton)

    assert len(window.editor_page._session.workflow().steps) == 1
    assert "New step" in window.editor_page._steps_list.item(0).text()
    window.editor_page._canvas.select_node("step-1")
    assert "New step" in window.editor_page._inspector.summary_text


def test_moved_node_is_saved_as_presentation_metadata(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    _create_and_rename(window, qtbot, "Positioned automation")
    node = window.editor_page._canvas.nodes["step-1"]
    node.setPos(321.0, 123.0)

    qtbot.mouseClick(window.editor_page._save_button, Qt.MouseButton.LeftButton)

    loaded = window._service.load_layout(window.editor_page._session.workflow().workflow_id)
    assert loaded.record is not None
    assert loaded.record.node_positions["step-1"] == (321.0, 123.0)


def test_unsaved_bar_can_stay_then_discard_definition_changes(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    _create_and_rename(window, qtbot, "Unsaved automation")

    assert window.editor_page._dirty_panel.isVisible()
    stay = next(
        button
        for button in window.editor_page._dirty_panel.findChildren(
            type(window.editor_page._save_button)
        )
        if button.text() == "Stay"
    )
    qtbot.mouseClick(stay, Qt.MouseButton.LeftButton)
    assert not window.editor_page._dirty_panel.isVisible()

    qtbot.mouseClick(window.editor_page._add_button, Qt.MouseButton.LeftButton)
    assert window.editor_page._dirty_panel.isVisible()
    discard = next(
        button
        for button in window.editor_page._dirty_panel.findChildren(
            type(window.editor_page._save_button)
        )
        if button.text() == "Discard"
    )
    qtbot.mouseClick(discard, Qt.MouseButton.LeftButton)

    assert window.editor_page._session.workflow().name == "New automation"
    assert len(window.editor_page._session.workflow().steps) == 0
    assert not window.editor_page._dirty_panel.isVisible()


def test_editor_shortcuts_undo_outside_text_fields_but_not_inside_them(qtbot, tmp_path) -> None:
    window = _make_window(qtbot, tmp_path)
    _create_and_rename(window, qtbot, "Shortcut automation")
    assert window.editor_page._session.workflow().name == "Shortcut automation"

    name_input = window.editor_page._name_input
    name_input.setFocus()
    qtbot.keyClick(name_input, Qt.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window.editor_page._session.workflow().name == "Shortcut automation"

    window.editor_page._canvas.setFocus()
    qtbot.keyClick(window.editor_page._canvas, Qt.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window.editor_page._session.workflow().name == "New automation"
