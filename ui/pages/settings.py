"""Settings page — application configuration only.

Per the UX brief, unfinished features are hidden, not faked: Settings shows
the authorized-folder choice and the acceptance-checker configuration,
edited inline (no blocking dialogs). Recording, Gemini, coding-agent, and
Advanced placeholders were removed because none of them had real behaviour
behind them.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from controller.verifier_config import VerifierConfig
from ui.components.banner import Banner
from ui.components.verifier_panel import VerifierEditorPanel
from ui.strings import (
    SETTINGS_CONFIG_SAVED_BODY,
    SETTINGS_CONFIG_SAVED_TITLE,
    SETTINGS_NO_DATA_DIR_BODY,
    SETTINGS_NO_DATA_DIR_TITLE,
    SETTINGS_SUBTITLE,
    SETTINGS_TITLE,
)
from ui.styles import SPACING_MD, SPACING_SM, SPACING_XL


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
        self._verifier_panel.reconfigure(app_data_dir, verifier_config)

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

        self._title_label = QLabel(SETTINGS_TITLE, self)
        self._title_label.setObjectName("pageTitle")
        self._scroll_layout.addWidget(self._title_label)
        self._subtitle_label = QLabel(SETTINGS_SUBTITLE, self)
        self._subtitle_label.setObjectName("pageSubtitle")
        self._scroll_layout.addWidget(self._subtitle_label)

        self._banner = Banner(self)
        self._scroll_layout.addWidget(self._banner)
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
        self._verifier_panel = VerifierEditorPanel(None, parent=self._verifier_group)
        self._verifier_panel.saved.connect(self._on_verifier_saved)
        verifier_layout.addWidget(self._verifier_panel)
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
        chosen = Path(directory)
        if self._service is not None:
            self._service.set_allowed_root(chosen)
        self._authorized_label.setText(f"Authorized folder: {chosen}")

    def _configure_verifier(self) -> None:
        """Show or hide the inline checker editor; explain a missing data folder."""
        if self._app_data_dir is None:
            self._banner.show_message(
                "warning", SETTINGS_NO_DATA_DIR_TITLE, SETTINGS_NO_DATA_DIR_BODY
            )
            return
        opening = not self._verifier_panel.isVisible()
        self._verifier_panel.setVisible(opening)
        if opening:
            self._verifier_panel.focus_first_field()

    def _on_verifier_saved(self, config: VerifierConfig) -> None:
        """Record the saved checker configuration and tell the shell."""
        self._verifier_config = config
        self._banner.show_message(
            "success", SETTINGS_CONFIG_SAVED_TITLE, SETTINGS_CONFIG_SAVED_BODY
        )
        self.verifier_configured.emit()
        self._verifier_panel.hide()

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        if service is not None and service.allowed_root is not None:
            self._authorized_label.setText(f"Authorized folder: {service.allowed_root}")
