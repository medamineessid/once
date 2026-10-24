"""Qt worker wrappers for controller operations."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from controller.service import WorkflowService
from engine.agent_change import ApprovedChange, ChangeReview
from engine.errors import OnceError
from engine.workflow import Workflow


class WorkflowWorker(QObject):
    """Run one workflow off the Qt GUI thread with cooperative cancellation."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: WorkflowService,
        workflow: Workflow,
        *,
        replay: bool = False,
        allowed_root: Path | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._workflow = workflow
        self._replay = replay
        self._allowed_root = allowed_root
        self._cancel_requested = Event()

    def cancel(self) -> None:
        """Request cancellation before the next engine step starts."""
        self._cancel_requested.set()

    @Slot()
    def run(self) -> None:
        """Execute the controller operation and publish its outcome."""
        try:
            if self._replay:
                result = self._service.run_replay(
                    self._workflow,
                    allowed_root=self._allowed_root,
                    cancel_check=self._cancel_requested.is_set,
                    progress_callback=self.progress.emit,
                )
            else:
                result = self._service.run_workflow(
                    self._workflow,
                    cancel_check=self._cancel_requested.is_set,
                    progress_callback=self.progress.emit,
                )
        except (OnceError, OSError, sqlite3.Error) as error:
            self.failed.emit(str(error))
        else:
            self.finished.emit(result)


class VerifyProposalWorker(QObject):
    """Run one pre-merge verification off the GUI thread, cancellable."""

    ok = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: WorkflowService,
        review: ChangeReview,
        cases_path: Path,
        argv: tuple[str, ...],
        timeout_seconds: float,
        worktree_root: Path,
    ) -> None:
        super().__init__()
        self._service = service
        self._review = review
        self._cases_path = cases_path
        self._argv = argv
        self._timeout_seconds = timeout_seconds
        self._worktree_root = worktree_root
        self._cancel_requested = Event()

    def cancel(self) -> None:
        self._cancel_requested.set()

    @Slot()
    def run(self) -> None:
        try:
            bundle = self._service.verify_proposal_pre_merge(
                self._review,
                self._cases_path,
                self._argv,
                self._timeout_seconds,
                self._worktree_root,
                cancel_check=self._cancel_requested.is_set,
            )
        except (OnceError, OSError, sqlite3.Error) as error:
            self.failed.emit(str(error))
        else:
            self.ok.emit(bundle)


class ApplyProposalWorker(QObject):
    """Fast-forward one approved change off the GUI thread."""

    ok = Signal(object)
    failed = Signal(str)

    def __init__(self, service: WorkflowService, approved: ApprovedChange) -> None:
        super().__init__()
        self._service = service
        self._approved = approved

    @Slot()
    def run(self) -> None:
        try:
            head = self._service.apply_agent_change(self._approved)
        except (OnceError, OSError, sqlite3.Error) as error:
            self.failed.emit(str(error))
        else:
            self.ok.emit(head)


class ApplyRecordedApprovalWorker(QObject):
    """Apply a proposal whose approval was recorded earlier, off the GUI thread."""

    ok = Signal(object)
    failed = Signal(str)

    def __init__(self, service: WorkflowService, review: ChangeReview) -> None:
        super().__init__()
        self._service = service
        self._review = review

    @Slot()
    def run(self) -> None:
        try:
            head = self._service.apply_recorded_approval(self._review)
        except (OnceError, OSError, sqlite3.Error) as error:
            self.failed.emit(str(error))
        else:
            self.ok.emit(head)


class PostMergeVerifyWorker(QObject):
    """Rerun the required acceptance checks on the merged main checkout."""

    ok = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: WorkflowService,
        review: ChangeReview,
        cases_path: Path,
        argv: tuple[str, ...],
        timeout_seconds: float,
    ) -> None:
        super().__init__()
        self._service = service
        self._review = review
        self._cases_path = cases_path
        self._argv = argv
        self._timeout_seconds = timeout_seconds

    @Slot()
    def run(self) -> None:
        try:
            bundle = self._service.verify_post_merge(
                Path(self._review.repo_path),
                self._cases_path,
                self._argv,
                self._timeout_seconds,
                self._review,
            )
        except (OnceError, OSError, sqlite3.Error) as error:
            self.failed.emit(str(error))
        else:
            self.ok.emit(bundle)
