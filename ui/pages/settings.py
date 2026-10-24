"""Settings page — application configuration and advanced tools."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService


class SettingsPage(QWidget):
    """Clean settings for ordinary users with advanced tools underneath."""

    verifier_configured = Signal()
    recording_started = Signal()
    recording_stopped = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._init_ui()

    def _init_ui(self) -> None:
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
        self._recording_list = QListWidget(self._recordings_group)
        self._recording_list.setObjectName("recordingList")
        self._recording_list.setAlternatingRowColors(True)
        self._recording_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        recordings_layout.addWidget(self._recording_list)
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
        self._advanced_group = QGroupBox("Advanced", self)
        self._advanced_group.setObjectName("settingsGroup")
        advanced_layout = QVBoxLayout(self._advanced_group)
        advanced_layout.setContentsMargins(12, 12, 12, 12)
        advanced_layout.setSpacing(8)
        self._advanced_intro_label = QLabel(
            "These tools are for verifier configuration, workflow editing, "
            "agent proposals, and diagnostics. They do not change the safety "
            "rules that govern Once.",
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
        page_layout.addWidget(scroll_area, stretch=1)
        page_layout.setStretchFactor(scroll_area, 1)

    def _choose_authorized_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose authorized folder")
        if not directory:
            return
        self._authorized_label.setText(f"Authorized folder: {directory}")

    def _start_recording(self) -> None:
        self.recording_started.emit()

    def _stop_recording(self) -> None:
        self.recording_stopped.emit()

    def _delete_recording(self) -> None:
        item = self._recording_list.currentItem()
        if item is None:
            return
        QMessageBox.warning(
            self,
            "Delete recording",
            f"Delete '{item.text()}'? This cannot be undone.",
        )

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
