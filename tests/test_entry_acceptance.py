"""First-time user journey through the real application entry point.

Closes the two pending MVP acceptance rows in docs/MVP_CHECKLIST.md: the
first-run journey and the editor acceptance are the same flow, driven here
through ``app.build_window`` — the exact wiring ``app.main`` runs on every
launch, with real services on an isolated LOCALAPPDATA (never real user data).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from app import build_window
from ui.shell import MainWindow

DATASET_ROOT = "appdata-entry-journey"


@pytest.fixture
def entry_shell(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[MainWindow, object]:
    """Launch the real --shell window through app.py wiring on tmp_path data."""
    app_dir = tmp_path / DATASET_ROOT
    monkeypatch.setenv("LOCALAPPDATA", str(app_dir))
    app, window, service = build_window(["--shell"])[:3]
    qtbot.addWidget(window)
    window.show()
    yield window, service
    # Flush pending UI jobs before shutting the real service down.
    app.processEvents()
    window.close()
    app.processEvents()
    service.close()
    for handler in logging.getLogger().handlers[:]:
        if "once.log" in str(getattr(handler, "baseFilename", "")):
            logging.getLogger().removeHandler(handler)
            handler.close()


def test_first_run_home_offers_two_working_entry_points(entry_shell) -> None:
    window, _ = entry_shell
    home = window.home_page
    assert window.workspace.currentWidget() is home
    assert home._title_label.isVisible()
    create_button = home._create_automation_button
    record_button = home._record_button
    assert create_button is not None and create_button.isEnabled()
    assert record_button is not None and record_button.isEnabled()

    # The empty first-run activity list says what to do, not nothing.
    assert not home._activity_rows
    assert home._activity_empty.isVisible()


def test_first_time_journey_through_entry_point_creates_and_runs(entry_shell, qtbot) -> None:
    window, _ = entry_shell

    # 1. Home's primary card opens the visual editor directly.
    qtbot.mouseClick(window.home_page._create_automation_button, Qt.MouseButton.LeftButton)
    assert window.workspace.currentWidget() is window.editor_page

    # 2. Build a one-step automation in the editor with a real user name.
    qtbot.mouseClick(window.editor_page._add_button, Qt.MouseButton.LeftButton)
    assert len(window.editor_page._session.workflow().steps) == 1
    name_input = window.editor_page._name_input
    name_input.setFocus()
    name_input.clear()
    qtbot.keyClicks(name_input, "Entry point journey")
    qtbot.keyClick(name_input, Qt.Key_Return)
    assert window.editor_page._session.workflow().name == "Entry point journey"

    # 3. Save; the shell then shows the saved automations list.
    qtbot.mouseClick(window.editor_page._save_button, Qt.MouseButton.LeftButton)
    assert window.workspace.currentWidget() is window.my_automations_page
    assert window.my_automations_page._workflow_list.count() == 1

    # 4. Run the saved automation from My automations.
    window.my_automations_page._workflow_list.setCurrentRow(0)
    qtbot.mouseClick(window.my_automations_page._run_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    qtbot.mouseClick(window.my_automations_page._run_button, Qt.MouseButton.LeftButton)
    # The one-step automation only reports, so the run is observation only.
    qtbot.waitUntil(
        lambda: "Run Observation only" in window.my_automations_page._details_label.text(),
        timeout=5000,
    )

    # 5. The persisted history is visible on Activity and named on Home.
    window._show_page_activity()
    assert window.activity_page._history_list.count() == 1
    window.home_page.refresh()
    assert window.home_page._activity_rows
