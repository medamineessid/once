"""Create Automation screen — describe a task and prepare a workflow."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components.banner import Banner
from ui.strings import (
    CREATE_BUTTON,
    CREATE_HINT,
    CREATE_NOT_AVAILABLE_BODY,
    CREATE_NOT_AVAILABLE_TITLE,
    CREATE_PLACEHOLDER,
    CREATE_QUESTION,
    CREATE_TITLE,
)
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL


class CreateAutomationPage(QWidget):
    """Beginner-friendly screen for describing a task to automate."""

    task_entered = Signal(str)
    editor_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._banner: Banner | None = None
        self._description_input: QTextEdit | None = None
        self._create_button: QPushButton | None = None
        self._scratch_button: QPushButton | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop)
        self._title_label = QLabel(CREATE_TITLE, self)
        self._title_label.setObjectName("pageTitle")
        layout.addWidget(self._title_label)
        self._banner = Banner(self)
        layout.addWidget(self._banner)
        self._question_label = QLabel(CREATE_QUESTION, self)
        self._question_label.setObjectName("questionLabel")
        layout.addWidget(self._question_label)
        layout.addSpacing(SPACING_MD)
        self._description_input = QTextEdit(self)
        self._description_input.setObjectName("descriptionInput")
        self._description_input.setPlaceholderText(CREATE_PLACEHOLDER)
        self._description_input.setMinimumHeight(120)
        self._description_input.setMaximumHeight(220)
        self._description_input.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        layout.addWidget(self._description_input)
        layout.addSpacing(SPACING_SM)
        self._hint_label = QLabel(CREATE_HINT, self)
        self._hint_label.setObjectName("hintLabel")
        layout.addWidget(self._hint_label)
        layout.addSpacing(SPACING_MD)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(SPACING_SM)
        self._create_button = QPushButton(CREATE_BUTTON, self)
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
        layout.addWidget(actions_container)
        self._scratch_button = QPushButton("Create from scratch", self)
        self._scratch_button.setObjectName("secondaryActionButton")
        self._scratch_button.clicked.connect(self.editor_requested.emit)
        layout.addWidget(self._scratch_button)

    def show_not_available(self, task_text: str) -> None:
        """Answer a typed description honestly on the page banner."""
        quote = task_text.strip()[:200]
        if self._banner is None:
            return
        self._banner.show_message(
            "info",
            CREATE_NOT_AVAILABLE_TITLE,
            f'"{quote}" — {CREATE_NOT_AVAILABLE_BODY}',
        )

    def _create_from_description(self) -> None:
        text = self._description_input.toPlainText().strip() if self._description_input else ""
        if text:
            self.task_entered.emit(text)

    def clear(self) -> None:
        if self._description_input:
            self._description_input.clear()
