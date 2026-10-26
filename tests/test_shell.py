"""Quick smoke tests for the redesigned application shell."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from ui.shell import MainWindow, ShellPages


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


@pytest.fixture
def window(qtbot, app):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    yield window


def test_page_navigation_switches_workspace(qtbot, window):
    qtbot.mouseClick(window.sidebar._automations_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert window.workspace.currentIndex() == ShellPages.MY_AUTOMATIONS


def test_home_page_shows_welcome_and_empty_activity(qtbot, window):
    home = window.home_page
    assert window.workspace.currentIndex() == ShellPages.HOME
    title = home._title_label.text()
    subtitle = home._subtitle_label.text()
    assert "Once" in title
    assert "personal assistant" in subtitle
    assert home._activity_empty.isVisible() is True


def test_create_automation_page_has_description_input(qtbot, window):
    window._show_create_automation()
    page = window.create_automation_page
    input_field = page._description_input
    assert input_field.placeholderText().startswith("Example:")
    QTest.keyClicks(input_field, "Open invoices folder and read PDFs")
    assert page._description_input.toPlainText() == "Open invoices folder and read PDFs"


def test_create_automation_button_emits_typed_task(qtbot, window, monkeypatch):
    notices: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text, *args, **kwargs: notices.append(text),
    )
    window._show_create_automation()
    page = window.create_automation_page
    page._description_input.setPlainText("Open invoices folder and read PDFs")
    received: list[str] = []
    page.task_entered.connect(received.append)

    qtbot.mouseClick(page._create_button, Qt.MouseButton.LeftButton)

    assert received == ["Open invoices folder and read PDFs"]
    assert len(notices) == 1
    assert "cannot turn this description into an automation yet" in notices[0]


def test_create_automation_button_ignores_blank_input(qtbot, window, monkeypatch):
    notices: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text, *args, **kwargs: notices.append(text),
    )
    window._show_create_automation()
    page = window.create_automation_page
    page._description_input.setPlainText("   ")
    received: list[str] = []
    page.task_entered.connect(received.append)

    qtbot.mouseClick(page._create_button, Qt.MouseButton.LeftButton)

    assert received == []
    assert notices == []


def test_sidebar_active_state_after_sidebar_click(qtbot, window):
    qtbot.mouseClick(window.sidebar._activity_button, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert window.sidebar.is_on(ShellPages.ACTIVITY)


def test_settings_page_opens_from_sidebar(qtbot, window):
    window._show_page(ShellPages.SETTINGS)
    qtbot.wait(50)
    settings = window.settings_page
    assert window.workspace.currentIndex() == ShellPages.SETTINGS
    assert settings._authorized_group.isVisible() is True
    assert settings._recordings_group.isVisible() is True
    assert settings._gemini_group.isVisible() is True
    assert settings._coding_agent_group.isVisible() is True
    assert settings._advanced_group.isVisible() is True


def test_settings_page_shows_placeholder_integration_messages(qtbot, window):
    window._show_page(ShellPages.SETTINGS)
    qtbot.wait(50)
    settings = window.settings_page
    settings._start_recording()
    settings._connect_gemini()
    assert settings._status_label.isVisible() is True
    assert settings._status_label.text().startswith("Connect Gemini")
    settings._disconnect_gemini()
    assert settings._status_label.text().startswith("Disconnect Gemini")
    settings._open_coding_agent_proposals()
    assert settings._status_label.text().startswith("There are no recorded")
    settings._open_coding_agent_review()
    assert settings._status_label.text().startswith("No proposal is ready")
    settings._delete_recording()
    assert settings._status_label.text().startswith("No recording is selected")


def test_settings_page_has_recording_controls(qtbot, window):
    settings = window.settings_page
    assert settings._start_recording_button.text() == "Start recording"
    assert settings._stop_recording_button.text() == "Stop recording"
    assert settings._delete_recording_button.text() == "Delete selected"
    assert settings._start_recording_button.isEnabled() is True
    assert settings._stop_recording_button.isEnabled() is True
    assert settings._delete_recording_button.isEnabled() is True


def test_sidebar_buttons_resist_stuck_repeats(qtbot, window):
    assert window.sidebar._home_button.autoRepeat() is False
    assert window.sidebar._automations_button.autoRepeat() is False
    assert window.sidebar._activity_button.autoRepeat() is False
    assert window.sidebar._settings_button.autoRepeat() is False
