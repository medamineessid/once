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
    CREATE_RECORD_BODY,
    CREATE_RECORD_START,
    CREATE_RECORD_STOP,
    CREATE_RECORD_TITLE,
    CREATE_TITLE,
    RECORDING_BACK,
    RECORDING_PAGE_TITLE,
)
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL


class CreateAutomationPage(QWidget):
    """Beginner-friendly screen for describing a task to automate."""

    task_entered = Signal(str)
    editor_requested = Signal()
    record_requested = Signal()
    stop_record_requested = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._banner: Banner | None = None
        self._description_input: QTextEdit | None = None
        self._create_button: QPushButton | None = None
        self._scratch_button: QPushButton | None = None
        self._record_button: QPushButton | None = None
        self._stop_record_button: QPushButton | None = None
        self._back_button: QPushButton | None = None
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
        self._scratch_button.clicked.connect(self._open_scratch_editor)
        layout.addWidget(self._scratch_button)
        self._record_card = QFrame(self)
        self._record_card.setObjectName("recordCard")
        record_layout = QVBoxLayout(self._record_card)
        record_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        record_title = QLabel(CREATE_RECORD_TITLE, self._record_card)
        record_title.setObjectName("cardTitle")
        record_body = QLabel(CREATE_RECORD_BODY, self._record_card)
        record_body.setObjectName("cardBody")
        record_body.setWordWrap(True)
        record_layout.addWidget(record_title)
        record_layout.addWidget(record_body)
        record_actions = QHBoxLayout()
        self._record_button = QPushButton(CREATE_RECORD_START, self._record_card)
        self._record_button.setObjectName("primaryActionButton")
        self._record_button.clicked.connect(self.record_requested.emit)
        self._stop_record_button = QPushButton(CREATE_RECORD_STOP, self._record_card)
        self._stop_record_button.setObjectName("secondaryActionButton")
        self._stop_record_button.clicked.connect(self.stop_record_requested.emit)
        self._stop_record_button.hide()
        record_actions.addWidget(self._record_button)
        record_actions.addWidget(self._stop_record_button)
        record_layout.addLayout(record_actions)
        layout.addWidget(self._record_card)
        self._back_button = QPushButton(RECORDING_BACK, self)
        self._back_button.setObjectName("secondaryActionButton")
        self._back_button.clicked.connect(self.cancelled.emit)
        layout.addWidget(self._back_button)

    def show_recording_mode(self) -> None:
        """Show the dedicated recording route, not the typed-description form."""
        self._title_label.setText(RECORDING_PAGE_TITLE)
        self._question_label.hide()
        self._description_input.hide()
        self._hint_label.hide()
        self._create_button.hide()
        self._scratch_button.hide()
        self._record_card.show()
        self._back_button.show()

    def show_creation_mode(self) -> None:
        """Restore the description page for callers that still use it."""
        self._title_label.setText(CREATE_TITLE)
        self._question_label.show()
        self._description_input.show()
        self._hint_label.show()
        self._create_button.show()
        self._scratch_button.show()
        self._record_card.show()
        self._back_button.show()

    def set_recording_state(self, active: bool, message: str | None = None) -> None:
        """Reflect the real recorder lifecycle without implying draft execution."""
        if self._record_button is not None:
            self._record_button.setEnabled(not active)
        if self._stop_record_button is not None:
            self._stop_record_button.setVisible(active)
        if message and self._banner is not None:
            self._banner.show_message("info" if active else "success", CREATE_RECORD_TITLE, message)

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

    def _open_scratch_editor(self) -> None:
        if self._banner is not None:
            self._banner.clear()
        self.editor_requested.emit()

    def clear(self) -> None:
        if self._description_input:
            self._description_input.clear()
