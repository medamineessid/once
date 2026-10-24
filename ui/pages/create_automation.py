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
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("Create automation", self)
        self._title_label.setObjectName("pageTitle")
        self._title_label.setStyleSheet("font-size: 26px; font-weight: 600; color: #1d1d1d;")
        layout.addWidget(self._title_label, alignment=Qt.AlignHCenter)
        layout.addSpacing(4)
        self._question_label = QLabel("What would you like Once to do?", self)
        self._question_label.setObjectName("questionLabel")
        self._question_label.setStyleSheet("font-size: 18px; font-weight: 500; color: #3a3a3a;")
        layout.addWidget(self._question_label, alignment=Qt.AlignHCenter)
        layout.addSpacing(12)
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
        layout.addSpacing(8)
        self._hint_label = QLabel(
            "Once will prepare a plan for your review before any action is executed.",
            self,
        )
        self._hint_label.setObjectName("hintLabel")
        self._hint_label.setStyleSheet("font-size: 13px; color: #6b6b6b;")
        layout.addWidget(self._hint_label, alignment=Qt.AlignHCenter)
        layout.addSpacing(12)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)
        self._create_button = QPushButton("Create automation", self)
        self._create_button.setObjectName("primaryActionButton")
        self._create_button.setMinimumHeight(42)
        self._create_button.setDefault(True)
        self._create_button.clicked.connect(self._create_from_description)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("secondaryActionButton")
        self._cancel_button.setMinimumHeight(42)
        self._cancel_button.clicked.connect(self._cancel)
        actions_row.addWidget(self._create_button, stretch=3)
        actions_row.addWidget(self._cancel_button, stretch=1)
        actions_container = QFrame(self)
        actions_container.setObjectName("actionsContainer")
        actions_container_layout = QVBoxLayout(actions_container)
        actions_container_layout.setContentsMargins(0, 0, 0, 0)
        actions_container_layout.setSpacing(8)
        actions_container_layout.addLayout(actions_row)
        layout.addWidget(actions_container, alignment=Qt.AlignHCenter)

    def _create_from_description(self) -> None:
        text = self._description_input.text().strip() if self._description_input else ""
        if text:
            self.task_entered.emit(text)

    def _cancel(self) -> None:
        pass

    def clear(self) -> None:
        if self._description_input:
            self._description_input.clear()
