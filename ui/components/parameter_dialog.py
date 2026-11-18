"""Ask one run-time value per placeholder before an automation starts."""

from __future__ import annotations

from typing import override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ui.motion import fade_dialog
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM


class ParameterDialog(QDialog):
    """One labelled text field per placeholder; nothing runs without an answer."""

    def __init__(self, names: tuple[str, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("parameterDialog")
        self.setWindowTitle("This automation needs a value")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_SM)

        intro = QLabel(
            "Fill in the value Once should use. It is used for this run only and is never saved.",
            self,
        )
        intro.setObjectName("dialogBody")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._fields: dict[str, QLineEdit] = {}
        for name in names:
            label = QLabel(name.replace("_", " ").capitalize(), self)
            label.setObjectName("fieldLabel")
            field = QLineEdit(self)
            field.setObjectName(f"parameterField_{name}")
            field.setPlaceholderText(f"Value for {name}")
            layout.addWidget(label)
            layout.addWidget(field)
            self._fields[name] = field

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addSpacing(SPACING_MD)
        layout.addWidget(buttons)
        fade_dialog(self)
        first = next(iter(self._fields.values()), None)
        if first is not None:
            first.setFocus(Qt.FocusReason.OtherFocusReason)

    @override
    def values(self) -> dict[str, str]:
        """The typed values, keyed by placeholder name."""
        return {name: field.text().strip() for name, field in self._fields.items()}

    def ask(self) -> dict[str, str] | None:
        """Show the dialog; None means the person cancelled the run."""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        values = self.values()
        if any(not value for value in values.values()) or any(
            "{" in value for value in values.values()
        ):
            return None
        return values
