"""Confirmation dialog for destructive delete actions.

Delete actions are always confirmed with a dialog that names what will be
removed. The button set is exactly Cancel and Delete, and a run count adds one
pre-checked "also delete its runs" choice so the default removes both.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QMessageBox, QWidget

from ui.motion import fade_dialog
from ui.strings import DELETE_ACTION, DELETE_CANCEL, DELETE_CONFIRM_TITLE


@dataclass(frozen=True)
class DeleteChoice:
    """The user's answer to a delete confirmation."""

    confirmed: bool
    delete_runs: bool = False


def _run_noun(count: int) -> str:
    return "run" if count == 1 else "runs"


def run_delete_message(name: str) -> str:
    """Name one run's automation so the dialog cannot be ambiguous."""
    return f"Delete the run of '{name}'? This cannot be undone."


def clear_runs_message(count: int) -> str:
    """Name how many runs a clear-all action removes."""
    return f"Delete all {count} {_run_noun(count)}? This cannot be undone."


def automation_delete_message(name: str, run_count: int) -> str:
    """Name the automation and, when present, how many runs go with it."""
    if run_count <= 0:
        return f"Delete '{name}'? This cannot be undone."
    return f"Delete '{name}' and its {run_count} {_run_noun(run_count)}? This cannot be undone."


class DeleteConfirmDialog(QMessageBox):
    """Modal confirmation with Cancel and Delete, plus optional run deletion."""

    def __init__(
        self,
        message: str,
        *,
        runs_count: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(DELETE_CONFIRM_TITLE)
        self.setIcon(QMessageBox.Icon.Warning)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(message)
        self._cancel_button = self.addButton(DELETE_CANCEL, QMessageBox.ButtonRole.RejectRole)
        self._delete_button = self.addButton(DELETE_ACTION, QMessageBox.ButtonRole.DestructiveRole)
        self.setDefaultButton(self._cancel_button)
        self._runs_check: QCheckBox | None = None
        if runs_count > 0:
            self._runs_check = QCheckBox(f"Also delete its {runs_count} {_run_noun(runs_count)}")
            self._runs_check.setChecked(True)
            self.setCheckBox(self._runs_check)

    @override
    def showEvent(self, event) -> None:
        """Fade and scale the dialog in when it appears."""
        super().showEvent(event)
        fade_dialog(self)

    @property
    def runs_checkbox(self) -> QCheckBox | None:
        """The optional runs checkbox, or None when there is no run history."""
        return self._runs_check

    def choice(self) -> DeleteChoice:
        """Return the current answer without running the dialog."""
        confirmed = self.clickedButton() is self._delete_button
        return DeleteChoice(
            confirmed,
            confirmed and self._runs_check is not None and self._runs_check.isChecked(),
        )

    def ask(self) -> DeleteChoice:
        """Show the dialog and return the user's answer."""
        self.exec()
        return self.choice()
