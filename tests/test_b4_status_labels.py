"""B4: an observation-only run is labelled in plain language, never as a code.

Both surfaces read the label from `ui.components.formatting.status_display`
(`ui/pages/activity.py` rows and details, `ui/pages/home.py` recent activity),
so the wording cannot drift between pages.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStatus, WorkflowStep
from storage.database import connect
from storage.history import ExecutionHistory
from ui.components.formatting import status_display
from ui.pages.activity import ActivityPage
from ui.pages.home import HomePage

LABEL = "Observation only — nothing was performed"


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def make_service(tmp_path: Path) -> WorkflowService:
    return WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))


def demo_run_service(tmp_path: Path) -> WorkflowService:
    service = make_service(tmp_path)
    service.run_demo()
    return service


def observation_workflow() -> Workflow:
    return Workflow(
        "outcome-workflow",
        "Observation workflow",
        (WorkflowStep("report", "Report", StepKind.REPORT, "Nothing to do yet."),),
    )


def non_demo_run_service(tmp_path: Path) -> WorkflowService:
    """Home hides the diagnostic demo row from recent activity, so this test
    needs a report-only workflow that is not the demo."""
    service = make_service(tmp_path)
    service.run_workflow(observation_workflow())
    return service


def test_the_new_run_status_has_one_plain_language_label() -> None:
    assert status_display(WorkflowStatus.OBSERVATION_ONLY.value) == (LABEL, "neutral")


def test_failure_keeps_its_own_label() -> None:
    """Guard: the new label must not blur a real failure."""
    assert status_display(WorkflowStatus.FAILED.value) == ("Failed", "fail")
    assert status_display(WorkflowStatus.SUCCEEDED.value) == ("Succeeded", "ok")


def test_activity_row_shows_the_observation_label(qtbot, tmp_path) -> None:
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(demo_run_service(tmp_path))

    item = page._history_list.item(0)
    row = page._history_list.itemWidget(item)
    texts = " | ".join(label.text() for label in row.findChildren(QLabel))

    assert LABEL in texts
    assert "OBSERVATION_ONLY" not in texts


def test_activity_details_explain_the_observation_in_plain_language(qtbot, tmp_path) -> None:
    page = ActivityPage()
    qtbot.addWidget(page)
    page.set_service(demo_run_service(tmp_path))

    page._history_list.setCurrentRow(0)
    details = page._details_label.text()

    assert LABEL in details
    assert "OBSERVATION_ONLY" not in details


def test_home_recent_activity_shows_the_observation_label(qtbot, tmp_path) -> None:
    page = HomePage()
    qtbot.addWidget(page)
    page.set_service(non_demo_run_service(tmp_path))
    page.refresh()

    texts = " | ".join(label.text() for label in page._activity_rows[0].findChildren(QLabel))

    assert LABEL in texts
    assert "OBSERVATION_ONLY" not in texts
