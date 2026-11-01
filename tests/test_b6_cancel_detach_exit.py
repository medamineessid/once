"""B6: the detach path in ``ui.workers.cancel_and_join`` cannot crash at exit.

A worker that never honors the cancel flag keeps running past the bounded
join. The caller then drops its references (mimicking
``MyAutomationsPage.shutdown_worker``), so the still-running ``QThread`` is
finally destroyed while Python shuts down. This test runs that exact
sequence in a fresh subprocess and asserts the process exits cleanly
(exit code 0, no fault) within a timeout.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from engine.workflow import StepKind, Workflow, WorkflowStep

REPO_ROOT = Path(__file__).resolve().parents[1]

CHILD_TIMEOUT_SECONDS = 40

_CHILD_SCRIPT = r'''
import os
import sys
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.fspath("@REPO_ROOT@"))

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QWidget

from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.workers import WorkflowWorker, cancel_and_join


def stubborn_run(workflow, cancel_check=None, progress_callback=None):
    """Behave like a controller operation that ignores cancellation."""
    deadline = time.perf_counter() + 7.0
    while time.perf_counter() < deadline:
        time.sleep(0.05)
    return SimpleNamespace(
        status=SimpleNamespace(value="SUCCEEDED"),
        results=(),
    )


stub_service = SimpleNamespace(run_workflow=stubborn_run)
stub_workflow = Workflow(
    workflow_id="b6-stubborn",
    name="Stubborn automation",
    steps=(
        WorkflowStep(step_id="s1", name="Sleep", kind=StepKind.REPORT, message="..."),
    ),
)

app = QApplication([])
widget = QWidget()  # stand-in for the page that owns the thread in production

thread = QThread(widget)
worker = WorkflowWorker(stub_service, stub_workflow)
worker.moveToThread(thread)
thread.started.connect(worker.run)
thread.start()

# The bounded join: worker ignores cancel, so this must detach (return False).
detached = not cancel_and_join(thread, worker)
print(f"DETACH={detached}", flush=True)

# Same reference-dropping as MyAutomationsPage.shutdown_worker.
worker = None
thread = None
app.processEvents()

# Model the window already closed: the widget dies too, then the process
# exits through normal interpreter shutdown while the worker still sleeps.
widget.deleteLater()
app.processEvents()
sys.exit(0)
'''


def test_detached_worker_ignoring_cancel_exits_cleanly(tmp_path: Path) -> None:
    script = tmp_path / "b6_stubborn_worker_exit.py"
    script.write_text(
        _CHILD_SCRIPT.replace("@REPO_ROOT@", REPO_ROOT.as_posix()), encoding="utf-8"
    )

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CHILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise AssertionError(
            "The child process hung during exit while a detached worker was "
            f"still running.\nstdout: {error.stdout!r}\nstderr: {error.stderr!r}"
        ) from None

    assert "DETACH=True" in completed.stdout, (
        "The child must exercise the detach path (cancel_and_join returned "
        f"False). stdout: {completed.stdout!r} stderr: {completed.stderr!r}"
    )
    assert completed.returncode == 0, (
        "The child process did not exit cleanly; the detach path crashed at "
        f"exit (return code {completed.returncode}).\n"
        f"stdout: {completed.stdout!r}\nstderr: {completed.stderr!r}"
    )


def test_cancel_and_join_returns_true_when_thread_finishes_in_bound() -> None:
    """Control: a cooperative worker finishes inside the bound (no detach)."""
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication, QWidget
    from ui.workers import WorkflowWorker, cancel_and_join

    app = QApplication.instance() or QApplication([])

    quick_service = SimpleNamespace(
        run_workflow=lambda *args, **kwargs: SimpleNamespace(
            status=SimpleNamespace(value="SUCCEEDED"), results=()
        )
    )
    stub_workflow = Workflow(
        workflow_id="b6-quick",
        name="Quick automation",
        steps=(
            WorkflowStep(step_id="s1", name="Note", kind=StepKind.REPORT, message="..."),
        ),
    )

    widget = QWidget()
    thread = QThread(widget)
    worker = WorkflowWorker(quick_service, stub_workflow)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    thread.start()

    joined = cancel_and_join(thread, worker)
    assert joined is True, "A cooperative worker must join inside the bound"
