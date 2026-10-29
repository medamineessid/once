"""FlowForge-inspired application shell."""

from __future__ import annotations

from pathlib import Path
from typing import override

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
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
from ui.styles import SPACING_LG, SPACING_MD, SPACING_SM, apply_theme


class ShellPages:
    HOME = 0
    MY_AUTOMATIONS = 1
    ACTIVITY = 2
    SETTINGS = 3
    CREATE = 5  # stacked page without a sidebar entry; sidebar shows nothing checked

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

    def __init__(self, text: str, object_name: str, parent=None):
        """Object name keyed by the theme so styling lives in one place."""
        super().__init__(parent)
        self.setText(text)
        self.setObjectName(object_name)
        self.setCheckable(True)
        self.setAutoExclusive(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
        self.setStyleSheet("QToolBar { background: transparent; }")
        logo = QLabel("Once")
        logo.setObjectName("onceLogo")
        self.addWidget(logo)
        self.addWidget(Spacer())
        self._home_button = SidebarButton("Home", "sidebarHomeButton")
        self._home_button.clicked_custom.connect(self.homeClicked.emit)
        self.addWidget(self._home_button)
        self._automations_button = SidebarButton("My automations", "sidebarAutomationsButton")
        self._automations_button.clicked_custom.connect(self.automationsClicked.emit)
        self.addWidget(self._automations_button)
        self._activity_button = SidebarButton("Activity", "sidebarActivityButton")
        self._activity_button.clicked_custom.connect(self.activityClicked.emit)
        self.addWidget(self._activity_button)
        self._settings_button = SidebarButton("Settings", "sidebarSettingsButton")
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
        footer = QLabel("Once Assistive Automation")
        footer.setObjectName("sidebarFooter")
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
        self.home_page.set_service(self._service)
        self.activity_page.set_service(self._service)
        self.my_automations_page.set_service(self._service)
        self.settings_page.set_service(self._service)
        self.settings_page.configure(
            app_data_dir=self._app_data_dir, verifier_config=self._verifier_config
        )
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        central_layout.setSpacing(0)
        side_panel = QWidget(self)
        side_panel.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        side_layout.setSpacing(SPACING_SM)
        side_layout.addWidget(self.sidebar)
        side_panel.setFixedWidth(220)
        main_panel = QWidget(self)
        main_panel.setObjectName("mainPanel")
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        main_layout.setSpacing(SPACING_MD)
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
        self.my_automations_page.opened_workflow.connect(self._open_workflow)
        self.create_automation_page.task_entered.connect(self._handle_task_entered)
        self.review_page.cancelled.connect(self._on_review_cancelled)
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
        self.my_automations_page.refresh()

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
        """Enter the create flow through the typed page state, like every page."""
        self._show_page(ShellPages.CREATE)

    def _run_demo_from_home(self) -> None:
        self._service.run_demo()

    def _open_workflow(self, path: Path) -> None:
        workflow = self._service.load(path)
        self.workspace.setCurrentWidget(self.review_page)
        self.review_page.show_workflow(workflow)

    def _handle_task_entered(self, text: str) -> None:
        """Acknowledge a described task without pretending to build a workflow.

        Turning a description into real steps is later migration work: the
        controller has no builder for it, and faking one here would hand the
        user a workflow that cannot run.
        """
        QMessageBox.information(
            self,
            "Not available yet",
            f"Once cannot turn this description into an automation yet:\n\n{text[:200]}\n\n"
            "Nothing was created and no workflow was started.",
        )

    def _on_review_cancelled(self) -> None:
        self._show_page(ShellPages.HOME)

    @override
    def closeEvent(self, event) -> None:
        if self._recording_service is not None and self._recording_service.recording:
            self._recording_service.stop()
        self._service.close()
        super().closeEvent(event)


# ensure tests can access internals without relying on private attrs
