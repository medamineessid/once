"""Confirmation dialog for destructive delete actions.

Delete actions are always confirmed with a dialog that names what will be
removed. The button set is exactly Cancel and Delete, and a run count adds one
pre-checked "also delete its runs" choice so the default removes both.

The dialog is built on `ui.components.dialog`, not on `QMessageBox`: the stock
message box painted its buttons with the platform style, so Delete came out
white on near-white and Cancel was barely visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import override

from PySide6.QtWidgets import QCheckBox, QWidget

from ui.components.dialog import ConfirmDialog
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


def clear_drafts_message(count: int) -> str:
    """Name how many unnamed drafts a clear action removes."""
    draft_word = "draft" if count == 1 else "drafts"
    return f"Delete {count} unnamed {draft_word}? This cannot be undone."


def automation_delete_message(name: str, run_count: int) -> str:
    """Name the automation and, when present, how many runs go with it."""
    if run_count <= 0:
        return f"Delete '{name}'? This cannot be undone."
    return f"Delete '{name}' and its {run_count} {_run_noun(run_count)}? This cannot be undone."


class DeleteConfirmDialog(ConfirmDialog):
    """Modal confirmation with Cancel and a filled Delete, plus optional runs."""

    def __init__(
        self,
        message: str,
        *,
        runs_count: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            DELETE_CONFIRM_TITLE,
            message,
            action_label=DELETE_ACTION,
            cancel_label=DELETE_CANCEL,
            filled_danger=True,
            parent=parent,
        )
        self._runs_check: QCheckBox | None = None
        if runs_count > 0:
            self._runs_check = self.add_checkbox(
                f"Also delete its {runs_count} {_run_noun(runs_count)}",
                checked=True,
            )
        # Cancel is the default so a stray Enter never deletes anything.
        self.cancel_button.setFocus()

    @property
    def runs_checkbox(self) -> QCheckBox | None:
        """The optional runs checkbox, or None when there is no run history."""
        return self._runs_check

    def choice(self) -> DeleteChoice:
        """Return the current answer without running the dialog."""
        confirmed = self.result() == int(ConfirmDialog.DialogCode.Accepted)
        return DeleteChoice(
            confirmed,
            confirmed and self._runs_check is not None and self._runs_check.isChecked(),
        )

    @override
    def ask(self) -> DeleteChoice:
        """Show the dialog and return the user's answer."""
        self.exec()
        return self.choice()
