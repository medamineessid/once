"""Qt worker wrappers for controller operations."""

from __future__ import annotations

import sqlite3
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from controller.service import WorkflowService
from engine.errors import OnceError
from engine.workflow import Workflow


class WorkflowWorker(QObject):
    """Run one workflow off the Qt GUI thread with cooperative cancellation."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, service: WorkflowService, workflow: Workflow) -> None:
        super().__init__()
        self._service = service
        self._workflow = workflow
        self._cancel_requested = Event()

    def cancel(self) -> None:
        """Request cancellation before the next engine step starts."""
        self._cancel_requested.set()

    @Slot()
    def run(self) -> None:
        """Execute the controller operation and publish its outcome."""
        try:
            result = self._service.run_workflow(
                self._workflow,
                cancel_check=self._cancel_requested.is_set,
                progress_callback=self.progress.emit,
            )
        except (OnceError, OSError, sqlite3.Error) as error:
            self.failed.emit(str(error))
        else:
            self.finished.emit(result)
