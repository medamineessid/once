"""Unit tests for the P2 shared components.

A control counts as WORKING only when a test clicks it and asserts an
observable effect, so every interaction below goes through real clicks or
the component's public API.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ui.components.banner import Banner
from ui.components.cards import Card, Chip, EmptyState
from ui.components.confirm import InlineConfirm
from ui.components.footer import NEEDS_ATTENTION, READY, RUNNING, StatusFooter
from ui.components.formatting import human_timestamp, status_display
from ui.components.icons import (
    draw_activity_glyph,
    draw_alert_circle,
    draw_automations_glyph,
    draw_check_circle,
    draw_home_glyph,
    draw_info_circle,
    draw_settings_glyph,
    icon_pixmap,
)
from ui.components.pageheader import PageHeader
from ui.styles import CONTRAST_PAIRS
from ui.styles.contrast import contrast_ratio


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


# --- Banner ----------------------------------------------------------------------
def test_banner_shows_severity_title_and_body(qtbot, app):
    banner = Banner()
    qtbot.addWidget(banner)
    assert banner.isHidden()

    banner.show_message("error", "Something failed", "Try again.")

    assert banner.isVisible()
    assert banner.title_text == "Something failed"
    assert banner.body_text == "Try again."


def test_banner_dismiss_click_hides_and_signals(qtbot, app):
    banner = Banner()
    qtbot.addWidget(banner)
    banner.show_message("info", "Heads up", "Details.")
    dismissed: list[bool] = []
    banner.dismissed.connect(lambda: dismissed.append(True))

    QTest.mouseClick(banner._dismiss, Qt.MouseButton.LeftButton)

    assert banner.isHidden()
    assert dismissed == [True]


def test_banner_can_close_without_dismiss_button(qtbot, app):
    banner = Banner()
    qtbot.addWidget(banner)
    banner.show_message("warning", "Careful", "...", dismiss_button=False)
    assert banner._dismiss.isHidden()


# --- InlineConfirm ----------------------------------------------------------------
def test_inline_confirm_first_click_arms_only(qtbot, app):
    confirm = InlineConfirm("Run", "Confirm run?")
    qtbot.addWidget(confirm)
    confirmeds: list[int] = []
    confirm.confirmed.connect(lambda: confirmeds.append(1))

    QTest.mouseClick(confirm, Qt.MouseButton.LeftButton)

    assert confirm.is_armed() is True
    assert confirm.text() == "Confirm run?"
    assert confirmeds == []


def test_inline_confirm_second_click_runs_and_disarms(qtbot, app):
    confirm = InlineConfirm("Run", "Confirm run?")
    qtbot.addWidget(confirm)
    confirmeds: list[int] = []
    confirm.confirmed.connect(lambda: confirmeds.append(1))

    QTest.mouseClick(confirm, Qt.MouseButton.LeftButton)
    QTest.mouseClick(confirm, Qt.MouseButton.LeftButton)

    assert confirmeds == [1]
    assert confirm.is_armed() is False
    assert confirm.text() == "Run"


def test_inline_confirm_armed_state_expires(qtbot, app):
    confirm = InlineConfirm("Run", "Confirm run?", confirm_timeout_ms=1)
    qtbot.addWidget(confirm)
    confirmeds: list[int] = []
    confirm.confirmed.connect(lambda: confirmeds.append(1))
    confirm.arm_for_test()
    assert confirm.is_armed() is True

    qtbot.wait(50)

    assert confirm.is_armed() is False
    assert confirm.text() == "Run"
    QTest.mouseClick(confirm, Qt.MouseButton.LeftButton)
    assert confirmeds == []  # the expired click armed the button but did not run


def test_inline_confirm_set_running_disables_and_restores(qtbot, app):
    confirm = InlineConfirm("Run", "Confirm run?")
    qtbot.addWidget(confirm)
    confirm.arm_for_test()

    confirm.set_running(True, "Running…")

    assert confirm.isEnabled() is False
    assert confirm.text() == "Running…"

    confirm.set_running(False, "Running…")

    assert confirm.isEnabled() is True
    assert confirm.text() == "Run"


def test_inline_confirm_reset_drops_armed_state(qtbot, app):
    confirm = InlineConfirm("Run", "Confirm run?")
    qtbot.addWidget(confirm)
    confirm.arm_for_test()
    confirm.reset()
    assert confirm.is_armed() is False
    assert confirm.text() == "Run"


# --- Status footer -----------------------------------------------------------------
def test_status_footer_switches_ready_running_attention(qtbot, app):
    footer = StatusFooter()
    qtbot.addWidget(footer)
    assert footer.state == READY

    footer.set_state(RUNNING)
    assert footer.state == RUNNING
    assert footer.text == RUNNING

    footer.set_state(NEEDS_ATTENTION)
    assert footer.state == NEEDS_ATTENTION


def test_status_footer_unknown_state_falls_back_to_ready(qtbot, app):
    footer = StatusFooter()
    qtbot.addWidget(footer)
    footer.set_state("nonsense")
    assert footer.state == READY


# --- Cards, chips, empty state ------------------------------------------------------
def test_card_action_click_emits_action_requested(qtbot, app):
    card = Card("Title", "Body", "Press me")
    qtbot.addWidget(card)
    received: list[bool] = []
    card.action_requested.connect(lambda: received.append(True))

    QTest.mouseClick(card.action_button, Qt.MouseButton.LeftButton)

    assert received == [True]


def test_chip_has_kind_property(qtbot, app):
    chip = Chip("Failed", kind="fail")
    qtbot.addWidget(chip)
    assert chip.property("chipKind") == "fail"


def test_empty_state_shows_heading_body_and_optional_action(qtbot, app):
    empty = EmptyState("Nothing yet", "Try something.", action_label="Go", on_action=lambda: None)
    qtbot.addWidget(empty)
    empty.show()
    qtbot.wait(10)
    assert empty.heading_label.text() == "Nothing yet"
    assert empty.action_button.isVisible()


# --- Page header ---------------------------------------------------------------------
def test_page_header_primary_relays_action(qtbot, app):
    header = PageHeader("Title", "Description", primary_label="Do it")
    qtbot.addWidget(header)
    received: list[bool] = []
    header.action_requested.connect(lambda: received.append(True))

    QTest.mouseClick(header.primary_button, Qt.MouseButton.LeftButton)

    assert received == [True]


def test_page_header_read_only_has_no_primary(qtbot, app):
    header = PageHeader("Title", "Description")
    qtbot.addWidget(header)
    assert header.primary_button is None


# --- Formatting and icons ------------------------------------------------------------
def test_status_display_maps_known_and_unknown_statuses() -> None:
    assert status_display("SUCCEEDED") == ("Succeeded", "ok")
    assert status_display("FAILED") == ("Failed", "fail")
    assert status_display("CANCELLED") == ("Cancelled", "neutral")
    assert status_display("WHATEVER") == ("WHATEVER", "neutral")


def test_human_timestamp_today_and_older() -> None:
    now = datetime(2026, 10, 29, 10, 0, 0)
    today = datetime(2026, 10, 29, 8, 5, 0)
    older = datetime(2025, 1, 2, 8, 30, 0)
    assert human_timestamp(today, now=now) == "today at 08:05"
    assert "2025" in human_timestamp(older, now=now)
    assert human_timestamp(None, now=now) == ""


def test_icon_pixmap_renders_every_glyph(qtbot, app):
    for draw in (
        draw_home_glyph,
        draw_automations_glyph,
        draw_activity_glyph,
        draw_settings_glyph,
        draw_info_circle,
        draw_check_circle,
        draw_alert_circle,
    ):
        pixmap = icon_pixmap(draw, 20)
        assert isinstance(pixmap, QPixmap)
        assert not pixmap.isNull()


# --- Contrast and strings -------------------------------------------------------------
def test_contrast_pairs_meet_accessibility_minimum() -> None:
    for name, foreground, background in CONTRAST_PAIRS:
        ratio = contrast_ratio(foreground, background)
        assert ratio >= 4.5, f"{name} is only {ratio:.2f}:1"


def test_strings_are_non_empty(qtbot, app) -> None:
    import ui.strings as strings

    for variable in dir(strings):
        value = getattr(strings, variable)
        if variable.isupper() and isinstance(value, str):
            assert value.strip(), f"{variable} contains no user-visible text"
