"""Settings page — application configuration only.

Per the UX brief, unfinished features are hidden, not faked: Settings shows
the authorized-folder choice and the acceptance-checker configuration. The
recording group, the Gemini group, the coding-agent buttons, and the empty
Advanced group were removed because none of them had real behaviour behind
them. Recording lives in the create flow once that journey exists.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from controller.verifier_config import VerifierConfig
from ui.styles import SPACING_MD, SPACING_SM, SPACING_XL
from ui.verifier_dialog import VerifierConfigDialog


class SettingsPage(QWidget):
    """Authorized-folder and acceptance-checker configuration."""

    verifier_configured = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._app_data_dir: Path | None = None
        self._verifier_config: VerifierConfig | None = None
        self._init_ui()

    def configure(
        self,
        app_data_dir: Path | None,
        verifier_config: VerifierConfig | None = None,
    ) -> None:
        """Receive the data folder the verifier configuration is stored in."""
        self._app_data_dir = app_data_dir
        self._verifier_config = verifier_config

    def _init_ui(self) -> None:
        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("settingsScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_widget = QWidget(self)
        scroll_widget.setObjectName("settingsWidget")
        self._scroll_layout = QVBoxLayout(scroll_widget)
        self._scroll_layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        self._scroll_layout.setSpacing(SPACING_MD)
        self._scroll_layout.setAlignment(Qt.AlignTop)
        self._title_label = QLabel("Settings", self)
        self._title_label.setObjectName("pageTitle")
        self._scroll_layout.addWidget(self._title_label)
        self._subtitle_label = QLabel("Configure how Once works for you.", self)
        self._subtitle_label.setObjectName("pageSubtitle")
        self._scroll_layout.addWidget(self._subtitle_label)
        self._scroll_layout.addSpacing(SPACING_MD)

        self._authorized_group = QGroupBox("Authorized folders", self)
        self._authorized_group.setObjectName("settingsGroup")
        authorized_layout = QVBoxLayout(self._authorized_group)
        authorized_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        authorized_layout.setSpacing(SPACING_SM)
        self._authorized_label = QLabel("No folder selected.", self._authorized_group)
        self._authorized_label.setWordWrap(True)
        self._authorized_label.setObjectName("authorizedLabel")
        authorized_layout.addWidget(self._authorized_label)
        self._choose_authorized_button = QPushButton("Choose folder", self._authorized_group)
        self._choose_authorized_button.setObjectName("secondaryActionButton")
        self._choose_authorized_button.clicked.connect(self._choose_authorized_folder)
        authorized_layout.addWidget(self._choose_authorized_button)
        self._scroll_layout.addWidget(self._authorized_group)

        self._verifier_group = QGroupBox("Acceptance checker", self)
        self._verifier_group.setObjectName("settingsGroup")
        verifier_layout = QVBoxLayout(self._verifier_group)
        verifier_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        verifier_layout.setSpacing(SPACING_SM)
        self._verifier_label = QLabel(
            "The checker reruns acceptance cases against a proposed change before you approve it.",
            self._verifier_group,
        )
        self._verifier_label.setWordWrap(True)
        self._verifier_label.setObjectName("verifierIntroLabel")
        verifier_layout.addWidget(self._verifier_label)
        self._configure_verifier_button = QPushButton("Configure checker…", self._verifier_group)
        self._configure_verifier_button.setObjectName("secondaryActionButton")
        self._configure_verifier_button.clicked.connect(self._configure_verifier)
        verifier_layout.addWidget(self._configure_verifier_button)
        self._scroll_layout.addWidget(self._verifier_group)

        self._scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        page_layout.addWidget(scroll_area, stretch=1)

    def _choose_authorized_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose authorized folder")
        if not directory:
            return
        self._authorized_label.setText(f"Authorized folder: {directory}")

    def _configure_verifier(self) -> None:
        """Open the real acceptance-checker editor used by the old window."""
        if self._app_data_dir is None:
            QMessageBox.information(
                self,
                "Not available yet",
                "Once could not find its data folder on this machine, so the"
                " checker cannot be configured here yet.",
            )
            return
        dialog = VerifierConfigDialog(
            self._app_data_dir,
            current=self._verifier_config,
            parent=self,
        )
        dialog.exec()
        if dialog.saved is not None:
            self._verifier_config = dialog.saved
            self.verifier_configured.emit()

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
