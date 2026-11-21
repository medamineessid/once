"""Capture the Activity page with real runs, in a throwaway data folder.

Usage: python scripts/shot_activity_runs.py <output.png>

Seeds one saved automation, one run that succeeded, and one that failed on a
missing file, then grabs the real window. Nothing outside the temporary data
folder is read or written.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.shell import MainWindow, ShellPages


def seed(service: WorkflowService, folder: Path) -> None:
    """Save one automation and run it twice: once well, once into a failure."""
    workflow = Workflow(
        "notepad-note",
        "Write a note in Notepad",
        (
            WorkflowStep(
                "open",
                "Note the task",
                StepKind.REPORT,
                "Open Notepad, type once test, close it.",
            ),
            WorkflowStep(
                "check",
                "Confirm the note exists",
                StepKind.VERIFY_PATH_EXISTS,
                "Confirm the note was saved.",
                str(folder / "note.txt"),
            ),
        ),
    )
    service.save(workflow)
    (folder / "note.txt").write_text("once test\n", encoding="utf-8")
    service.run_workflow(workflow, allowed_root=folder)
    (folder / "note.txt").unlink()
    service.run_workflow(workflow, allowed_root=folder)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: shot_activity_runs.py <output.png>")
        return 2
    out = Path(sys.argv[1])
    data = Path(tempfile.mkdtemp(prefix="once-shot-activity-"))
    folder = data / "notes"
    folder.mkdir()
    app = QApplication.instance() or QApplication([])
    service = WorkflowService.for_app_data(data)
    seed(service, folder)
    window = MainWindow(service=service)
    window.resize(1280, 820)
    window.show()
    window._show_page(ShellPages.ACTIVITY)
    window.activity_page._history_list.setCurrentRow(0)
    QTest.qWait(700)
    pixmap = window.screen().grabWindow(int(window.winId()))
    out.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(out), "PNG"):
        print(f"could not save {out}")
        return 1
    print(f"{out}: {pixmap.width()}x{pixmap.height()}")
    window.close()
    service.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
