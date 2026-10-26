"""FlowForge-inspired application shell."""

from __future__ import annotations

from pathlib import Path
from typing import override

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from controller.recording import RecordingService
from controller.service import WorkflowService
from controller.verifier_config import VerifierConfig
from ui.components.spacer import Spacer
from ui.pages import (
    ActivityPage,
    CreateAutomationPage,
    HomePage,
    MyAutomationsPage,
    ReviewPage,
    SettingsPage,
)
from ui.styles import apply_theme


class ShellPages:
    HOME = 0
    MY_AUTOMATIONS = 1
    ACTIVITY = 2
    SETTINGS = 3

    @classmethod
    def all(cls):
        return [
            ("Home", cls.HOME, "home_page"),
            ("My automations", cls.MY_AUTOMATIONS, "my_automations_page"),
            ("Activity", cls.ACTIVITY, "activity_page"),
            ("Settings", cls.SETTINGS, "settings_page"),
        ]


class SidebarButton(QToolButton):
    clicked_custom = Signal()

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setAutoExclusive(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setStyleSheet(
            "QToolButton { background: transparent; border: none; "
            "border-left: 3px solid transparent; color: #4A4A4A; "
            "font-size: 14px; padding: 10px 12px; border-radius: 0 8px 8px 0; "
            "font-family: 'Inter', 'Segoe UI', 'SF Pro Display', system-ui, sans-serif; }"
            "QToolButton:hover { background: #F3F4F6; color: #1D1D1D; }"
            "QToolButton:checked { background: #FFFFFF; "
            "border-left: 3px solid #2563EB; color: #1D1D1D; font-weight: 500; }"
        )
        self.clicked.connect(self.clicked_custom.emit)


class Sidebar(QToolBar):
    homeClicked = Signal()  # noqa: N815
    automationsClicked = Signal()  # noqa: N815
    activityClicked = Signal()  # noqa: N815
    settingsClicked = Signal()  # noqa: N815

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setIconSize(QSize(20, 20))
        self.setMovable(False)
        self.setFloatable(False)
        self.setStyleSheet("QToolBar { background: transparent; };")
        logo = QLabel("Once")
        logo.setObjectName("onceLogo")
        self.addWidget(logo)
        self.addWidget(Spacer())
        self._home_button = SidebarButton("Home")
        self._home_button.clicked_custom.connect(self.homeClicked.emit)
        self.addWidget(self._home_button)
        self._automations_button = SidebarButton("My automations")
        self._automations_button.clicked_custom.connect(self.automationsClicked.emit)
        self.addWidget(self._automations_button)
        self._activity_button = SidebarButton("Activity")
        self._activity_button.clicked_custom.connect(self.activityClicked.emit)
        self.addWidget(self._activity_button)
        self._settings_button = SidebarButton("Settings")
        self._settings_button.clicked_custom.connect(self.settingsClicked.emit)
        self.addWidget(self._settings_button)
        for button in (
            self._home_button,
            self._automations_button,
            self._activity_button,
            self._settings_button,
        ):
            button.setAutoRepeat(False)
        self.addWidget(Spacer())
        mfr = QLabel("Once")
        mfr.setObjectName("onceManufacturer")
        self.addWidget(mfr)
        self.addWidget(Spacer())
        self.addWidget(QLabel("Assistive automation"))
        self.addWidget(QLabel("local"))
        self.addWidget(Spacer())
        self.addWidget(QLabel("offline by default"))
        self.addSeparator()
        footer = QLabel("Once Assistive Automation")
        footer.setObjectName("sidebarFooter")
        footer.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.addWidget(footer)

    def set_checked(self, page: ShellPages) -> None:
        self._home_button.setChecked(page == ShellPages.HOME)
        self._automations_button.setChecked(page == ShellPages.MY_AUTOMATIONS)
        self._activity_button.setChecked(page == ShellPages.ACTIVITY)
        self._settings_button.setChecked(page == ShellPages.SETTINGS)

    def is_on(self, page: ShellPages) -> bool:
        return (
            (page == ShellPages.HOME and self._home_button.isChecked())
            or (page == ShellPages.MY_AUTOMATIONS and self._automations_button.isChecked())
            or (page == ShellPages.ACTIVITY and self._activity_button.isChecked())
            or (page == ShellPages.SETTINGS and self._settings_button.isChecked())
        )


class MainWindow(QMainWindow):
    """Native PySide6 shell for Once."""

    def __init__(
        self,
        service: WorkflowService | None = None,
        recording_service: RecordingService | None = None,
        verifier_config: VerifierConfig | None = None,
        verifier_note: str | None = None,
        app_data_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Once")
        self.setMinimumSize(960, 620)
        self._service = service or WorkflowService()
        self._recording_service = recording_service
        self._verifier_config = verifier_config
        self._verifier_note = verifier_note
        self._app_data_dir = app_data_dir
        apply_theme(self)
        self.sidebar = Sidebar(self)
        self.workspace = QStackedWidget(self)
        self.home_page = HomePage(self)
        self.my_automations_page = MyAutomationsPage(self)
        self.activity_page = ActivityPage(self)
        self.settings_page = SettingsPage(self)
        self.review_page = ReviewPage(self)
        self.create_automation_page = CreateAutomationPage(self)
        self.workspace.addWidget(self.home_page)
        self.workspace.addWidget(self.my_automations_page)
        self.workspace.addWidget(self.activity_page)
        self.workspace.addWidget(self.settings_page)
        self.workspace.addWidget(self.review_page)
        self.workspace.addWidget(self.create_automation_page)
        self.activity_page.set_service(self._service)
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(12, 12, 12, 12)
        central_layout.setSpacing(0)
        side_panel = QWidget(self)
        side_panel.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(8, 8, 8, 8)
        side_layout.setSpacing(8)
        side_layout.addWidget(self.sidebar)
        side_panel.setFixedWidth(220)
        main_panel = QWidget(self)
        main_panel.setObjectName("mainPanel")
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        main_layout.addWidget(self.workspace)
        central_layout.addWidget(side_panel)
        central_layout.addWidget(main_panel)
        self.setCentralWidget(central)
        self.sidebar.homeClicked.connect(self._show_page_home)
        self.sidebar.automationsClicked.connect(self._show_page_automations)
        self.sidebar.activityClicked.connect(self._show_page_activity)
        self.sidebar.settingsClicked.connect(self._show_page_settings)
        self.home_page.created_automation.connect(self._show_create_automation)
        self.home_page.run_demo_requested.connect(self._run_demo_from_home)
        self.home_page.my_automations_requested.connect(self._show_my_automations)
        self.my_automations_page.opened_workflow.connect(self._open_workflow)
        self.my_automations_page.preview_requested.connect(self._preview_workflow)
        self.my_automations_page.run_requested.connect(self._run_workflow_from_list)
        self.create_automation_page.task_entered.connect(self._handle_task_entered)
        self.review_page.approved.connect(self._on_approved)
        self.review_page.cancelled.connect(self._on_review_cancelled)
        self.activity_page.run_selected.connect(self._show_run_details)
        self.settings_page.verifier_configured.connect(self._on_verifier_configured)
        self.settings_page.recording_started.connect(self._on_recording_started)
        self.settings_page.recording_stopped.connect(self._on_recording_stopped)
        self._finalise_initial_state()
        self._show_page(ShellPages.HOME)

    def _show_page(self, page: ShellPages) -> None:
        self.workspace.setCurrentIndex(page)
        self.sidebar.set_checked(page)
        self._current_page = page

    def _show_page_home(self) -> None:
        self._show_page(ShellPages.HOME)

    def _show_page_automations(self) -> None:
        self._show_page(ShellPages.MY_AUTOMATIONS)

    def _show_page_activity(self) -> None:
        self._show_page(ShellPages.ACTIVITY)
        self.activity_page.refresh()

    def _show_page_settings(self) -> None:
        self._show_page(ShellPages.SETTINGS)

    def _finalise_initial_state(self) -> None:
        """Called after all signals are connected so the initial HOME page
        correctly reflects in the sidebar."""
        self.sidebar.set_checked(ShellPages.HOME)
        self._current_page = ShellPages.HOME

    def _show_create_automation(self) -> None:
        self.workspace.setCurrentWidget(self.create_automation_page)

    def _run_demo_from_home(self) -> None:
        self._service.run_demo()

    def _show_my_automations(self) -> None:
        self.workspace.setCurrentWidget(self.my_automations_page)

    def _open_workflow(self, path: Path) -> None:
        workflow = self._service.load(path)
        self.workspace.setCurrentWidget(self.review_page)
        self.review_page.set_workflow(workflow)

    def _preview_workflow(self, path: Path) -> None:
        workflow = self._service.load(path)
        self.workspace.setCurrentWidget(self.review_page)
        self.review_page.set_workflow(workflow)

    def _run_workflow_from_list(self, path: Path) -> None:
        workflow = self._service.load(path)
        self._service.run_workflow(workflow)

    def _handle_task_entered(self, text: str) -> None:
        workflow = self._service.build_workflow_from_task(text)
        self.workspace.setCurrentWidget(self.review_page)
        self.review_page.set_workflow(workflow)

    def _on_approved(self) -> None:
        pass

    def _on_review_cancelled(self) -> None:
        self._show_page(ShellPages.HOME)

    def _show_run_details(self) -> None:
        pass

    def _on_verifier_configured(self) -> None:
        pass

    def _on_recording_started(self) -> None:
        pass

    def _on_recording_stopped(self) -> None:
        pass

    @override
    def closeEvent(self, event) -> None:
        if self._recording_service is not None and self._recording_service.recording:
            self._recording_service.stop()
        self._service.close()
        super().closeEvent(event)


# ensure tests can access internals without relying on private attrs
