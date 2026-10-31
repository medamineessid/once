"""Acceptance coverage for creating an automation in the shell editor."""

from __future__ import annotations

from PySide6.QtCore import Qt

from controller.service import WorkflowService
from ui.shell import MainWindow, ShellPages


def test_create_from_scratch_adds_saves_and_lists_automation(qtbot, tmp_path) -> None:
    window = MainWindow(service=WorkflowService.for_app_data(tmp_path))
    qtbot.addWidget(window)
    window.show()

    window._show_create_automation()
    qtbot.mouseClick(window.create_automation_page._scratch_button, Qt.MouseButton.LeftButton)
    assert window.workspace.currentWidget() is window.editor_page

    qtbot.mouseClick(window.editor_page._add_button, Qt.MouseButton.LeftButton)
    assert len(window.editor_page._session.workflow().steps) == 1
    qtbot.mouseClick(window.editor_page._save_button, Qt.MouseButton.LeftButton)

    assert window.workspace.currentIndex() == ShellPages.MY_AUTOMATIONS
    assert window.my_automations_page._workflow_list.count() == 1
    row = window.my_automations_page._workflow_list.itemWidget(
        window.my_automations_page._workflow_list.item(0)
    )
    assert (
        row._name_label.text()
        == "automation-"
        + window.editor_page._session.workflow().workflow_id.removeprefix("automation-")
    )

    window.my_automations_page._workflow_list.setCurrentRow(0)
    qtbot.mouseClick(window.my_automations_page._open_button, Qt.MouseButton.LeftButton)
    assert window.workspace.currentWidget() is window.review_page
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
