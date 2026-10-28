"""Quick smoke tests for the redesigned application shell."""

from __future__ import annotations

import pytest
from PySide6.QtCore import SIGNAL, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QToolButton

from ui.components.spacer import Spacer
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


def test_shell_injects_the_service_into_the_home_page(qtbot, window):
    # Without this, HomePage._refresh_activity() returns early and the Home
    # page shows an empty Recent activity block forever.
    assert window.home_page._service is not None
    assert window.home_page._service is window._service


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
    assert settings._verifier_group.isVisible() is True
    assert window.sidebar._settings_button.isChecked() is True


def test_settings_page_keeps_no_placeholder_controls(qtbot, window):
    """Settings shows only real configuration, never dead placeholder groups."""
    settings = window.settings_page
    for removed in (
        "_recordings_group",
        "_gemini_group",
        "_coding_agent_group",
        "_advanced_group",
        "_start_recording_button",
        "_stop_recording_button",
        "_delete_recording_button",
        "_connect_gemini_button",
        "_status_label",
    ):
        assert not hasattr(settings, removed), f"placeholder still present: {removed}"


def test_settings_verifier_button_saves_and_signals(qtbot, window, monkeypatch, tmp_path):
    """The verifier entry point uses the real editor dialog and reports the save."""
    settings = window.settings_page
    saved_flags: list[bool] = []
    seen_dirs: list[object] = []

    class FakeVerifierDialog:
        def __init__(self, app_data_dir, current=None, parent=None):
            seen_dirs.append(app_data_dir)
            self.saved = None

        def exec(self):
            self.saved = True
            return 1

    monkeypatch.setattr("ui.pages.settings.VerifierConfigDialog", FakeVerifierDialog)
    settings.verifier_configured.connect(lambda: saved_flags.append(True))

    settings.configure(app_data_dir=tmp_path)
    settings._configure_verifier()

    assert seen_dirs == [tmp_path]
    assert saved_flags == [True]


def test_settings_verifier_button_without_data_dir_does_not_crash(qtbot, window, monkeypatch):
    """Without a data folder Once explains itself instead of failing later."""
    settings = window.settings_page
    notices: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda parent, title, text, *a, **k: notices.append(text)
    )
    settings.configure(app_data_dir=None)
    settings._configure_verifier()
    assert len(notices) == 1


# --- Layout foundation (B3): structure and honest controls -------------------------------


def test_sidebar_has_four_nav_items_brand_and_one_footer(qtbot, window):
    widgets = [window.sidebar.widgetForAction(a) for a in window.sidebar.actions()]
    buttons = [w for w in widgets if isinstance(w, QToolButton)]
    labels = [w for w in widgets if isinstance(w, QLabel) and not isinstance(w, Spacer)]
    assert [b.text() for b in buttons] == ["Home", "My automations", "Activity", "Settings"]
    assert [label.text() for label in labels] == ["Once", "Once Assistive Automation"]


def test_every_page_has_no_unwired_buttons(qtbot, window):
    """Honest-controls rule: a visible enabled button must be actually connected."""
    pages = [
        window.home_page,
        window.my_automations_page,
        window.activity_page,
        window.settings_page,
        window.review_page,
        window.create_automation_page,
    ]
    unwired: list[str] = []
    for page in pages:
        window.workspace.setCurrentWidget(page)
        qtbot.wait(10)
        for button in page.findChildren(QPushButton):
            if (
                button.isVisible()
                and button.isEnabled()
                and button.receivers(SIGNAL("clicked()")) == 0
            ):
                unwired.append(f"{page.__class__.__name__}: {button.text()}")
    assert unwired == []


def test_pages_use_spacing_tokens_for_margins(qtbot, window):
    from ui.styles import SPACING_VALUES

    layouts = [
        window.home_page.layout(),
        window.my_automations_page.layout(),
        window.activity_page.layout(),
        window.create_automation_page.layout(),
        window.review_page.layout(),
        window.settings_page._scroll_layout,
    ]
    for layout in layouts:
        margins = layout.contentsMargins()
        for value in (margins.left(), margins.top(), margins.right(), margins.bottom()):
            assert value in SPACING_VALUES


def test_type_scale_is_declared_once_in_the_theme(qtbot, window):
    from ui.styles import (
        TYPE_CAPTION_PX,
        TYPE_HOME_TITLE_PX,
        TYPE_QUESTION_PX,
        TYPE_SUBTITLE_PX,
        TYPE_TITLE_PX,
    )

    pages = [
        window.home_page,
        window.my_automations_page,
        window.activity_page,
        window.create_automation_page,
        window.review_page,
        window.settings_page,
    ]
    for page in pages:
        for widget in (*page.findChildren(QLabel), *page.findChildren(QPushButton)):
            assert "font-size:" not in widget.styleSheet(), (
                f"inline font-size on {page.__class__.__name__}: {widget.styleSheet()}"
            )

    sheet = QApplication.instance().styleSheet()
    for rule, size in (
        ("QLabel#pageTitle", TYPE_TITLE_PX),
        ("QLabel#pageSubtitle", TYPE_SUBTITLE_PX),
        ("QLabel#homeTitle", TYPE_HOME_TITLE_PX),
        ("QLabel#questionLabel", TYPE_QUESTION_PX),
        ("QLabel#hintLabel", TYPE_CAPTION_PX),
    ):
        start = sheet.index(rule)
        block = sheet[start : sheet.index("}", start)]
        assert f"font-size: {size}px" in block, f"{rule} does not use its token"
    assert window.sidebar._home_button.styleSheet() == ""


def test_sidebar_buttons_resist_stuck_repeats(qtbot, window):
    assert window.sidebar._home_button.autoRepeat() is False
    assert window.sidebar._automations_button.autoRepeat() is False
    assert window.sidebar._activity_button.autoRepeat() is False
    assert window.sidebar._settings_button.autoRepeat() is False
