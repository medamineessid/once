"""My automations — each saved automation is a row with its own actions.

Rows carry the name (generated from the first meaningful step when the saved
name says nothing), the saved date, the last status pill, and Run / Open /
Delete controls. There is no global action bar any more: an action always
belongs to the row it changes.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from controller.service import WorkflowService
from engine.errors import OnceError, WorkflowValidationError
from engine.workflow import Workflow
from ui.components.approval_panel import DesktopApprovalPanel
from ui.components.band import PageBand
from ui.components.banner import Banner
from ui.components.buttons import ActionButton
from ui.components.cards import Chip, EmptyState
from ui.components.confirm import InlineConfirm
from ui.components.delete_confirm import (
    DeleteConfirmDialog,
    automation_delete_message,
    clear_drafts_message,
)
from ui.components.formatting import (
    automation_display_name,
    friendly_step_display,
    friendly_step_status,
    human_timestamp,
    is_generic_automation_name,
    status_display,
)
from ui.components.parameter_dialog import ParameterDialog
from ui.components.parameters import (
    apply_parameter_values,
    missing_values,
    parameter_names,
)
from ui.components.scroll_page import ScrollPage
from ui.strings import (
    DELETE_ACTION,
    MY_BANNER_ERROR_TITLE,
    MY_CLEAR_DRAFTS,
    MY_DELETE_ERROR_TITLE,
    MY_DELETE_HINT_BODY,
    MY_DELETE_HINT_TITLE,
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
    MY_SAVED_PREFIX,
    MY_SUBTITLE,
    MY_TITLE,
    MY_UNREADABLE_BODY,
    MY_UNREADABLE_TITLE,
)
from ui.styles import SPACING_LG, SPACING_SM, SPACING_XL
from ui.workers import WorkflowWorker, cancel_and_join


def _saved_on_text(path: Path) -> str:
    """Local last-modified date of a saved automation file, or empty."""
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")


#: The list never grows past this; beyond it the page scrolls instead.
MAX_LIST_HEIGHT = 560


class AutomationRow(QWidget):
    """One saved automation: name, saved date, last status, three actions."""

    run_requested = Signal()
    open_requested = Signal()
    delete_requested = Signal()

    def __init__(
        self,
        title: str,
        status_text: str | None,
        chip_kind: str,
        when_text: str = "",
        saved_on: str = "",
        *,
        on_run: Callable[[], None] | None = None,
        on_open: Callable[[], None] | None = None,
        on_delete: Callable[[], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("automationRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QVBoxLayout(self)
        row.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)
        row.setSpacing(SPACING_SM)

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
            top.addWidget(chip, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.run_button = InlineConfirm(
            MY_RUN, MY_RUN_CONFIRM, confirm_timeout_ms=5000, parent=self
        )
        self.run_button.setObjectName("runRowButton")
        self.run_button.setProperty("variant", "primary")
        self.open_button = ActionButton(MY_OPEN, variant="secondary", parent=self)
        self.delete_button = ActionButton(DELETE_ACTION, variant="destructive", parent=self)
        for button in (self.run_button, self.open_button, self.delete_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        if on_run is not None:
            self.run_button.confirmed.connect(lambda: on_run())
        if on_open is not None:
            self.open_button.clicked.connect(lambda: on_open())
        if on_delete is not None:
            self.delete_button.clicked.connect(lambda: on_delete())
        top.addWidget(self.run_button)
        top.addWidget(self.open_button)
        top.addWidget(self.delete_button)
        row.addLayout(top)

        caption_parts: list[str] = []
        if saved_on:
            caption_parts.append(f"{MY_SAVED_PREFIX} {saved_on}")
        if status_text is None:
            caption_parts.append(MY_NOT_RUN)
        elif when_text:
            caption_parts.append(f"{MY_LAST_RUN_PREFIX} · {status_text} · {when_text}")
        else:
            caption_parts.append(f"{MY_LAST_RUN_PREFIX} · {status_text}")
        caption_text = " · ".join(caption_parts)
        self._caption = QLabel(caption_text, self)
        self._caption.setObjectName("rowCaption")
        row.addWidget(self._caption)

    @property
    def name_text(self) -> str:
        """The displayed automation name, for tests."""
        return self._name_label.text()

    @property
    def caption_text(self) -> str:
        """Captions keep the last-run shape visible next to the name."""
        return self._caption.text()

    def set_running(self, running: bool) -> None:
        """Disable the row's controls while its run is in flight."""
        self.run_button.set_running(running, MY_RUN_RUNNING)
        self.open_button.setEnabled(not running)
        self.delete_button.setEnabled(not running)


class MyAutomationsPage(QWidget):
    """List saved workflows with per-row name, status, date and actions."""

    opened_workflow = Signal(Path)
    workflow_selected = Signal()
    preview_requested = Signal()
    run_requested = Signal(Path)
    created_automation = Signal()
    #: True while this page owns the live run thread, so the shell can show Stop.
    run_state_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._service: WorkflowService | None = None
        self._workflow_list: QListWidget | None = None
        self._worker: WorkflowWorker | None = None
        self._thread: QThread | None = None
        self._pending_approval_path: Path | None = None
        self._rows: list[AutomationRow] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)
        self._band = PageBand(
            MY_TITLE,
            micro="0 saved automations",
            description=MY_SUBTITLE,
            primary_label=MY_NEW_ACTION,
            tone="primary",
            parent=self,
        )
        self._micro_label = self._band.micro_label
        self._title_label = self._band.title_label
        self._subtitle_label = self._band.description_label
        layout.addWidget(self._band)
        if self._band.primary_button is not None:
            self._band.primary_button.clicked.connect(self._create_requested)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        body_layout.setSpacing(SPACING_SM)
        layout.addWidget(ScrollPage(body, self), stretch=1)

        self._banner = Banner(body)
        body_layout.addWidget(self._banner)

        # The two list controls live in their own row above the list. Added
        # after the list they floated over its last row at narrow heights.
        self._toolbar = QWidget(body)
        self._toolbar.setObjectName("myAutomationsToolbar")
        controls = QHBoxLayout(self._toolbar)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(SPACING_SM)
        self._preview_button = ActionButton(MY_PREVIEW, variant="secondary", parent=self._toolbar)
        self._preview_button.clicked.connect(self._preview_selected)
        self._clear_drafts_button = ActionButton(
            MY_CLEAR_DRAFTS, variant="secondary", parent=self._toolbar
        )
        self._clear_drafts_button.clicked.connect(self._clear_unnamed_drafts)
        controls.addWidget(self._preview_button)
        controls.addWidget(self._clear_drafts_button)
        controls.addStretch(1)
        body_layout.addWidget(self._toolbar)

        self._workflow_list = QListWidget(body)
        self._workflow_list.setObjectName("workflowList")
        self._workflow_list.setAlternatingRowColors(False)
        self._workflow_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._workflow_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._workflow_list.setMinimumHeight(200)
        self._workflow_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._workflow_list.itemDoubleClicked.connect(lambda _item: self._open_selected())
        body_layout.addWidget(self._workflow_list, stretch=1)

        self._approval_panel = DesktopApprovalPanel(body)
        self._approval_panel.approved.connect(self._on_run_approved)
        self._approval_panel.cancelled.connect(self._on_run_cancelled)
        body_layout.addWidget(self._approval_panel)
        self._details_label = QLabel(MY_EMPTY, body)
        self._details_label.setObjectName("automationDetailsLabel")
        self._details_label.setWordWrap(True)
        body_layout.addWidget(self._details_label)

        self._empty_state = EmptyState(
            "Nothing saved yet",
            MY_EMPTY,
            icon_name="arrows-down-up",
            parent=body,
        )
        body_layout.addWidget(self._empty_state)
        body_layout.addStretch(1)
        self._refresh()

    # ------------------------------------------------------------- helpers

    def _create_requested(self) -> None:
        """The header action lands the user on the real create flow."""
        self.created_automation.emit()

    def _show_page_error(self, message: str) -> None:
        """Surface a failed load/run on the page banner, never as a modal."""
        self._details_label.setVisible(True)
        self._details_label.setText(f"Error: {message}")
        self._banner.show_message("error", MY_BANNER_ERROR_TITLE, message)

    def _show_run_hint(self) -> None:
        self._banner.show_message("info", MY_RUN_HINT_TITLE, MY_RUN_HINT_BODY)

    # ------------------------------------------------------------------ state

    def _set_running(self, running: bool) -> None:
        self._preview_button.setEnabled(not running)
        for row in self._rows:
            row.set_running(running)

    def _thread_finished(self) -> None:
        self._worker = None
        self._thread = None
        self._set_running(False)
        self.run_state_changed.emit(False)

    @property
    def worker(self) -> WorkflowWorker | None:
        """The live run worker, for the shell's Stop control."""
        return self._worker

    def run_saved(self, saved_path: Path) -> bool:
        """Run one saved automation by path, as its own row's Run would."""
        if self._service is None:
            return False
        for index in range(self._workflow_list.count()):
            item = self._workflow_list.item(index)
            if item is not None and Path(item.data(Qt.UserRole)) == saved_path:
                self._run_row(index)
                return True
        self._refresh()
        return False

    # ------------------------------------------------------------ read paths

    def _show_workflow_details(self, workflow: Workflow) -> None:
        lines = [automation_display_name(workflow.name, workflow.steps)]
        for index, step in enumerate(workflow.steps, start=1):
            title, action_label, clean_desc = friendly_step_display(step)
            line = f"{index}. {action_label}: {title}"
            if clean_desc and clean_desc != title:
                line += f" — {clean_desc}"
            lines.append(line)
        self._details_label.setText("\n".join(lines))

    def _selected_index(self) -> int:
        if self._workflow_list is None:
            return -1
        return self._workflow_list.currentRow()

    def _on_selection_changed(self) -> None:
        self.workflow_selected.emit()
        # A panel is approval for exactly one automation; switching rows
        # discards it, so no stale approval can start a run for another row.
        self._approval_panel.reset()
        self._pending_approval_path = None
        for row in self._rows:
            row.run_button.reset()
        if self._thread is not None:
            self._set_running(True)
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

    def _open_row(self, index: int) -> None:
        """Open one row in the details page."""
        self._workflow_list.setCurrentRow(index)
        self._open_selected()

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
        lines = [f"Preview (read-only): {automation_display_name(workflow.name, workflow.steps)}"]
        lines.extend(f" - {step}" for step in preview.steps)
        if preview.executable:
            lines.append("Status: this replay can be executed.")
        else:
            lines.append("Status: this replay contains unsupported actions and cannot be executed.")
        self._details_label.setText("\n".join(lines))
        self.preview_requested.emit()

    def _delete_row(self, index: int) -> None:
        """Delete the automation named by one row, naming its runs in the dialog."""
        if self._workflow_list is None:
            return
        item = self._workflow_list.item(index)
        if item is None or self._service is None:
            self._banner.show_message("info", MY_DELETE_HINT_TITLE, MY_DELETE_HINT_BODY)
            return
        row_path = item.data(Qt.UserRole)
        if row_path is None:
            return
        saved_path = Path(row_path)
        workflow_id = saved_path.stem
        name = self._display_name_for(saved_path)
        run_count = sum(
            1 for run in self._service.history() if getattr(run, "workflow_id", None) == workflow_id
        )
        choice = DeleteConfirmDialog(
            automation_delete_message(name, run_count),
            runs_count=run_count,
            parent=self,
        ).ask()
        if not choice.confirmed:
            return
        try:
            self._service.delete_automation(workflow_id, delete_runs=choice.delete_runs)
        except OnceError as error:
            self._details_label.setText(f"Error: {error}")
            self._banner.show_message("error", MY_DELETE_ERROR_TITLE, str(error))
            return
        self._approval_panel.reset()
        self._pending_approval_path = None
        self._refresh()

    def _clear_unnamed_drafts(self) -> None:
        """Delete saved automations whose name says nothing, after confirming."""
        if self._service is None:
            return
        drafts = [path for path in self._service.list_saved() if self._is_unnamed(path)]
        if not drafts:
            self._banner.show_message(
                "info",
                "Nothing to clear",
                "Every saved automation already has a name that describes it.",
            )
            return
        choice = DeleteConfirmDialog(clear_drafts_message(len(drafts)), parent=self).ask()
        if not choice.confirmed:
            return
        removed = 0
        failures: list[str] = []
        for path in drafts:
            try:
                self._service.delete_automation(path.stem, delete_runs=choice.delete_runs)
                removed += 1
            except OnceError as error:
                failures.append(f"{path.name}: {error}")
        self._refresh()
        if failures:
            self._banner.show_message("error", MY_DELETE_ERROR_TITLE, "; ".join(failures))
        else:
            self._banner.show_message(
                "success",
                "Unnamed drafts cleared",
                f"Removed {removed} draft{'s' if removed != 1 else ''} that had no useful name.",
            )

    def _is_unnamed(self, path: Path) -> bool:
        """True when the saved workflow's name is a placeholder."""
        if self._service is None:
            return False
        return is_generic_automation_name(self._service.workflow_name(path.stem))

    def _display_name_for(self, path: Path) -> str:
        """Saved name, else a title generated from the steps, else the file name."""
        if self._service is None:
            return path.name
        saved_name = self._service.workflow_name(path.stem)
        steps: tuple[object, ...] = ()
        try:
            workflow = self._service.load(path)
        except WorkflowValidationError:
            steps = ()
        else:
            steps = tuple(workflow.steps)
        return automation_display_name(saved_name, steps, fallback=path.name)

    # ----------------------------------------------------------- run (mutating)

    def _run_row(self, index: int) -> None:
        """Start one row's run; the row's own button armed the confirmation."""
        if self._workflow_list is None:
            return
        self._workflow_list.setCurrentRow(index)
        item = self._workflow_list.item(index)
        if item is None or self._service is None:
            self._show_run_hint()
            return
        saved_path = Path(item.data(Qt.UserRole))
        try:
            workflow = self._service.load(saved_path)
        except WorkflowValidationError as error:
            self._show_page_error(str(error))
            return
        filled = self._ask_for_parameters(workflow)
        if filled is None:
            return
        workflow = filled
        if self._approval_panel.show_for(workflow):
            # Mutating desktop automations wait here: the approval panel is
            # the run gate, so the run starts only from the panel's Approve.
            self._pending_approval_path = saved_path
            self._set_running(True)
            return
        self.run_requested.emit(saved_path)
        self._start_run(workflow)

    def _ask_for_parameters(self, workflow: Workflow) -> Workflow | None:
        """Ask for any value the automation left open, or None when cancelled."""
        names = parameter_names(workflow)
        if not names:
            return workflow
        values = ParameterDialog(names, parent=self).ask()
        if values is None:
            self._details_label.setVisible(True)
            self._details_label.setText("Nothing ran: this automation needs a value first.")
            return None
        missing = missing_values(workflow, values)
        if missing:
            self._show_page_error(
                f"Every value is needed before '{missing[0].replace('_', ' ')}' can be used."
            )
            return None
        return apply_parameter_values(workflow, values)

    # ----------------------------------------------------- desktop approval

    def _on_run_approved(self, approval: object) -> None:
        """The panel's Approve click passed the gate; run the automation."""
        saved_path = self._pending_approval_path
        self._pending_approval_path = None
        if saved_path is None or self._service is None:
            return
        self.run_requested.emit(saved_path)
        self._start_run(approval.workflow, approval=approval)  # type: ignore[attr-defined]

    def _on_run_cancelled(self) -> None:
        """The panel was declined: nothing runs and the page stays usable."""
        self._pending_approval_path = None
        self._set_running(False)

    def _start_run(self, workflow: Workflow, approval: object | None = None) -> None:
        if self._thread is not None:
            return
        name = automation_display_name(workflow.name, workflow.steps)
        self._details_label.setVisible(True)
        self._details_label.setText(f"Running '{name}'...")
        self._set_running(True)
        self.run_state_changed.emit(True)
        self._thread = QThread(self)
        self._worker = WorkflowWorker(self._service, workflow, desktop_approval=approval)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        # The handlers below touch widgets, so they must run in the GUI thread.
        queued = Qt.ConnectionType.QueuedConnection
        self._worker.progress.connect(self._on_run_progress, queued)
        self._worker.finished.connect(self._on_run_finished, queued)
        self._worker.finished.connect(self._quit_run_thread)
        self._worker.failed.connect(self._on_run_failed, queued)
        self._worker.failed.connect(self._quit_run_thread)
        self._thread.finished.connect(self._thread_finished, queued)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _quit_run_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()

    def shutdown_worker(self) -> None:
        """Cancel and join the running automation thread for window close."""
        if self._thread is None:
            self._approval_panel.reset()
            self._pending_approval_path = None
            return
        cancel_and_join(self._thread, self._worker)
        self._worker = None
        self._thread = None

    def _on_run_progress(self, step_result: object) -> None:
        evidence = (
            f" [{'; '.join(step_result.evidence)}]" if step_result.evidence else ""  # type: ignore[attr-defined]
        )
        label = friendly_step_status(getattr(step_result.status, "value", ""))
        line = f"{label} — {step_result.message}{evidence}"  # type: ignore[attr-defined]
        self._details_label.setText(f"{self._details_label.text()}\n{line}")

    def _on_run_finished(self, run: object) -> None:
        status_value = getattr(getattr(run, "status", None), "value", "Unknown")
        label, _chip = status_display(status_value, getattr(run, "results", None))
        # Refresh first (it updates the row's last-run pill and resets the
        # details placeholder), then show the outcome so it is not wiped.
        self._refresh()
        self._details_label.setText(
            f"Run {label}: {len(run.results)} steps recorded."  # type: ignore[attr-defined]
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
        # Clearing the list emits itemSelectionChanged; without blocking it the
        # page reloads a workflow that was just deleted and reports a stale
        # "not found" error.
        blocked = QSignalBlocker(self._workflow_list)
        self._workflow_list.clear()
        self._rows.clear()
        if self._service is None:
            self._micro_label.setText("0 saved automations")
            self._details_label.setText(MY_EMPTY)
            self._workflow_list.setVisible(False)
            return
        saved_paths = tuple(self._service.list_saved())
        count = len(saved_paths)
        self._micro_label.setText(f"{count} saved automation{'s' if count != 1 else ''}")
        unreadable = 0
        for index, path in enumerate(saved_paths):
            saved_name = self._service.workflow_name(path.stem)
            if saved_name is None:
                unreadable += 1
            item = QListWidgetItem("")
            item.setData(Qt.UserRole, path)
            run = self._last_run_for(path.stem)
            status_text = None
            chip_kind = "neutral"
            if run is not None:
                status_value = getattr(getattr(run, "status", None), "value", "Unknown")
                status_text, chip_kind = status_display(status_value, getattr(run, "results", None))
            row = AutomationRow(
                self._display_name_for(path),
                status_text,
                chip_kind,
                when_text=human_timestamp(getattr(run, "finished_at", None)) if run else "",
                saved_on=_saved_on_text(path),
                on_run=lambda idx=index: self._run_row(idx),
                on_open=lambda idx=index: self._open_row(idx),
                on_delete=lambda idx=index: self._delete_row(idx),
                parent=self._workflow_list,
            )
            item.setSizeHint(row.sizeHint())
            self._workflow_list.addItem(item)
            self._workflow_list.setItemWidget(item, row)
            self._rows.append(row)
        self._workflow_list.setVisible(bool(saved_paths))
        self._empty_state.setVisible(not saved_paths)
        self._fit_rows()
        if unreadable:
            # An icon carries the severity; the banner never prints the word
            # "Warning" as plain text.
            self._banner.show_message("warning", MY_UNREADABLE_TITLE, MY_UNREADABLE_BODY)
        if not saved_paths:
            self._details_label.setVisible(False)
            return
        self._details_label.setVisible(True)
        self._details_label.setText(MY_DETAILS_EMPTY)
        del blocked

    def _fit_rows(self) -> None:
        """Size the list to the rows it holds.

        A row's height only settles once its stylesheet padding and fonts are
        applied, so measure the rendered rows instead of guessing: a fixed
        guess used to clip the last automation off the bottom of the list.
        """
        if self._workflow_list is None or not self._rows:
            return
        spacing = self._workflow_list.spacing()
        total = 2 * self._workflow_list.frameWidth()
        for index, row in enumerate(self._rows):
            row.ensurePolished()
            measured = row.sizeHint().height()
            self._workflow_list.item(index).setSizeHint(row.sizeHint())
            total += measured
        total += spacing * max(0, self._workflow_list.count() - 1)
        self._workflow_list.setFixedHeight(min(MAX_LIST_HEIGHT, total))

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        self._fit_rows()

    def set_service(self, service: WorkflowService | None) -> None:
        self._service = service
        self._refresh()
