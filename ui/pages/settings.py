"""Settings page — application configuration and advanced tools."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService


def _build_section(
    title: str,
    controls: tuple[tuple[QWidget, callable] | tuple[QWidget], ...],
    parent: QWidget | None = None,
) -> QGroupBox:
    """Build a compact settings section with a title and one or more controls."""
    group = QGroupBox(title, parent)
    group.setObjectName("settingsGroup")
    layout = QVBoxLayout(group)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)
    for item in controls:
        widget = item[0]
        callback = item[1] if len(item) > 1 else None
        if callback is not None:
            if isinstance(widget, QPushButton):
                widget.clicked.connect(callback)
            else:
                raise TypeError(f"unsupported callback target {type(widget)}")
        layout.addWidget(widget)
    return group


class SettingsPage(QWidget):
    verifier_configured = Signal()
    recording_started = Signal()
    recording_stopped = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._init_ui()

    def _set_status(self, message: str) -> None:
        """Show a plain-language status message without blocking the UI."""
        self._status_label.setText(message)
        self._status_label.show()

    def _init_ui(self) -> None:
        self._status_label = QLabel("", self)
        self._status_label.setObjectName("settingsStatus")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            "font-size: 13px; color: #2563EB; padding: 2px 24px 0 24px;"
        )
        self._status_label.hide()
        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("settingsScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_widget = QWidget(self)
        scroll_widget.setObjectName("settingsWidget")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(24, 24, 24, 24)
        scroll_layout.setSpacing(16)
        scroll_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("Settings", self)
        self._title_label.setObjectName("pageTitle")
        self._title_label.setStyleSheet("font-size: 26px; font-weight: 600; color: #1d1d1d;")
        scroll_layout.addWidget(self._title_label)
        self._subtitle_label = QLabel(
            "Configure how Once works for you.",
            self,
        )
        self._subtitle_label.setObjectName("pageSubtitle")
        self._subtitle_label.setStyleSheet("font-size: 15px; color: #525252; margin-top: 2px;")
        scroll_layout.addWidget(self._subtitle_label)
        scroll_layout.addSpacing(12)
        self._authorized_group = QGroupBox("Authorized folders", self)
        self._authorized_group.setObjectName("settingsGroup")
        authorized_layout = QVBoxLayout(self._authorized_group)
        authorized_layout.setContentsMargins(12, 12, 12, 12)
        authorized_layout.setSpacing(8)
        self._authorized_label = QLabel("No folder selected.", self._authorized_group)
        self._authorized_label.setWordWrap(True)
        self._authorized_label.setStyleSheet("font-size: 13px; color: #525252;")
        authorized_layout.addWidget(self._authorized_label)
        self._choose_authorized_button = QPushButton("Choose folder", self._authorized_group)
        self._choose_authorized_button.setObjectName("secondaryActionButton")
        self._choose_authorized_button.setMinimumHeight(36)
        self._choose_authorized_button.clicked.connect(self._choose_authorized_folder)
        authorized_layout.addWidget(self._choose_authorized_button)
        scroll_layout.addWidget(self._authorized_group)
        self._recordings_group = QGroupBox("Recording", self)
        self._recordings_group.setObjectName("settingsGroup")
        recordings_layout = QVBoxLayout(self._recordings_group)
        recordings_layout.setContentsMargins(12, 12, 12, 12)
        recordings_layout.setSpacing(8)
        recordings_actions_row = QHBoxLayout()
        recordings_actions_row.setSpacing(10)
        self._start_recording_button = QPushButton("Start recording", self._recordings_group)
        self._start_recording_button.setObjectName("primaryActionButton")
        self._start_recording_button.setMinimumHeight(34)
        self._start_recording_button.clicked.connect(self._start_recording)
        self._stop_recording_button = QPushButton("Stop recording", self._recordings_group)
        self._stop_recording_button.setObjectName("secondaryActionButton")
        self._stop_recording_button.setMinimumHeight(34)
        self._stop_recording_button.clicked.connect(self._stop_recording)
        self._delete_recording_button = QPushButton("Delete selected", self._recordings_group)
        self._delete_recording_button.setObjectName("dangerButton")
        self._delete_recording_button.setMinimumHeight(34)
        self._delete_recording_button.clicked.connect(self._delete_recording)

        recordings_actions_row.addWidget(self._start_recording_button)
        recordings_actions_row.addWidget(self._stop_recording_button)
        recordings_actions_row.addWidget(self._delete_recording_button)
        recordings_layout.addLayout(recordings_actions_row)
        scroll_layout.addWidget(self._recordings_group)
        self._gemini_group = QGroupBox("Gemini integration", self)
        self._gemini_group.setObjectName("settingsGroup")
        gemini_layout = QVBoxLayout(self._gemini_group)
        gemini_layout.setContentsMargins(12, 12, 12, 12)
        gemini_layout.setSpacing(8)
        self._connect_gemini_button = QPushButton("Connect Gemini", self._gemini_group)
        self._connect_gemini_button.clicked.connect(self._connect_gemini)
        gemini_layout.addWidget(self._connect_gemini_button)
        self._disconnect_gemini_button = QPushButton("Disconnect Gemini", self._gemini_group)
        self._disconnect_gemini_button.clicked.connect(self._disconnect_gemini)
        gemini_layout.addWidget(self._disconnect_gemini_button)
        self._gemini_intro_label = QLabel(
            "Gemini helps with invoice understanding when enabled.",
            self._gemini_group,
        )
        self._gemini_intro_label.setStyleSheet("font-size: 13px; color: #525252;")
        gemini_layout.addWidget(self._gemini_intro_label)
        scroll_layout.addWidget(self._gemini_group)
        self._coding_agent_group = QGroupBox("Coding agent", self)
        self._coding_agent_group.setObjectName("settingsGroup")
        coding_layout = QVBoxLayout(self._coding_agent_group)
        coding_layout.setContentsMargins(12, 12, 12, 12)
        coding_layout.setSpacing(8)
        self._open_proposals_button = QPushButton("Open proposals", self._coding_agent_group)
        self._open_proposals_button.clicked.connect(self._open_coding_agent_proposals)
        coding_layout.addWidget(self._open_proposals_button)
        self._start_review_button = QPushButton("Start review", self._coding_agent_group)
        self._start_review_button.clicked.connect(self._open_coding_agent_review)
        coding_layout.addWidget(self._start_review_button)
        self._coding_agent_intro_label = QLabel(
            "Review proposed changes before anything is applied.",
            self._coding_agent_group,
        )
        self._coding_agent_intro_label.setStyleSheet("font-size: 13px; color: #525252;")
        coding_layout.addWidget(self._coding_agent_intro_label)
        scroll_layout.addWidget(self._coding_agent_group)
        self._advanced_group = QGroupBox("Advanced", self)
        self._advanced_group.setObjectName("settingsGroup")
        advanced_layout = QVBoxLayout(self._advanced_group)
        advanced_layout.setContentsMargins(12, 12, 12, 12)
        advanced_layout.setSpacing(8)
        self._advanced_intro_label = QLabel(
            "These tools are for verifier configuration, workflow editing,"
            " agent proposals, and diagnostics. They do not change the safety"
            " rules that govern Once.",
            self._advanced_group,
        )
        self._advanced_intro_label.setWordWrap(True)
        self._advanced_intro_label.setStyleSheet("font-size: 13px; color: #525252;")
        advanced_layout.addWidget(self._advanced_intro_label)
        scroll_layout.addWidget(self._advanced_group)
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        page_layout.addWidget(self._status_label)
        page_layout.addWidget(scroll_area, stretch=1)
        page_layout.setStretchFactor(scroll_area, 1)

    def _choose_authorized_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose authorized folder")
        if not directory:
            return
        self._authorized_label.setText(f"Authorized folder: {directory}")

    def _connect_gemini(self) -> None:
        self._set_status(
            "Connect Gemini when you want invoice understanding on this"
            " machine. The connection is verified before any data leaves"
            " the machine."
        )

    def _disconnect_gemini(self) -> None:
        self._set_status(
            "Disconnect Gemini when you no longer want invoice understanding on this machine."
        )

    def _open_coding_agent_proposals(self) -> None:
        self._set_status(
            "There are no recorded proposals yet. Propose a fix from a run"
            " or verification result when that capability is enabled."
        )

    def _open_coding_agent_review(self) -> None:
        self._set_status(
            "No proposal is ready for review. The review screen opens when a"
            " proposal has been recorded."
        )

    def _start_recording(self) -> None:
        self.recording_started.emit()

    def _stop_recording(self) -> None:
        self.recording_stopped.emit()

    def _delete_recording(self) -> None:
        # Recordings are listed on the recorder screen; this page has none yet.
        self._set_status(
            "No recording is selected here. Select a recording on the recorder screen to delete it."
        )

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
