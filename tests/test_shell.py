"""Quick smoke tests for the redesigned application shell."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

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
    empty = home._activity_empty
    assert home._activity_empty.isVisible() is True


def test_create_automation_page_has_description_input(qtbot, window):
    window._show_create_automation()
    page = window.create_automation_page
    input_field = page._description_input
    assert input_field.placeholderText().startswith("Example:")
    QTest.keyClicks(input_field, "Open invoices folder and read PDFs")
    assert page._description_input.toPlainText() == "Open invoices folder and read PDFs"
