"""Home page for Once — the first screen new users see."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL, SPACING_XXL


class HomePage(QWidget):
    """Welcome screen with two actions and recent activity."""

    created_automation = Signal()
    run_demo_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._activity_panel: QWidget | None = None
        self._create_automation_button: QPushButton | None = None
        self._demo_button: QPushButton | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XXL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("Welcome to Once", self)
        self._title_label.setObjectName("homeTitle")
        layout.addWidget(self._title_label, alignment=Qt.AlignHCenter)
        self._subtitle_label = QLabel(
            "Your personal assistant for automating repetitive computer tasks.",
            self,
        )
        self._subtitle_label.setObjectName("homeSubtitle")
        layout.addWidget(self._subtitle_label, alignment=Qt.AlignHCenter)
        layout.addSpacing(SPACING_XXL)
        actions_panel = QFrame(self)
        actions_panel.setObjectName("actionsPanel")
        actions_layout = QVBoxLayout(actions_panel)
        actions_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        actions_layout.setSpacing(SPACING_MD)
        actions_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._create_automation_button = QPushButton("Create an automation", self)
        self._create_automation_button.setObjectName("primaryActionButton")
        self._create_automation_button.setMinimumHeight(44)
        self._create_automation_button.setDefault(True)
        self._create_automation_button.clicked.connect(self._create_automation)
        actions_layout.addWidget(self._create_automation_button)
        self._demo_button = QPushButton("Try a demonstration", self)
        self._demo_button.setObjectName("secondaryActionButton")
        self._demo_button.setMinimumHeight(44)
        self._demo_button.clicked.connect(self._run_demo)
        actions_layout.addWidget(self._demo_button)
        layout.addWidget(actions_panel, alignment=Qt.AlignHCenter)
        layout.addSpacing(SPACING_XXL)
        self._activity_panel = QWidget(self)
        self._activity_panel.setObjectName("activityPanel")
        self._activity_layout = QVBoxLayout(self._activity_panel)
        self._activity_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_layout.setSpacing(SPACING_SM)
        self._activity_label = QLabel("Recent activity", self._activity_panel)
        self._activity_label.setObjectName("activityLabel")
        self._activity_layout.addWidget(self._activity_label)
        self._activity_empty = QLabel(
            "You haven't run any automations yet. Try the demonstration to get started.",
            self,
        )
        self._activity_empty.setObjectName("activityEmpty")
        self._activity_layout.addWidget(self._activity_empty)
        layout.addWidget(self._activity_panel, alignment=Qt.AlignHCenter)
        self._refresh_activity()

    def _create_automation(self) -> None:
        self.created_automation.emit()

    def _run_demo(self) -> None:
        """Emit the typed request; the shell triggers exactly one demo run."""
        self.run_demo_requested.emit()

    def _refresh_activity(self) -> None:
        if self._service is None:
            return
        passes = []
        for run in self._service.history():
            if run.status.value == "SUCCEEDED":
                passes.append(run)
        if passes:
            self._activity_empty.hide()
            for run in passes:
                item = QLabel(f"✓ {run.workflow_id} completed", self)
                item.setObjectName("activityItem")
                self._activity_layout.addWidget(item)
        else:
            self._activity_empty.show()

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh_activity()
