"""One tokenised dialog component for every confirmation and message.

Qt's stock message boxes paint their buttons with the platform style, so on the
navy-and-lemon shell the destructive button came out white on near-white. Every
dialog in the app therefore uses this component instead: the app's own
typography, a filled danger action with readable white text, an outlined navy
cancel, and a visible focus state on both.

The component holds no policy: it shows text and returns what the user chose.
"""

from __future__ import annotations

from typing import override

from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.components.buttons import ActionButton
from ui.motion import fade_dialog
from ui.styles import SPACING_LG, SPACING_SM, SPACING_XL, apply_theme

#: Object name of the filled-destructive style in ui/styles.
FILLED_DANGER = "dangerFilledButton"


class TokenDialog(QDialog):
    """A modal dialog drawn with the app's tokens rather than the platform style."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("tokenDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(440)
        apply_theme(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        layout.setSpacing(SPACING_SM)

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName("dialogTitle")
        self._title_label.setWordWrap(True)
        self._message_label = QLabel(message, self)
        self._message_label.setObjectName("dialogMessage")
        self._message_label.setWordWrap(True)
        layout.addWidget(self._title_label)
        layout.addWidget(self._message_label)

        self._extra = QVBoxLayout()
        self._extra.setSpacing(SPACING_SM)
        layout.addLayout(self._extra)
        layout.addStretch(1)

        self._button_row = QHBoxLayout()
        self._button_row.setSpacing(SPACING_SM)
        self._button_row.addStretch(1)
        layout.addLayout(self._button_row)
        self._action_buttons: list[ActionButton] = []

    # ------------------------------------------------------------- building
    def add_checkbox(self, label: str, *, checked: bool) -> QCheckBox:
        """Add one optional choice under the message."""
        box = QCheckBox(label, self)
        box.setObjectName("dialogCheckbox")
        box.setChecked(checked)
        self._extra.addWidget(box)
        return box

    def add_button(
        self,
        text: str,
        *,
        variant: str = "secondary",
        filled_danger: bool = False,
        primary: bool = False,
    ) -> ActionButton:
        """Add one action button to the right-hand row."""
        button = ActionButton(text, variant=variant, parent=self)
        if filled_danger:
            # A filled danger action: the outlined variant is unreadable as the
            # main choice in a dialog, which is the defect this replaces.
            button.setObjectName(FILLED_DANGER)
        button.setMinimumHeight(40)
        self._button_row.addWidget(button)
        self._action_buttons.append(button)
        if primary:
            self._primary = button
        return button

    # -------------------------------------------------------------- reading
    def text(self) -> str:
        """The message shown to the user."""
        return self._message_label.text()

    def buttons(self) -> tuple[ActionButton, ...]:
        """Every action button, in the order it was added."""
        return tuple(self._action_buttons)

    @override
    def showEvent(self, event) -> None:
        """Fade the dialog in when it appears, unless motion is off."""
        super().showEvent(event)
        fade_dialog(self)


class ConfirmDialog(TokenDialog):
    """A dialog with exactly two answers: the action, or cancel."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        action_label: str,
        cancel_label: str = "Cancel",
        filled_danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, message, parent=parent)
        self._cancel_button = self.add_button(cancel_label, variant="secondary")
        self._action_button = self.add_button(
            action_label, variant="destructive", filled_danger=filled_danger
        )
        self._cancel_button.setAutoDefault(False)
        self._action_button.setAutoDefault(False)
        self._cancel_button.setDefault(True)
        self._cancel_button.clicked.connect(self.reject)
        self._action_button.clicked.connect(self.accept)

    @property
    def cancel_button(self) -> ActionButton:
        """The outlined cancel button."""
        return self._cancel_button

    @property
    def action_button(self) -> ActionButton:
        """The button that confirms the action."""
        return self._action_button

    def ask(self) -> bool:
        """Show the dialog and report whether the action was chosen."""
        self.exec()
        return self.result() == int(QDialog.DialogCode.Accepted)
