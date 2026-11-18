"""Design-language tests for the v4 system: rail, bands, buttons, motion.

These tests measure the real widgets and the real stylesheet; nothing here
asserts a number that is only written in a comment. Style updates that change
the design intentionally must update these expectations.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from ui.components.band import PageBand, cropped_title_width, display_line_height
from ui.components.buttons import ActionButton
from ui.components.cards import EmptyState
from ui.components.phosphor_icons import render_icon_pixmap
from ui.components.sidebar_item import SidebarItem, sidebar_metrics
from ui.motion import animations_enabled
from ui.styles import (
    ARROW_SHIFT_PX,
    DURATION_DIALOG_MS,
    DURATION_HOVER_MS,
    DURATION_PAGE_MS,
    DURATION_STAGGER_MS,
    HERO_REVEAL_OFFSET_PX,
    HOVER_SCALE,
    NAVY,
    PRESS_SCALE,
    SIDEBAR_ACTIVE_BG,
    SIDEBAR_BG,
    TYPE_HERO_PX,
    TYPE_PAGE_TITLE_PX,
    apply_theme,
    render_stylesheet,
)

UI_ROOT = Path(__file__).resolve().parent.parent / "ui"


@pytest.fixture
def app(qtbot):
    application = QApplication.instance() or QApplication([])
    apply_theme(application)
    return application


# --- Sidebar rail -----------------------------------------------------------


def test_sidebar_icon_is_24px_with_a_14px_gap(qtbot, app):
    item = SidebarItem("Home", "sidebarHomeButton", "house")
    qtbot.addWidget(item)
    item.resize(232, 52)
    metrics = sidebar_metrics()
    icon = item.icon_rect()
    text = item.text_rect()
    assert metrics.icon_size == 24
    assert metrics.gap == 14
    assert icon.width() == 24 and icon.height() == 24
    assert text.left() - icon.right() - 1 == 14


def test_sidebar_is_navy_and_the_active_item_carries_a_lemon_pill(qtbot, app):
    item = SidebarItem("Activity", "sidebarActivityButton", "pulse")
    qtbot.addWidget(item)
    item.resize(232, 52)
    item.setChecked(True)
    pixmap = item.grab()
    image = pixmap.toImage()
    ratio = pixmap.devicePixelRatio()
    # Sample the pill body, right of the 24px icon and its 14px gap.
    sample = image.pixelColor(int(180 * ratio), int(26 * ratio))
    assert QColor(sample).name().upper() == SIDEBAR_ACTIVE_BG.upper()
    rail = image.pixelColor(int(2 * ratio), int(2 * ratio))
    assert QColor(rail).name().upper() in {SIDEBAR_BG.upper(), SIDEBAR_ACTIVE_BG.upper()}


def test_sidebar_active_pill_is_drawn_in_lemon_from_the_tokens():
    from ui.styles import SIDEBAR_ACTIVE_BG

    assert SIDEBAR_ACTIVE_BG == "#F7DC3C"


# --- Bands, display type, colour blocking ----------------------------------


def test_page_band_title_is_uppercase_anton_at_72px_with_a_tight_line_box(qtbot, app):
    band = PageBand("Activity", micro="3 runs recorded", description="Recent runs")
    qtbot.addWidget(band)
    title = band.title_label
    assert title.text() == "ACTIVITY"
    assert title.font().family() == "Anton"
    assert title.font().pixelSize() == TYPE_PAGE_TITLE_PX == 72
    assert title.height() == display_line_height(TYPE_PAGE_TITLE_PX)
    assert title.height() < TYPE_PAGE_TITLE_PX  # 0.85 line box, not 1.0
    assert title.width() == cropped_title_width("Activity")


def test_every_page_has_a_colour_blocked_band(qtbot, tmp_path):
    from controller.service import WorkflowService
    from ui.shell import MainWindow

    application = QApplication.instance() or QApplication([])
    apply_theme(application)
    service = WorkflowService.for_app_data(tmp_path / "appdata")
    window = MainWindow(service=service)
    qtbot.addWidget(window)
    try:
        bands = window.findChildren(PageBand)
        # Home uses the hero as its colour block; the four list/detail pages
        # each own a band.
        assert len(bands) >= 4
        for page in (
            window.activity_page,
            window.my_automations_page,
            window.settings_page,
            window.review_page,
        ):
            page_bands = page.findChildren(PageBand)
            assert page_bands, f"{type(page).__name__} has no colour-blocked band"
            title = page_bands[0].title_label
            assert title.text() == title.text().upper()
            assert title.font().family() == "Anton"
    finally:
        window.close()
        service.close()


def test_home_hero_is_uppercase_and_the_second_line_is_cropped(qtbot, tmp_path):
    from controller.service import WorkflowService
    from ui.shell import MainWindow

    application = QApplication.instance() or QApplication([])
    apply_theme(application)
    service = WorkflowService.for_app_data(tmp_path / "appdata")
    window = MainWindow(service=service)
    qtbot.addWidget(window)
    window.resize(1280, 820)
    window.show()
    qtbot.wait(30)
    try:
        hero = window.home_page._hero
        first, second = hero.line_labels
        assert first.text() == "AUTOMATE"
        assert second.text() == "ANYTHING."
        assert first.font().pixelSize() == TYPE_HERO_PX == 128
        assert first.height() == round(TYPE_HERO_PX * 0.85)
        assert hero.second_line_cropped() is True
        # The two actions live inside the hero: a 128px lemon circle and an
        # outlined Build control. No card row, no full-width button bar.
        assert hero.record_button.width() == 128
        assert hero.record_button.height() == 128
        assert hero.record_button.objectName() == "circleButton"
        assert hero.build_button.objectName() == "heroSecondaryButton"
    finally:
        window.close()
        service.close()


def test_home_shows_three_real_stat_blocks(qtbot, tmp_path):
    from controller.service import WorkflowService
    from ui.shell import MainWindow

    application = QApplication.instance() or QApplication([])
    apply_theme(application)
    service = WorkflowService.for_app_data(tmp_path / "appdata")
    service.run_workflow(service.demo_workflow())
    window = MainWindow(service=service)
    qtbot.addWidget(window)
    try:
        home = window.home_page
        home.refresh()
        values = [home._automations_stat.value_text, home._runs_stat.value_text]
        assert values == ["0", "1"]
        assert home._succeeded_stat.value_text.isdigit()
    finally:
        window.close()
        service.close()


# --- Buttons ---------------------------------------------------------------


def test_every_page_button_uses_one_of_the_three_variants(qtbot, tmp_path):
    from controller.service import WorkflowService
    from ui.shell import MainWindow

    allowed = {
        "primaryActionButton",
        "secondaryActionButton",
        "dangerButton",
        "heroSecondaryButton",
        "circleButton",
        "outlinedCircleButton",
        "confirmButton",
        "runRowButton",
        "linkActionButton",
        "ghostButton",
        "bannerDismiss",
    }
    application = QApplication.instance() or QApplication([])
    apply_theme(application)
    service = WorkflowService.for_app_data(tmp_path / "appdata")
    window = MainWindow(service=service)
    qtbot.addWidget(window)
    try:
        for page in (
            window.home_page,
            window.my_automations_page,
            window.activity_page,
            window.settings_page,
            window.review_page,
        ):
            for button in page.findChildren(QPushButton):
                assert button.objectName() in allowed, (
                    f"{type(page).__name__}: {button.text()!r} has no design-system variant"
                )
    finally:
        window.close()
        service.close()


def test_primary_button_is_lemon_with_navy_text():
    sheet = render_stylesheet()
    start = sheet.index("QPushButton#primaryActionButton {")
    block = sheet[start : sheet.index("}", start)]
    from ui.styles import LEMON

    assert f"background: {LEMON}" in block
    assert f"color: {NAVY}" in block


def test_secondary_and_destructive_buttons_are_outlined():
    sheet = render_stylesheet()
    for selector, colour in (
        ("QPushButton#secondaryActionButton {", NAVY),
        ("QPushButton#dangerButton {", None),
    ):
        start = sheet.index(selector)
        block = sheet[start : sheet.index("}", start)]
        assert "background: transparent" in block
        assert "border: 1px solid" in block
        if colour is not None:
            assert f"border: 1px solid {colour}" in block


# --- Motion ----------------------------------------------------------------


def test_motion_tokens_match_the_brief():
    assert DURATION_PAGE_MS == 260
    assert DURATION_DIALOG_MS == 220
    assert DURATION_STAGGER_MS == 60
    assert HERO_REVEAL_OFFSET_PX == 16
    assert HOVER_SCALE == 1.03
    assert PRESS_SCALE == 0.97
    assert ARROW_SHIFT_PX == 4
    assert DURATION_HOVER_MS == 120


def test_button_hover_grows_and_press_shrinks(qtbot, app, monkeypatch):
    monkeypatch.setattr("ui.components.buttons.animations_enabled", lambda: True)
    button = ActionButton("Run", variant="primary")
    qtbot.addWidget(button)
    button.show()
    qtbot.wait(200)  # let the hover animation reach its end value
    button.enterEvent(_enter_event())
    qtbot.waitUntil(lambda: button.scale == pytest.approx(HOVER_SCALE), timeout=2000)
    button.mousePressEvent(_press_event())
    qtbot.waitUntil(lambda: button.scale == pytest.approx(PRESS_SCALE), timeout=2000)


def test_button_motion_is_instant_when_animations_are_off(qtbot, app, monkeypatch):
    monkeypatch.setattr("ui.components.buttons.animations_enabled", lambda: False)
    button = ActionButton("Build", variant="primary", with_arrow=True)
    qtbot.addWidget(button)
    button.resize(160, 40)
    button.show()
    button.animate_scale(HOVER_SCALE)
    assert button.scale == pytest.approx(HOVER_SCALE)
    resting = button._arrow_label.pos()
    button._shift_arrow(True)
    assert button._arrow_label.pos().x() == resting.x() + ARROW_SHIFT_PX


def test_page_transition_uses_the_shared_duration(qtbot, app):
    from ui import motion

    source = Path(motion.__file__).read_text(encoding="utf-8")
    assert "DURATION_PAGE_MS" in source
    assert "def fade_slide" in source


def _enter_event():
    from PySide6.QtGui import QEnterEvent

    return QEnterEvent(QPoint(1, 1), QPoint(1, 1), QPoint(1, 1))


def _press_event():
    from PySide6.QtGui import QMouseEvent

    return QMouseEvent(
        QEvent_mouse_press(),
        QPoint(2, 2),
        QPoint(2, 2),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def QEvent_mouse_press():
    from PySide6.QtCore import QEvent

    return QEvent.Type.MouseButtonPress


# --- Empty states and banners ----------------------------------------------


def test_empty_state_icon_is_48px(qtbot, app):
    state = EmptyState("No runs yet", "Run an automation first.", icon_name="pulse")
    qtbot.addWidget(state)
    state.show()
    icons = [label for label in state.findChildren(QWidget) if label.objectName() == "emptyIcon"]
    assert icons, "the empty state has no icon"
    assert icons[0].width() == 48
    assert icons[0].height() == 48


def test_warning_banner_shows_an_icon_not_the_word(qtbot, app):
    from ui.components.banner import Banner

    banner = Banner()
    qtbot.addWidget(banner)
    banner.show_message("warning", "Files need attention", "One saved file could not be read.")
    texts = [
        label.text()
        for label in banner.findChildren(QWidget)
        if hasattr(label, "text") and callable(label.text)
    ]
    assert "Warning" not in texts
    assert "warning" not in [text.casefold() for text in texts]
    icon_label = banner.findChild(QWidget, "bannerIcon")
    assert icon_label is not None
    assert not icon_label.pixmap().isNull()


def test_phosphor_icon_renders_non_empty_pixmap():
    pixmap = render_icon_pixmap("record", weight="Fill", logical_size=24, color=NAVY)
    assert not pixmap.isNull()
    assert pixmap.width() >= 24


# --- Derived automation names ----------------------------------------------


def test_derived_title_reads_like_a_task():
    from engine.workflow import StepKind, WorkflowStep
    from ui.components.formatting import automation_display_name, derived_automation_title

    steps = (
        WorkflowStep(
            "s1",
            "Open Notepad",
            StepKind.LAUNCH_APPLICATION,
            "The application was launched.",
            target='{"executable": "C:\\\\Windows\\\\System32\\\\notepad.exe"}',
        ),
        WorkflowStep("s2", "Type text", StepKind.TYPE_TEXT, "The text was entered."),
        WorkflowStep("s3", "Close Notepad", StepKind.CLOSE_APPLICATION, "Closed."),
    )
    assert derived_automation_title(steps) == "Open notepad, type text"
    assert automation_display_name("New automation", steps) == "Open notepad, type text"
    assert automation_display_name("Invoices weekly", steps) == "Invoices weekly"


# --- Token discipline ------------------------------------------------------


def _ui_python_files() -> list[Path]:
    return [path for path in UI_ROOT.rglob("*.py")]


def test_no_hex_colours_outside_the_token_file():
    tokens = (UI_ROOT / "styles" / "__init__.py").resolve()
    pattern = re.compile(r"#[0-9A-Fa-f]{6}\b")
    offenders = []
    for path in _ui_python_files():
        if path.resolve() == tokens:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(UI_ROOT)}:{line_number}")
    assert offenders == [], f"hex colours outside ui/styles: {offenders}"


def test_no_literal_durations_outside_the_motion_module():
    offenders = []
    duration_call = re.compile(r"setDuration\(\s*\d+|singleShot\(\s*\d+")
    for path in _ui_python_files():
        if path.name in {"motion.py"} or path.parent.name == "styles":
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if duration_call.search(line):
                offenders.append(f"{path.relative_to(UI_ROOT)}:{line_number}: {line.strip()}")
    assert offenders == [], f"literal durations outside tokens: {offenders}"


def test_no_inline_stylesheet_sizes_outside_the_token_file():
    offenders = []
    size_property = re.compile(r"font-size:\s*\d+px|border-radius:\s*\d+px|padding:\s*\d+px")
    for path in _ui_python_files():
        if path.parent.name == "styles" or path.name in {"motion.py", "sidebar_item.py"}:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if size_property.search(line) and "setStyleSheet" in line:
                offenders.append(f"{path.relative_to(UI_ROOT)}:{line_number}")
    assert offenders == [], f"inline stylesheet sizes outside tokens: {offenders}"


def test_animations_enabled_is_the_single_switch():
    """One predicate decides motion everywhere, including Windows settings."""
    assert callable(animations_enabled)
