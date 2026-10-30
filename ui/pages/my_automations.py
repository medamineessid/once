"""My Automations page — manage saved workflows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from engine.errors import WorkflowValidationError
from engine.workflow import Workflow
from ui.components.banner import Banner
from ui.components.cards import Chip
from ui.components.confirm import InlineConfirm
from ui.components.formatting import human_timestamp, status_display
from ui.components.pageheader import PageHeader
from ui.strings import (
    MY_BANNER_ERROR_TITLE,
    MY_DETAILS_EMPTY,
    MY_EMPTY,
    MY_LAST_RUN_PREFIX,
    MY_NEW_ACTION,
    MY_NOT_RUN,
    MY_OPEN,
    MY_PREVIEW,
    MY_RUN,
    MY_RUN_CONFIRM,
    MY_RUN_HINT_BODY,
    MY_RUN_HINT_TITLE,
    MY_RUN_RUNNING,
    MY_SUBTITLE,
    MY_TITLE,
)
from ui.styles import SPACING_LG, SPACING_SM, SPACING_XL
from ui.workers import WorkflowWorker

_ROW_HEIGHT = 56


class AutomationRow(QWidget):
    """One saved automation: Name on the left, last run shape on the right."""

    def __init__(
        self,
        title: str,
        status_text: str | None,
        chip_kind: str,
        when_text: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("automationRow")
        row = QVBoxLayout(self)
        row.setContentsMargins(6, 6, 6, 6)
        row.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(SPACING_SM)
        self._name_label = QLabel(title, self)
        self._name_label.setObjectName("rowTitle")
        if status_text is None:
            chip: QWidget | None = None
        else:
            chip = Chip(status_text, kind=chip_kind, parent=self)
        top.addWidget(self._name_label)
        top.addStretch(1)
        if chip is not None:
            top.addWidget(chip)
        row.addLayout(top)
        if status_text is None:
            caption_text = MY_NOT_RUN
        elif when_text:
            caption_text = f"{MY_LAST_RUN_PREFIX} · {status_text} · {when_text}"
        else:
            caption_text = f"{MY_LAST_RUN_PREFIX} · {status_text}"
        self._caption = QLabel(caption_text, self)
        self._caption.setObjectName("rowCaption")
        row.addWidget(self._caption)

    @property
    def caption_text(self) -> str:
        """Captions keep the last-run shape visible next to the filename."""
        return self._caption.text()


class MyAutomationsPage(QWidget):
    """List saved workflows with name, last status, and actions."""

    opened_workflow = Signal(Path)
    workflow_selected = Signal()
    preview_requested = Signal()
    run_requested = Signal(Path)
    created_automation = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._workflow_list: QListWidget | None = None
        self._worker: WorkflowWorker | None = None
        self._thread: QThread | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_LG)
        layout.setAlignment(Qt.AlignTop)
        self._header = PageHeader(MY_TITLE, MY_SUBTITLE, primary_label=MY_NEW_ACTION, parent=self)
        self._title_label = self._header.title_label
        self._subtitle_label = self._header.description_label
        layout.addWidget(self._header)
        if self._header.primary_button is not None:
            self._header.action_requested.connect(self._create_requested)

        self._banner = Banner(self)
        layout.addWidget(self._banner)

        self._workflow_list = QListWidget(self)
        self._workflow_list.setObjectName("workflowList")
        self._workflow_list.setAlternatingRowColors(True)
        self._workflow_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._workflow_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._workflow_list, stretch=1)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(SPACING_SM)
        self._open_button = QPushButton(MY_OPEN, self)
        self._open_button.setObjectName("secondaryActionButton")
        self._open_button.setMinimumHeight(38)
        self._open_button.clicked.connect(self._open_selected)
        self._preview_button = QPushButton(MY_PREVIEW, self)
        self._preview_button.setObjectName("secondaryActionButton")
        self._preview_button.setMinimumHeight(38)
        self._preview_button.clicked.connect(self._preview_selected)
        self._run_button = InlineConfirm(
            MY_RUN, MY_RUN_CONFIRM, confirm_timeout_ms=5000, parent=self
        )
        self._run_button.setMinimumHeight(38)
        self._run_button.confirmed.connect(self._on_run_confirmed)
        actions_row.addWidget(self._open_button)
        actions_row.addWidget(self._preview_button)
        actions_row.addWidget(self._run_button)
        actions_container = QFrame(self)
        actions_container.setObjectName("actionsContainer")
        actions_container_layout = QVBoxLayout(actions_container)
        actions_container_layout.setContentsMargins(0, 0, 0, 0)
        actions_container_layout.setSpacing(SPACING_SM)
        actions_container_layout.addLayout(actions_row)
        layout.addWidget(actions_container)
        layout.addSpacing(SPACING_SM)
        self._details_label = QLabel(MY_EMPTY, self)
        self._details_label.setObjectName("automationDetailsLabel")
        self._details_label.setWordWrap(True)
        layout.addWidget(self._details_label)
        self._refresh()

    # ------------------------------------------------------------- helpers

    def _create_requested(self) -> None:
        """The header action lands the user on the real create flow."""
        self.created_automation.emit()

    def _show_page_error(self, message: str) -> None:
        """Surface a failed load/run on the page banner, never as a modal."""
        self._details_label.setText(f"Error: {message}")
        self._banner.show_message("error", MY_BANNER_ERROR_TITLE, message)

    def _show_run_hint(self) -> None:
        self._banner.show_message("info", MY_RUN_HINT_TITLE, MY_RUN_HINT_BODY)

    # ------------------------------------------------------------------ state

    def _set_running(self, running: bool) -> None:
        self._open_button.setEnabled(not running)
        self._preview_button.setEnabled(not running)
        self._run_button.set_running(running, MY_RUN_RUNNING)

    def _thread_finished(self) -> None:
        self._worker = None
        self._thread = None
        self._set_running(False)

    # ------------------------------------------------------------ read paths

    def _show_workflow_details(self, workflow: Workflow) -> None:
        lines = [f"{workflow.name} ({workflow.workflow_id})"]
        lines.extend(f"{step.kind.value} - {step.name}: {step.message}" for step in workflow.steps)
        self._details_label.setText("\n".join(lines))

    def _on_selection_changed(self) -> None:
        self.workflow_selected.emit()
        self._run_button.reset()
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            self._details_label.setText(MY_DETAILS_EMPTY)
            return
        row_path = item.data(Qt.UserRole)
        if row_path is None:
            return
        try:
            workflow = self._service.load(Path(row_path))
        except WorkflowValidationError as error:
            # Row navigation stays modal-free; the message is shown inline.
            self._details_label.setText(f"Could not show '{item.text()}': {error}")
            return
        self._show_workflow_details(workflow)

    def _open_selected(self) -> None:
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            return
        saved_path = Path(item.data(Qt.UserRole))
        try:
            workflow = self._service.load(saved_path)
        except WorkflowValidationError as error:
            self._show_page_error(str(error))
            return
        self._show_workflow_details(workflow)
        self.opened_workflow.emit(saved_path)

    def _preview_selected(self) -> None:
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            return
        saved_path = Path(item.data(Qt.UserRole))
        try:
            workflow = self._service.load(saved_path)
        except WorkflowValidationError as error:
            self._show_page_error(str(error))
            return
        try:
            preview = self._service.preview_replay(workflow)
        except WorkflowValidationError as error:
            self._show_page_error(str(error))
            return
        lines = [f"Preview (read-only): {workflow.name} ({preview.workflow_id})"]
        lines.extend(f" - {step}" for step in preview.steps)
        if preview.executable:
            lines.append("Status: this replay can be executed.")
        else:
            lines.append("Status: this replay contains unsupported actions and cannot be executed.")
        self._details_label.setText("\n".join(lines))
        self.preview_requested.emit()

    # ----------------------------------------------------------- run (mutating)

    def _on_run_confirmed(self) -> None:
        """The inline confirm completed its second click; start the run."""
        item = self._workflow_list.currentItem()
        if item is None or self._service is None:
            self._run_button.reset()
            self._show_run_hint()
            return
        saved_path = Path(item.data(Qt.UserRole))
        try:
            workflow = self._service.load(saved_path)
        except WorkflowValidationError as error:
            self._run_button.reset()
            self._show_page_error(str(error))
            return
        self.run_requested.emit(saved_path)
        self._start_run(workflow)

    def _start_run(self, workflow: Workflow) -> None:
        if self._thread is not None:
            return
        self._details_label.setText(f"Running '{workflow.name}'...")
        self._set_running(True)
        self._thread = QThread(self)
        self._worker = WorkflowWorker(self._service, workflow)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        # The handlers below touch widgets, so they must run in the GUI thread.
        # WorkflowWorker emits from its own thread and these slots are plain
        # Python callables, which Qt would otherwise invoke in the worker
        # thread (cross-thread widget access aborts the process).
        queued = Qt.ConnectionType.QueuedConnection
        self._worker.progress.connect(self._on_run_progress, queued)
        self._worker.finished.connect(self._on_run_finished, queued)
        self._worker.finished.connect(self._quit_run_thread)
        self._worker.failed.connect(self._on_run_failed, queued)
        self._worker.failed.connect(self._quit_run_thread)
        self._thread.finished.connect(self._thread_finished, queued)
        self._thread.finished.connect(self._thread.deleteLater)
        # Note: worker.deleteLater is deliberately NOT connected to
        # thread.finished. QThread flushes that DeferredDelete itself while
        # finishing, and the Python wrapper still owns the worker until
        # _thread_finished drops it; the two deletions race and corrupt the
        # heap (intermittent process abort, reproduced in tests).
        self._thread.start()

    def _quit_run_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()

    def _on_run_progress(self, step_result: object) -> None:
        evidence = (
            f" [{'; '.join(step_result.evidence)}]" if step_result.evidence else ""  # type: ignore[attr-defined]
        )
        line = (
            f"{step_result.step_id}: {step_result.status.value}"  # type: ignore[attr-defined]
            f" - {step_result.message}{evidence}"  # type: ignore[attr-defined]
        )
        self._details_label.setText(f"{self._details_label.text()}\n{line}")

    def _on_run_finished(self, run: object) -> None:
        self._details_label.setText(
            f"Run {run.status.value}: {len(run.results)} steps recorded."  # type: ignore[attr-defined]
        )

    def _on_run_failed(self, message: str) -> None:
        self._details_label.setText(f"Error: {message}")
        self._banner.show_message("error", MY_BANNER_ERROR_TITLE, message)

    # ---------------------------------------------------------------- refresh

    def _last_run_for(self, workflow_id: str) -> object | None:
        """Newest run for the given id, or None when it never ran."""
        if self._service is None:
            return None
        for run in self._service.history():
            if getattr(run, "workflow_id", None) == workflow_id:
                return run
        return None

    def refresh(self) -> None:
        """Reload the saved workflow list shown on this page."""
        self._refresh()

    def _refresh(self) -> None:
        self._workflow_list.clear()
        if self._service is None:
            self._details_label.setText(MY_EMPTY)
            return
        saved_paths = tuple(self._service.list_saved())
        for path in saved_paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, path)
            run = self._last_run_for(path.stem)
            status_text = None
            chip_kind = "neutral"
            if run is not None:
                status_value = getattr(getattr(run, "status", None), "value", "Unknown")
                status_text, chip_kind = status_display(status_value)
            row = AutomationRow(
                path.stem,
                status_text,
                chip_kind,
                when_text=human_timestamp(getattr(run, "finished_at", None)) if run else "",
                parent=self._workflow_list,
            )
            hint = row.sizeHint()
            hint.setHeight(_ROW_HEIGHT)
            item.setSizeHint(hint)
            self._workflow_list.addItem(item)
            self._workflow_list.setItemWidget(item, row)
        if not saved_paths:
            self._details_label.setText(MY_EMPTY)
            return
        self._details_label.setText(MY_DETAILS_EMPTY)

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh()
