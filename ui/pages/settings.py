"""Settings — the same page language as everywhere else: band + section cards.

Unfinished features stay hidden, not faked: Settings shows the authorized-folder
choice and the acceptance-checker configuration, edited inline.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QLabel, QScrollArea, QVBoxLayout, QWidget

from controller.service import WorkflowService
from controller.verifier_config import VerifierConfig
from ui.components.band import PageBand
from ui.components.banner import Banner
from ui.components.buttons import ActionButton
from ui.components.cards import SectionCard
from ui.components.verifier_panel import VerifierEditorPanel
from ui.strings import (
    SETTINGS_CONFIG_SAVED_BODY,
    SETTINGS_CONFIG_SAVED_TITLE,
    SETTINGS_NO_DATA_DIR_BODY,
    SETTINGS_NO_DATA_DIR_TITLE,
    SETTINGS_SUBTITLE,
    SETTINGS_TITLE,
)
from ui.styles import SPACING_LG, SPACING_MD, SPACING_XL


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
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self._band = PageBand(
            SETTINGS_TITLE, micro="settings", description=SETTINGS_SUBTITLE, tone="alt", parent=self
        )
        self._micro_label = self._band.micro_label
        self._title_label = self._band.title_label
        self._subtitle_label = self._band.description_label
        page_layout.addWidget(self._band)

        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("settingsScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_widget = QWidget(self)
        scroll_widget.setObjectName("settingsWidget")
        self._scroll_layout = QVBoxLayout(scroll_widget)
        self._scroll_layout.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_XL)
        self._scroll_layout.setSpacing(SPACING_MD)
        self._scroll_layout.setAlignment(Qt.AlignTop)

        self._banner = Banner(scroll_widget)
        self._scroll_layout.addWidget(self._banner)

        self._authorized_card = SectionCard(
            "Authorized folders",
            "Once may only look at folders you choose. Nothing else is read.",
            parent=scroll_widget,
        )
        self._authorized_label = QLabel("No folder selected.", self._authorized_card)
        self._authorized_label.setWordWrap(True)
        self._authorized_label.setObjectName("authorizedLabel")
        self._authorized_card.content.addWidget(self._authorized_label)
        self._choose_authorized_button = ActionButton(
            "Choose folder", variant="secondary", parent=self._authorized_card
        )
        self._choose_authorized_button.clicked.connect(self._choose_authorized_folder)
        self._authorized_card.content.addWidget(
            self._choose_authorized_button, alignment=Qt.AlignmentFlag.AlignLeft
        )
        self._scroll_layout.addWidget(self._authorized_card)

        self._verifier_card = SectionCard(
            "Acceptance checker",
            "The checker reruns acceptance cases against a proposed change before you approve it.",
            parent=scroll_widget,
        )
        self._verifier_panel = VerifierEditorPanel(None, parent=self._verifier_card)
        self._verifier_panel.saved.connect(self._on_verifier_saved)
        self._verifier_card.content.addWidget(self._verifier_panel)
        self._configure_verifier_button = ActionButton(
            "Configure checker…", variant="secondary", parent=self._verifier_card
        )
        self._configure_verifier_button.clicked.connect(self._configure_verifier)
        self._verifier_card.content.addWidget(
            self._configure_verifier_button, alignment=Qt.AlignmentFlag.AlignLeft
        )
        self._scroll_layout.addWidget(self._verifier_card)

        cards = len(self.findChildren(SectionCard))
        self._micro_label.setText(f"{cards} setting{'s' if cards != 1 else ''}")
        self._scroll_layout.addStretch()
        self._scroll_layout.setSpacing(SPACING_MD)
        scroll_area.setWidget(scroll_widget)
        page_layout.addWidget(scroll_area, stretch=1)
        self._verifier_panel.hide()

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
