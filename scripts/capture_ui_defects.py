"""Capture "before" app-window images of the defects in docs/UI_DEFECTS.md.

Usage:
    python scripts/capture_ui_defects.py [--out docs/ui-reference/defects]

Every image is the real Qt window (the same class ``app.py`` builds), rendered
offscreen at 960x600 and 1920x1020 from a synthetic app-data folder under the
system temp directory. The real ``%LOCALAPPDATA%/Once`` folder is never read or
written: the service is pointed at the temporary folder instead.

Four states are captured:

- Home.
- My automations with thirteen saved rows, the unreadable-files banner and the
  desktop approval panel open.
- Automation details.
- Settings.
- The delete confirmation dialog, opened over the shell.

The images are visual evidence for a person to review. No claim is made here
about what the pixels show.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

AUTOMATION_NAMES: tuple[str, ...] = (
    "Send the monthly invoice pack to every client in the north region",
    "Rename screenshots",
    "Organise downloaded invoices into supplier folders by month and year",
    "Weekly backup",
    "Collapse the quarterly expense spreadsheets into one workbook for finance",
    "Open and close File Explorer",
    "Extract totals from the supplier PDF batch and write a summary row",
    "Tidy desktop",
    "Réorganiser les fichiers du dossier partagé avec les accents conservés",
    "Print labels",
    "Collect the attendance sheets, rename them and move them into the archive",
    "Nightly log rotation",
    "Generate the accessibility report for the October release candidate build",
)

UNREADABLE_FILES: dict[str, str] = {
    "vscode-session.json": json.dumps(
        {
            "schema_version": 3,
            "workflow_id": "vscode-session",
            "name": "Vs Code Session",
            "steps": [
                {
                    "step_id": "s1",
                    "name": "Open editor",
                    "kind": "LAUNCH_APPLICATION",
                    "message": "Launched Visual Studio Code.",
                    "target": json.dumps({"application": "vscode"}),
                }
            ],
        },
        indent=2,
    )
    + "\n",
    "broken-notes.json": '{"schema_version": 4, "workflow_id": "broken-notes",\n',
}

SIZES: tuple[tuple[int, int], ...] = ((960, 600), (1920, 1020))


def build_fixtures(root: Path) -> Path:
    """Create a synthetic app-data folder and return it.

    The folder holds thirteen saved automations, two files that cannot be read,
    and three history rows (succeeded, failed, still running).
    """
    from engine.workflow import (
        StepKind,
        StepResult,
        StepStatus,
        Workflow,
        WorkflowRun,
        WorkflowStatus,
        WorkflowStep,
    )
    from storage.database import connect
    from storage.history import ExecutionHistory
    from storage.workflows import save_workflow

    workflows = root / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (root / "recordings").mkdir(parents=True, exist_ok=True)

    for index, name in enumerate(AUTOMATION_NAMES, start=1):
        step_count = 2 + (index % 3)
        steps = tuple(
            WorkflowStep(
                step_id=f"s{position}",
                name=f"Step {position}",
                kind=StepKind.REPORT,
                message=f"Reported {name}.",
            )
            for position in range(1, step_count + 1)
        )
        saved = Workflow(workflow_id=f"fixture-{index:02d}", name=name, steps=steps)
        save_workflow(saved, workflows / f"fixture-{index:02d}.json")

    for file_name, body in UNREADABLE_FILES.items():
        (workflows / file_name).write_text(body, encoding="utf-8")

    connection = connect(root / "once.db")
    history = ExecutionHistory(connection)
    base = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
    runs = (
        (
            "run-succeeded",
            "fixture-02",
            WorkflowStatus.SUCCEEDED,
            (StepResult("s1", StepStatus.SUCCEEDED, "Renamed 41 screenshots."),),
        ),
        (
            "run-failed",
            "fixture-07",
            WorkflowStatus.FAILED,
            (
                StepResult(
                    "s1",
                    StepStatus.FAILED,
                    "The identified window is ambiguous, so nothing was done.",
                ),
            ),
        ),
        (
            "run-waiting",
            "fixture-05",
            WorkflowStatus.RUNNING,
            (StepResult("s1", StepStatus.SUCCEEDED, "Waiting for approval."),),
        ),
    )
    for offset, (run_id, workflow_id, status, results) in enumerate(runs):
        started = base + timedelta(hours=offset)
        history.record(
            WorkflowRun(
                run_id,
                workflow_id,
                status,
                results,
                started,
                started + timedelta(seconds=6),
            )
        )
    history.close()
    connection.close()
    return root


def _approval_workflow():
    """A workflow with one mutating step, so the approval panel can be shown."""
    from engine.workflow import StepKind, Workflow, WorkflowStep

    return Workflow(
        workflow_id="fixture-approval",
        name="Open and close File Explorer",
        steps=(
            WorkflowStep(
                step_id="s1",
                name="Open File Explorer",
                kind=StepKind.LAUNCH_APPLICATION,
                message="Opened File Explorer.",
                target=json.dumps({"application": "explorer"}),
            ),
        ),
    )


def _settle(app: QApplication, window) -> None:
    app.processEvents()
    QTest.qWait(250)
    app.processEvents()
    window.ensurePolished()
    app.processEvents()


def _save(widget, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(path))
    return path.stat().st_size


def capture(out_dir: Path) -> list[tuple[str, int]]:
    """Render every state at every size; return (file name, bytes) pairs."""
    from controller.service import WorkflowService
    from ui.components.delete_confirm import DeleteConfirmDialog, automation_delete_message
    from ui.shell import MainWindow, ShellPages
    from ui.strings import MY_UNREADABLE_BODY, MY_UNREADABLE_TITLE

    app = QApplication.instance() or QApplication([sys.argv[0]])
    fixtures = build_fixtures(Path(tempfile.mkdtemp(prefix="once-ui-captures-")))
    service = WorkflowService.for_app_data(fixtures)
    window = MainWindow(service, None, app_data_dir=fixtures)
    saved: list[tuple[str, int]] = []
    try:
        for width, height in SIZES:
            window.resize(width, height)
            window.show()
            _settle(app, window)
            size_tag = f"{width}x{height}"

            window._show_page(ShellPages.HOME)
            window.home_page.refresh()
            _settle(app, window)
            saved.append((f"home-{size_tag}.png", _save(window, out_dir / f"home-{size_tag}.png")))

            window._show_page(ShellPages.MY_AUTOMATIONS)
            page = window.my_automations_page
            page.refresh()
            page._banner.show_message("warning", MY_UNREADABLE_TITLE, MY_UNREADABLE_BODY)
            page._approval_panel.show_for(_approval_workflow())
            _settle(app, window)
            saved.append(
                (
                    f"my-automations-{size_tag}.png",
                    _save(window, out_dir / f"my-automations-{size_tag}.png"),
                )
            )

            workflow = service.load(fixtures / "workflows" / "fixture-02.json")
            window._show_page(ShellPages.REVIEW)
            window.review_page.show_workflow(workflow)
            _settle(app, window)
            saved.append(
                (
                    f"details-{size_tag}.png",
                    _save(window, out_dir / f"details-{size_tag}.png"),
                )
            )

            window._show_page(ShellPages.SETTINGS)
            _settle(app, window)
            saved.append(
                (
                    f"settings-{size_tag}.png",
                    _save(window, out_dir / f"settings-{size_tag}.png"),
                )
            )

            dialog = DeleteConfirmDialog(
                automation_delete_message("Rename screenshots", 3),
                runs_count=3,
                parent=window,
            )
            dialog.show()
            app.processEvents()
            QTest.qWait(250)
            app.processEvents()
            saved.append(
                (
                    f"delete-dialog-{size_tag}.png",
                    _save(dialog, out_dir / f"delete-dialog-{size_tag}.png"),
                )
            )
            dialog.close()
            dialog.deleteLater()
            app.processEvents()
    finally:
        window.close()
        app.processEvents()
        service.close()
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(ROOT / "docs" / "ui-reference" / "defects"),
        help="output folder for the PNG captures",
    )
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    for name, size in capture(out_dir):
        print(f"{name}\t{size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
