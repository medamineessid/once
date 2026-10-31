"""Once application shell: sidebar, page workspace, banner, and status footer."""

from __future__ import annotations

from pathlib import Path
from typing import override

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
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
from ui.components.banner import Banner
from ui.components.footer import (
    FOOTER_ATTENTION,
    FOOTER_READY,
    FOOTER_RUNNING,
    StatusFooter,
)
from ui.components.icons import (
    draw_activity_glyph,
    draw_automations_glyph,
    draw_home_glyph,
    draw_settings_glyph,
    icon_pixmap,
)
from ui.components.spacer import Spacer
from ui.pages import (
    ActivityPage,
    CreateAutomationPage,
    EditorPage,
    HomePage,
    MyAutomationsPage,
    ReviewPage,
    SettingsPage,
)
from ui.strings import (
    APP_TITLE,
    DEMO_FAILED_TITLE,
    DEMO_FINISHED_BODY,
    DEMO_FINISHED_TITLE,
    DEMO_STOPPED_TITLE,
    RUN_CANCELLED_MESSAGE,
    SIDEBAR_ACTIVITY,
    SIDEBAR_AUTOMATIONS,
    SIDEBAR_HOME,
    SIDEBAR_SETTINGS,
)
from ui.styles import SPACING_LG, SPACING_MD, apply_theme
from ui.workers import WorkflowWorker, cancel_and_join


class ShellPages:
    HOME = 0
    MY_AUTOMATIONS = 1
    ACTIVITY = 2
    SETTINGS = 3
    REVIEW = 4
    CREATE = 5  # stacked page without a sidebar entry; sidebar shows nothing checked
    EDITOR = 6

    @classmethod
    def all(cls):
        return [
            (SIDEBAR_HOME, cls.HOME, "home_page"),
            (SIDEBAR_AUTOMATIONS, cls.MY_AUTOMATIONS, "my_automations_page"),
            (SIDEBAR_ACTIVITY, cls.ACTIVITY, "activity_page"),
            (SIDEBAR_SETTINGS, cls.SETTINGS, "settings_page"),
        ]


class SidebarButton(QToolButton):
    clicked_custom = Signal()

    def __init__(self, text: str, object_name: str, glyph=None, parent=None):
        """Object name keyed by the theme so styling lives in one place."""
        super().__init__(parent)
        self.setText(text)
        self.setObjectName(object_name)
        if glyph is not None:
            self.setIcon(QIcon(icon_pixmap(glyph, 20)))
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
        self.setObjectName("sidebar")
        self.setOrientation(Qt.Orientation.Vertical)
        self.setIconSize(QSize(20, 20))
        self.setMovable(False)
        self.setFloatable(False)
        self.setStyleSheet("QToolBar { background: transparent; }")
        logo = QLabel("Once")
        logo.setObjectName("onceLogo")
        self.addWidget(logo)
        self.addWidget(Spacer())
        self._home_button = SidebarButton(
            SIDEBAR_HOME, "sidebarHomeButton", draw_home_glyph, parent=None
        )
        self._home_button.clicked_custom.connect(self.homeClicked.emit)
        self.addWidget(self._home_button)
        self._automations_button = SidebarButton(
            SIDEBAR_AUTOMATIONS,
            "sidebarAutomationsButton",
            draw_automations_glyph,
            parent=None,
        )
        self._automations_button.clicked_custom.connect(self.automationsClicked.emit)
        self.addWidget(self._automations_button)
        self._activity_button = SidebarButton(
            SIDEBAR_ACTIVITY, "sidebarActivityButton", draw_activity_glyph, parent=None
        )
        self._activity_button.clicked_custom.connect(self.activityClicked.emit)
        self.addWidget(self._activity_button)
        self._settings_button = SidebarButton(
            SIDEBAR_SETTINGS, "sidebarSettingsButton", draw_settings_glyph, parent=None
        )
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
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(960, 600)
        self._service = service or WorkflowService()
        self._recording_service = recording_service
        self._verifier_config = verifier_config
        self._verifier_note = verifier_note
        self._app_data_dir = app_data_dir
        self._demo_worker = None
        self._demo_thread: QThread | None = None
        apply_theme(self)
        self.sidebar = Sidebar(self)
        self.status_footer = StatusFooter(self)
        self.workspace = QStackedWidget(self)
        self.home_page = HomePage(self)
        self.my_automations_page = MyAutomationsPage(self)
        self.activity_page = ActivityPage(self)
        self.settings_page = SettingsPage(self)
        self.review_page = ReviewPage(self)
        self.create_automation_page = CreateAutomationPage(self)
        self.editor_page = EditorPage(self)
        self.workspace.addWidget(self.home_page)
        self.workspace.addWidget(self.my_automations_page)
        self.workspace.addWidget(self.activity_page)
        self.workspace.addWidget(self.settings_page)
        self.workspace.addWidget(self.review_page)
        self.workspace.addWidget(self.create_automation_page)
        self.workspace.addWidget(self.editor_page)
        self.home_page.set_service(self._service)
        self.activity_page.set_service(self._service)
        self.my_automations_page.set_service(self._service)
        self.settings_page.set_service(self._service)
        self.editor_page.set_service(self._service)
        self.settings_page.configure(
            app_data_dir=self._app_data_dir, verifier_config=self._verifier_config
        )
        # Layout: flush-left full-height sidebar; workspace column with the
        # non-modal banner above it and the run status under the sidebar.
        central = QWidget(self)
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        side_panel = QWidget(self)
        side_panel.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(0, 0, 0, SPACING_MD)
        side_layout.setSpacing(0)
        side_layout.addWidget(self.sidebar, stretch=1)
        side_layout.addWidget(self.status_footer)
        side_panel.setFixedWidth(232)
        main_panel = QWidget(self)
        main_panel.setObjectName("mainPanel")
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        main_layout.setSpacing(SPACING_MD)
        self.banner = Banner(self)
        main_layout.addWidget(self.banner)
        main_layout.addWidget(self.workspace)
        central_layout.addWidget(side_panel)
        central_layout.addWidget(main_panel, stretch=1)
        self.setCentralWidget(central)
        self.sidebar.homeClicked.connect(self._show_page_home)
        self.sidebar.automationsClicked.connect(self._show_page_automations)
        self.sidebar.activityClicked.connect(self._show_page_activity)
        self.sidebar.settingsClicked.connect(self._show_page_settings)
        self._install_page_shortcuts()
        self.home_page.created_automation.connect(self._show_create_automation)
        self.home_page.run_demo_requested.connect(self._run_demo_from_home)
        self.my_automations_page.created_automation.connect(self._show_create_automation)
        self.my_automations_page.opened_workflow.connect(self._open_workflow)
        self.create_automation_page.task_entered.connect(self._handle_task_entered)
        self.create_automation_page.editor_requested.connect(self._show_editor)
        self.editor_page.saved.connect(self._editor_saved)
        self.editor_page.cancelled.connect(self._show_create_automation)
        self.review_page.cancelled.connect(self._on_review_cancelled)
        self._finalise_initial_state()
        self._show_page(ShellPages.HOME)

    def _install_page_shortcuts(self) -> None:
        """Ctrl+1..4 switch pages. Ctrl+N is deliberately NOT bound (P4)."""
        bindings = {
            "Ctrl+1": self._show_page_home,
            "Ctrl+2": self._show_page_automations,
            "Ctrl+3": self._show_page_activity,
            "Ctrl+4": self._show_page_settings,
        }
        self._page_shortcuts: dict[str, QShortcut] = {}
        for sequence, handler in bindings.items():
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self._page_shortcuts[sequence] = shortcut

    def _show_page(self, page: ShellPages) -> None:
        self.workspace.setCurrentIndex(page)
        self.sidebar.set_checked(page)
        self._current_page = page

    def _show_page_home(self) -> None:
        self._show_page(ShellPages.HOME)
        self.home_page.refresh()

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

    def _show_editor(self) -> None:
        """Open a fresh definition in the controller-backed editor."""
        self.editor_page.start_new()
        self._show_page(ShellPages.EDITOR)

    def _editor_saved(self) -> None:
        """Return to the saved automation list after a successful save."""
        self.my_automations_page.refresh()
        self._show_page_automations()

    def _run_demo_from_home(self) -> None:
        """Start exactly one demo run off the GUI thread."""
        if self._demo_thread is not None:
            return
        self.status_footer.set_state(FOOTER_RUNNING)
        self._demo_thread = QThread(self)
        self._demo_worker = WorkflowWorker(self._service, self._service.demo_workflow())
        self._demo_worker.moveToThread(self._demo_thread)
        self._demo_thread.started.connect(self._demo_worker.run)
        queued = Qt.ConnectionType.QueuedConnection
        self._demo_worker.progress.connect(self._on_demo_progress, queued)
        self._demo_worker.finished.connect(self._on_demo_finished, queued)
        self._demo_worker.finished.connect(self._quit_demo_thread)
        self._demo_worker.failed.connect(self._on_demo_failed, queued)
        self._demo_worker.failed.connect(self._quit_demo_thread)
        self._demo_thread.finished.connect(self._on_demo_thread_finished, queued)
        self._demo_thread.finished.connect(self._demo_thread.deleteLater)
        # Note: worker.deleteLater is deliberately NOT connected to
        # thread.finished (see ui/pages/my_automations.py for the reasoning);
        # the two deletions race and corrupt the heap.
        self._demo_thread.start()

    def _on_demo_progress(self, step_result: object) -> None:
        self.status_footer.set_state(FOOTER_RUNNING)

    def _quit_demo_thread(self) -> None:
        if self._demo_thread is not None:
            self._demo_thread.quit()

    def _on_demo_thread_finished(self) -> None:
        self._demo_worker = None
        self._demo_thread = None

    def _on_demo_finished(self, run: object) -> None:
        status = getattr(run, "status", None)
        self.status_footer.set_state(FOOTER_READY)
        if status is not None and status.value == "SUCCEEDED":
            self.banner.show_message(
                "success",
                DEMO_FINISHED_TITLE,
                DEMO_FINISHED_BODY,
                dismiss_button=True,
            )
        elif status is not None and status.value == "CANCELLED":
            self.banner.show_message("warning", DEMO_STOPPED_TITLE, RUN_CANCELLED_MESSAGE)
        else:
            self.banner.show_message("error", DEMO_FAILED_TITLE, "The run did not succeed.")
        self.home_page.refresh()
        self.activity_page.refresh()

    def _on_demo_failed(self, message: str) -> None:
        self.status_footer.set_state(FOOTER_ATTENTION)
        self.banner.show_message("error", DEMO_FAILED_TITLE, message)
        self.home_page.refresh()
        self.activity_page.refresh()

    def _open_workflow(self, path: Path) -> None:
        workflow = self._service.load(path)
        self.workspace.setCurrentWidget(self.review_page)
        self.review_page.show_workflow(workflow)

    def _handle_task_entered(self, text: str) -> None:
        """Acknowledge a described task on the create page, non-modally.

        Turning a description into real steps is later migration work: the
        controller has no builder for it, and faking one here would hand the
        user a workflow that cannot run.
        """
        self.create_automation_page.show_not_available(text)

    def _on_review_cancelled(self) -> None:
        self._show_page(ShellPages.HOME)

    @override
    def closeEvent(self, event) -> None:
        if self._recording_service is not None and self._recording_service.recording:
            self._recording_service.stop()
        self.cancel_run_thread()
        self.my_automations_page.shutdown_worker()
        self._service.close()
        super().closeEvent(event)

    def cancel_run_thread(self) -> None:
        """Cooperatively cancel and join the demo thread (bounded)."""
        if self._demo_thread is None:
            return
        cancel_and_join(self._demo_thread, self._demo_worker)
        self._on_demo_thread_finished()


# ensure tests can access internals without relying on private attrs
