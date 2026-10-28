"""Create Automation screen — describe a task and prepare a workflow."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL


class CreateAutomationPage(QWidget):
    """Beginner-friendly screen for describing a task to automate."""

    task_entered = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._description_input: QTextEdit | None = None
        self._create_button: QPushButton | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("Create automation", self)
        self._title_label.setObjectName("pageTitle")
        layout.addWidget(self._title_label, alignment=Qt.AlignHCenter)
        layout.addSpacing(4)
        self._question_label = QLabel("What would you like Once to do?", self)
        self._question_label.setObjectName("questionLabel")
        layout.addWidget(self._question_label, alignment=Qt.AlignHCenter)
        layout.addSpacing(SPACING_MD)
        self._description_input = QTextEdit(self)
        self._description_input.setObjectName("descriptionInput")
        self._description_input.setPlaceholderText(
            "Example: Open my invoices folder and identify PDF files."
        )
        self._description_input.setMinimumHeight(120)
        self._description_input.setMaximumHeight(220)
        from PySide6.QtGui import QTextOption

        self._description_input.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        layout.addWidget(self._description_input, alignment=Qt.AlignHCenter)
        layout.addSpacing(SPACING_SM)
        self._hint_label = QLabel(
            "Once will prepare a plan for your review before any action is executed.",
            self,
        )
        self._hint_label.setObjectName("hintLabel")
        layout.addWidget(self._hint_label, alignment=Qt.AlignHCenter)
        layout.addSpacing(SPACING_MD)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(SPACING_SM)
        self._create_button = QPushButton("Create automation", self)
        self._create_button.setObjectName("primaryActionButton")
        self._create_button.setMinimumHeight(42)
        self._create_button.setDefault(True)
        self._create_button.clicked.connect(self._create_from_description)
        actions_row.addWidget(self._create_button)
        actions_container = QFrame(self)
        actions_container.setObjectName("actionsContainer")
        actions_container_layout = QVBoxLayout(actions_container)
        actions_container_layout.setContentsMargins(0, 0, 0, 0)
        actions_container_layout.setSpacing(SPACING_SM)
        actions_container_layout.addLayout(actions_row)
        layout.addWidget(actions_container, alignment=Qt.AlignHCenter)

    def _create_from_description(self) -> None:
        text = self._description_input.toPlainText().strip() if self._description_input else ""
        if text:
            self.task_entered.emit(text)

    def clear(self) -> None:
        if self._description_input:
            self._description_input.clear()
