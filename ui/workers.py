"""Qt worker wrappers for controller operations."""

from __future__ import annotations

import atexit
import logging
import sqlite3
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, Signal, Slot

from controller.run_events import RunEvent, RunEventSource, RunEventStream
from controller.service import WorkflowService
from engine.agent_change import ApprovedChange, ChangeReview
from engine.errors import OnceError
from engine.workflow import Workflow

logger = logging.getLogger(__name__)


def cancel_and_join(thread: QThread | None, worker: WorkflowWorker | None) -> bool:
    """Cooperatively cancel the worker, then join the thread with a bound.

    Closing a window during a demo or an automation run must (1) ask the
    engine to stop at the next step boundary through the worker's cancel
    flag, (2) quit the thread's event loop, and (3) join it within a fixed
    bound. Returns True when the thread finished inside the bound and can
    be destroyed safely. On timeout the thread is detached from its parent:
    destroying a still-running QThread aborts the process, so the window
    close must never leave it parented while busy (AD-015 rationale).

    A worker that ignores the cancel flag would still be running when the
    process exits. Destroying a running QThread at interpreter shutdown
    makes PySide6 fail-fast (Windows exit code -1073740791), so detach also
    remembers the thread in a module-level registry and lets an
    interpreter-exit hook give it one generous bounded join first; a
    QThread that has finished is always destroyed safely (proven by
    tests/test_b6_cancel_detach_exit.py).
    """
    if thread is None:
        return True
    if worker is not None:
        worker.cancel()
    thread.quit()
    if thread.wait(WorkflowWorker.THREAD_JOIN_TIMEOUT_MS):
        return True
    logger.warning(
        "Workflow thread still busy after %s ms; detaching it so window "
        "destruction cannot kill a running QThread.",
        WorkflowWorker.THREAD_JOIN_TIMEOUT_MS,
    )
    thread.setParent(None)
    _detached_runs.append((thread, worker))
    register_detached_run_exit_hook()
    return False


# Detached, still-running runs are kept here so no caller can leave a busy
# QThread unowned: PySide6 destroys it while running at interpreter exit and
# the process fails with -1073740791 (see the B6 test).
_detached_runs: list[tuple[QThread, QObject | None]] = []

#: Extra, generous join window granted to detached threads at exit.
DETACHED_RUN_EXIT_GRACE_MS = 30_000

_EXIT_HOOK_REGISTERED = False


def register_detached_run_exit_hook() -> None:
    """Register (once) the interpreter-exit hook that out-waits detached runs."""
    global _EXIT_HOOK_REGISTERED
    if _EXIT_HOOK_REGISTERED:
        return
    _EXIT_HOOK_REGISTERED = True
    atexit.register(_wait_out_detached_runs)


def _wait_out_detached_runs() -> None:
    """At exit, join every detached still-running thread with a generous bound.

    Runs before Python and PySide6 teardown, so a thread that finishes here
    is destroyed cleanly afterwards. A thread that is still running after
    DETACHED_RUN_EXIT_GRACE_MS keeps piping through teardown: destroying a
    running QThread aborts the process, so we log and leave it alone.
    """
    for index, (thread, _worker) in enumerate(_detached_runs):
        try:
            if thread is not None and thread.isRunning():
                joined = thread.wait(DETACHED_RUN_EXIT_GRACE_MS)
                if joined:
                    logger.info(
                        "Detached workflow thread joined after an extra %s ms.",
                        DETACHED_RUN_EXIT_GRACE_MS,
                    )
                else:
                    logger.warning(
                        "Detached workflow thread was still running after an "
                        "extra %s ms; the process may report a fault while "
                        "shutting down.",
                        DETACHED_RUN_EXIT_GRACE_MS,
                    )
        except RuntimeError as error:
            # The wrapper was already destroyed elsewhere; nothing to do.
            logger.debug("Detached thread record already gone at exit: %s", error)
        # After the grace join the thread is finished (destroyable) or was
        # still running and got the warning above; the record itself is no
        # longer needed.
        _detached_runs[index] = (None, None)
    _detached_runs.clear()


class WorkflowWorker(QObject):
    """Run one workflow off the Qt GUI thread with cooperative cancellation."""

    #: Upper bound for joining a running worker thread on window close.
    THREAD_JOIN_TIMEOUT_MS = 5000

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    #: One typed ui.run_events contract event per engine observation, emitted
    #: from the worker thread; connections must be queued (cross-thread).
    run_event = Signal(object)

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
        self._event_stream: RunEventSource | None = None

    def cancel(self) -> None:
        """Request cancellation before the next engine step starts."""
        self._cancel_requested.set()

    @Slot()
    def run(self) -> None:
        """Execute the controller operation and publish its outcome."""
        events = RunEventStream(self._workflow)
        self._event_stream = events
        self._emit_run_events(events.start())

        def on_step_result(step_result: object) -> None:
            self._emit_run_events(events.observe_step(step_result))  # type: ignore[arg-type]
            self.progress.emit(step_result)

        try:
            if self._replay:
                result = self._service.run_replay(
                    self._workflow,
                    allowed_root=self._allowed_root,
                    cancel_check=self._cancel_requested.is_set,
                    progress_callback=on_step_result,  # type: ignore[arg-type]
                )
            else:
                result = self._service.run_workflow(
                    self._workflow,
                    cancel_check=self._cancel_requested.is_set,
                    progress_callback=on_step_result,  # type: ignore[arg-type]
                )
        except (OnceError, OSError, sqlite3.Error) as error:
            self._emit_run_events(events.observe_failure(str(error)))
            self.failed.emit(str(error))
        else:
            self._emit_run_events(events.observe_run(result))
            self.finished.emit(result)

    def _emit_run_events(self, events: tuple[RunEvent, ...]) -> None:
        for event in events:
            self.run_event.emit(event)


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
