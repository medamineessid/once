"""Reduced motion test: verify animations are suppressed when
Windows animation preference is off."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QListWidgetItem, QWidget

from ui.motion import fade_dialog, fade_item, fade_slide, pulse, reveal_lines
from ui.styles import DIALOG_SCALE, DURATION_DIALOG_MS


def test_fade_slide_respects_reduced_motion(qtbot):
    """fade_slide returns instantly when animations_enabled() is False."""
    widget = qtbot.addWidget(QWidget())
    with patch("ui.motion.animations_enabled", return_value=False):
        fade_slide(widget)


def test_fade_item_respects_reduced_motion(qtbot):
    """fade_item returns instantly when animations_enabled() is False."""
    widget = qtbot.addWidget(QListWidget())
    item = QListWidgetItem(widget)
    with patch("ui.motion.animations_enabled", return_value=False):
        fade_item(item, index=0)


def test_fade_dialog_respects_reduced_motion(qtbot):
    """fade_dialog returns instantly when animations_enabled() is False."""
    dialog = qtbot.addWidget(QDialog())
    with patch("ui.motion.animations_enabled", return_value=False):
        fade_dialog(dialog)


def test_reveal_lines_respects_reduced_motion(qtbot):
    """reveal_lines touches nothing when animations_enabled() is False."""
    labels = [QLabel("line"), QLabel("line")]
    for label in labels:
        qtbot.addWidget(label)
    positions = [label.pos() for label in labels]
    with patch("ui.motion.animations_enabled", return_value=False):
        reveal_lines(labels)
    assert [label.pos() for label in labels] == positions
    assert all(label.graphicsEffect() is None for label in labels)


def test_dialog_motion_values_are_real() -> None:
    """The dialog animation must actually scale (0.98) over 220 ms."""
    assert DIALOG_SCALE == 0.98
    assert DURATION_DIALOG_MS == 220


def test_pulse_returns_none_when_reduced_motion():
    """pulse returns None (no animation) when animations_enabled() is False."""
    widget = QWidget()
    with patch("ui.motion.animations_enabled", return_value=False):
        result = pulse(widget)
    assert result is None, "pulse should return None when animations disabled"
