"""Home page for Once — the first screen new users see."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService


class HomePage(QWidget):
    """Welcome screen with three primary actions and recent activity."""

    created_automation = Signal()
    run_demo_requested = Signal()
    my_automations_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._activity_panel: QWidget | None = None
        self._create_automation_button: QPushButton | None = None
        self._demo_button: QPushButton | None = None
        self._my_automations_button: QPushButton | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._title_label = QLabel("Welcome to Once", self)
        self._title_label.setObjectName("homeTitle")
        self._title_label.setFont(QFont("Inter", 32, QFont.Weight.Bold, False))
        self._title_label.setStyleSheet("color: #1d1d1d;")
        layout.addWidget(self._title_label, alignment=Qt.AlignHCenter)
        self._subtitle_label = QLabel(
            "Your personal assistant for automating repetitive computer tasks.",
            self,
        )
        self._subtitle_label.setObjectName("homeSubtitle")
        self._subtitle_label.setStyleSheet("font-size: 16px; color: #525252; margin-top: 4px;")
        layout.addWidget(self._subtitle_label, alignment=Qt.AlignHCenter)
        layout.addSpacing(24)
        actions_panel = QFrame(self)
        actions_panel.setObjectName("actionsPanel")
        actions_layout = QVBoxLayout(actions_panel)
        actions_layout.setContentsMargins(8, 8, 8, 8)
        actions_layout.setSpacing(12)
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
        self._my_automations_button = QPushButton("My automations", self)
        self._my_automations_button.setObjectName("secondaryActionButton")
        self._my_automations_button.setMinimumHeight(44)
        self._my_automations_button.clicked.connect(self._open_my_automations)
        actions_layout.addWidget(self._my_automations_button)
        layout.addWidget(actions_panel, alignment=Qt.AlignHCenter)
        layout.addSpacing(24)
        self._activity_panel = QWidget(self)
        self._activity_panel.setObjectName("activityPanel")
        self._activity_layout = QVBoxLayout(self._activity_panel)
        self._activity_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_layout.setSpacing(8)
        self._activity_label = QLabel("Recent activity", self._activity_panel)
        self._activity_label.setObjectName("activityLabel")
        self._activity_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #3a3a3a;")
        self._activity_layout.addWidget(self._activity_label)
        self._activity_empty = QLabel(
            "You haven't run any automations yet. Try the demonstration to get started.",
            self,
        )
        self._activity_empty.setObjectName("activityEmpty")
        self._activity_empty.setStyleSheet("font-size: 13px; color: #6b6b6b;")
        self._activity_layout.addWidget(self._activity_empty)
        layout.addWidget(self._activity_panel, alignment=Qt.AlignHCenter)
        self._refresh_activity()

    def _create_automation(self) -> None:
        self.created_automation.emit()

    def _run_demo(self) -> None:
        self.run_demo_requested.emit()
        if self._service is not None:
            self._service.run_demo()

    def _open_my_automations(self) -> None:
        self.my_automations_requested.emit()

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
                item.setStyleSheet("font-size: 13px; color: #2e7d32;")
                self._activity_layout.addWidget(item)
        else:
            self._activity_empty.show()

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh_activity()
