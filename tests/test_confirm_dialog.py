"""The tokenised dialog: readable destructive action, outlined cancel, focus.

The delete confirmation used to be a stock `QMessageBox`, whose buttons were
painted by the platform style and came out white on near-white. These checks
pin the replacement: a filled danger action, an outlined navy cancel, a visible
focus state on both, and a default answer that deletes nothing.
"""

from __future__ import annotations

from pathlib import Path

from ui.components.delete_confirm import DeleteConfirmDialog, automation_delete_message
from ui.components.dialog import FILLED_DANGER


def _stylesheet() -> str:
    source = Path(__file__).resolve().parents[1] / "ui" / "styles" / "__init__.py"
    return source.read_text(encoding="utf-8")


def test_delete_dialog_uses_a_filled_danger_action_and_outlined_cancel(qtbot):
    dialog = DeleteConfirmDialog(automation_delete_message("Weekly backup", 2), runs_count=2)
    qtbot.addWidget(dialog)

    assert dialog.action_button.text() == "Delete"
    assert dialog.action_button.objectName() == FILLED_DANGER
    assert dialog.cancel_button.text() == "Cancel"
    assert dialog.cancel_button.objectName() == "secondaryActionButton"
    assert dialog.text() == "Delete 'Weekly backup' and its 2 runs? This cannot be undone."


def test_both_dialog_buttons_can_take_focus_and_cancel_is_the_default(qtbot):
    dialog = DeleteConfirmDialog(automation_delete_message("Weekly backup", 0))
    qtbot.addWidget(dialog)

    for button in dialog.buttons():
        assert button.focusPolicy().value != 0, f"{button.text()} cannot take focus"
    assert dialog.cancel_button.isDefault() is True
    assert dialog.action_button.isDefault() is False


def test_the_runs_choice_starts_checked_and_disappears_without_history(qtbot):
    with_runs = DeleteConfirmDialog(automation_delete_message("Tidy desktop", 3), runs_count=3)
    qtbot.addWidget(with_runs)
    assert with_runs.runs_checkbox is not None
    assert with_runs.runs_checkbox.isChecked() is True

    without_runs = DeleteConfirmDialog(automation_delete_message("Tidy desktop", 0))
    qtbot.addWidget(without_runs)
    assert without_runs.runs_checkbox is None


def test_rejecting_the_dialog_confirms_nothing(qtbot):
    dialog = DeleteConfirmDialog(automation_delete_message("Print labels", 1), runs_count=1)
    qtbot.addWidget(dialog)
    dialog.reject()
    choice = dialog.choice()
    assert choice.confirmed is False
    assert choice.delete_runs is False


def test_the_filled_danger_style_is_readable_and_has_a_focus_state():
    sheet = _stylesheet()
    start = sheet.index("QPushButton#dangerFilledButton {")
    block = sheet[start : sheet.index("}", start)]
    assert "background: $STATUS_ERROR" in block
    assert "color: $WHITE" in block
    focused = sheet[sheet.index("QPushButton#primaryActionButton:focus,") :]
    assert "QPushButton#dangerFilledButton:focus" in focused[:400]
    dialog_start = sheet.index("QDialog#tokenDialog {")
    dialog_block = sheet[dialog_start : sheet.index("}", dialog_start)]
    assert "background: $SURFACE" in dialog_block
