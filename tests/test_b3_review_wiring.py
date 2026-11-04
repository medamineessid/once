"""B3: review page wiring through the ONE existing approval path.

The approval path is the ai.approval gate accessed by the controller
(`preview_proposal` -> `approve_proposal` -> `service.save_approved`).
These tests click the visible Approve control and assert its real effect
(a persisted workflow), never a second approval path.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from ai.models import ProviderDraft
from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.components.banner import SEVERITY_ERROR, SEVERITY_SUCCESS
from ui.pages.review import ReviewPage


def make_service(tmp_path: Path) -> WorkflowService:
    return WorkflowService.for_app_data(tmp_path / "appdata")


def sample_draft(workflow_id: str = "review-demo") -> ProviderDraft:
    workflow = Workflow(
        workflow_id=workflow_id,
        name="Tidy the notes",
        steps=(
            WorkflowStep(step_id="s1", name="Say hello", kind=StepKind.REPORT, message="Hello."),
            WorkflowStep(step_id="s2", name="Report done", kind=StepKind.REPORT, message="Done."),
        ),
    )
    return ProviderDraft(goal="Run a small demo", workflow=workflow)


def invalid_draft() -> ProviderDraft:
    workflow = Workflow(workflow_id="broken", name="", steps=())
    return ProviderDraft(goal="Broken draft", workflow=workflow)


def test_load_proposal_lists_preview_steps_and_goal(qtbot, tmp_path) -> None:
    page = ReviewPage()
    qtbot.addWidget(page)
    page.set_service(make_service(tmp_path))

    page.load_proposal(sample_draft())

    goal_text = page._goal_label.text()
    assert goal_text == "Goal: Run a small demo"
    steps = [page._steps_list.item(index).text() for index in range(page._steps_list.count())]
    assert len(steps) == 2
    assert all("source=AI inference" in line for line in steps)
    assert any("expected=Hello." in line for line in steps)


def test_approve_visible_only_with_service_and_previewed_proposal(qtbot, tmp_path) -> None:
    page = ReviewPage()
    qtbot.addWidget(page)
    page.show()
    service = make_service(tmp_path)

    # Default page: nothing loaded and nothing reviewable.
    assert page._approve_button.isHidden()
    assert page._edit_button.isHidden()

    # A proposal without a service cannot be saved, so it stays hidden.
    page.load_proposal(sample_draft())
    assert page._approve_button.isHidden()

    # A service without a proposal has nothing to approve either.
    page.load_proposal(None)
    page.set_service(service)
    assert page._approve_button.isHidden()

    # Both present: the honest, wired control appears.
    page.load_proposal(sample_draft())
    assert page._approve_button.isVisible()


def test_clicking_approve_saves_through_the_existing_gate(qtbot, tmp_path) -> None:
    service = make_service(tmp_path)
    page = ReviewPage()
    qtbot.addWidget(page)
    page.set_service(service)
    page.load_proposal(sample_draft(workflow_id="approved-via-gate"))

    with qtbot.waitSignal(page.approved, timeout=5000):
        QTest.mouseClick(page._approve_button, Qt.MouseButton.LeftButton)

    saved_names = [path.name for path in service.list_saved()]
    assert "approved-via-gate.json" in saved_names
    loaded = service.load(tmp_path / "appdata" / "workflows" / "approved-via-gate.json")
    assert loaded.name == "Tidy the notes"
    assert page._banner.property("severity") == SEVERITY_SUCCESS


def test_clicking_approve_with_no_service_does_nothing(qtbot) -> None:
    page = ReviewPage()
    qtbot.addWidget(page)
    page.load_proposal(sample_draft())

    assert page._approve_button.isHidden()
    # The guard must hold even when the slot is called directly.
    emitted: list[int] = []
    page.approved.connect(lambda: emitted.append(1))
    page._approve()
    assert emitted == []
    assert page._approve_button.isHidden()


def test_invalid_draft_shows_error_banner_and_stays_hidden(qtbot, tmp_path) -> None:
    page = ReviewPage()
    qtbot.addWidget(page)
    page.show()
    page.set_service(make_service(tmp_path))

    page.load_proposal(invalid_draft())

    assert page._banner.isVisible()
    assert page._banner.property("severity") == SEVERITY_ERROR
    assert page._banner.body_text != ""
    assert page._approve_button.isHidden()
    items = [page._steps_list.item(index).text() for index in range(page._steps_list.count())]
    assert items == ["No step details to review."]


def test_edit_button_stays_hidden_until_it_is_wired(qtbot, tmp_path) -> None:
    """Edit has no existing approval-path effect yet: honest = hidden."""
    page = ReviewPage()
    qtbot.addWidget(page)
    page.set_service(make_service(tmp_path))
    page.load_proposal(sample_draft())

    assert page._edit_button.isHidden()


def test_load_proposal_failure_banner_can_be_dismissed(qtbot, tmp_path) -> None:
    page = ReviewPage()
    qtbot.addWidget(page)
    page.show()
    page.set_service(make_service(tmp_path))
    page.load_proposal(invalid_draft())
    assert page._banner.isVisible()

    QTest.mouseClick(page._banner._dismiss, Qt.MouseButton.LeftButton)
    assert page._banner.isHidden()
