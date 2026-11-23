"""Synthetic app-data folders for UI audits.

Every audit and every visual check builds its own folder under the system temp
directory. The real ``%LOCALAPPDATA%/Once`` folder is never read or written by
this module, by ``scripts/build_ui_fixtures.py`` or by the audit script.

The folder holds exactly what the pages render from:

- thirteen saved automations with deliberately long and short names;
- two files that cannot be read as automations (one broken JSON, one that the
  launch-target validator rejects with a plain reason);
- history with one succeeded run, one failed run, and one run still marked
  RUNNING so a row can be shown while a run waits for approval.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

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

#: Names that stress the row layout: very long, very short, non-ASCII.
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

#: Two files the page must surface instead of silently dropping.
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


def _report_step(index: int, name: str, message: str) -> WorkflowStep:
    return WorkflowStep(
        step_id=f"s{index}",
        name=name,
        kind=StepKind.REPORT,
        message=message,
    )


def _workflow(index: int, name: str) -> Workflow:
    """One saved automation with two to four honest REPORT steps."""
    step_count = 2 + (index % 3)
    steps = tuple(
        _report_step(position, f"Step {position}", f"Reported {name}.")
        for position in range(1, step_count + 1)
    )
    return Workflow(workflow_id=f"fixture-{index:02d}", name=name, steps=steps)


def build_ui_fixtures(root: Path) -> Path:
    """Create a complete synthetic app-data folder and return its path."""
    root = Path(root)
    workflows = root / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (root / "recordings").mkdir(parents=True, exist_ok=True)

    for index, name in enumerate(AUTOMATION_NAMES, start=1):
        save_workflow(_workflow(index, name), workflows / f"fixture-{index:02d}.json")

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
