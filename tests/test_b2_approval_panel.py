"""B2: the desktop approval panel is the one approval surface for desktop runs.

An automation that mutates the desktop can only start a run through this
panel: it lists exactly the mutating steps (engine/desktop.py's
mutating_kind_names + requires_desktop_approval), Approve works only while
the list is shown, and Approve calls the existing gate
approve_desktop_workflow. Read-only automations show no panel and run
without approval. Everything below runs with fake providers; no real
desktop, browser, or Chrome is touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from controller.service import WorkflowService
from engine.desktop import DesktopApproval, mutating_kind_names
from engine.workflow import (
    StepKind,
    Workflow,
    WorkflowStep,
)
from storage.database import connect
from storage.history import ExecutionHistory
from tests.test_desktop_engine import FakeDesktopActions
from ui.components.approval_panel import DesktopApprovalPanel
from ui.pages.my_automations import MyAutomationsPage
from ui.strings import (
    DESKTOP_APPROVAL_KIND_CLICK_UI_ELEMENT,
    DESKTOP_APPROVAL_KIND_TYPE_TEXT,
    DESKTOP_APPROVAL_STEP_TEMPLATE,
)

WINDOW = {"title": "Once demo", "class_name": "DemoWindowClass"}
TYPE_TARGET = {
    "window": WINDOW,
    "element": {"class_name": "DemoEditClass", "control_type": "Edit"},
    "text": "hello once",
}
CLICK_TARGET = {
    "window": WINDOW,
    "element": {"class_name": "DemoButtonClass", "control_type": "Button"},
}


class FakeBrowserProvider:
    """Only what the service needs: a shutdown the service can call."""

    def __init__(self) -> None:
        self.shutdown_calls = 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def typing_workflow() -> Workflow:
    return Workflow(
        "typing-flow",
        "Typing flow",
        (
            WorkflowStep(
                "type",
                "Type into demo",
                StepKind.TYPE_TEXT,
                "Text entered.",
                target=json.dumps(TYPE_TARGET),
            ),
        ),
    )


def mixed_mutating_workflow() -> Workflow:
    """Two mutating kinds, approvable through the real desktop policy."""
    return Workflow(
        "mixed-flow",
        "Mixed flow",
        (
            WorkflowStep(
                "type",
                "Type into demo",
                StepKind.TYPE_TEXT,
                "Text entered.",
                target=json.dumps(TYPE_TARGET),
            ),
            WorkflowStep(
                "click",
                "Click demo button",
                StepKind.CLICK_UI_ELEMENT,
                "The button was clicked.",
                target=json.dumps(CLICK_TARGET),
            ),
        ),
    )


def unapprovable_mix_workflow() -> Workflow:
    """A REPORT step mixed in: the desktop gate refuses it with a real error."""
    return Workflow(
        "report-mix-flow",
        "Report mix flow",
        (
            WorkflowStep(
                "report",
                "Report step",
                StepKind.REPORT,
                "Nothing on the desktop changes here.",
            ),
            WorkflowStep(
                "type",
                "Type into demo",
                StepKind.TYPE_TEXT,
                "Text entered.",
                target=json.dumps(TYPE_TARGET),
            ),
        ),
    )


def read_only_workflow() -> Workflow:
    return Workflow(
        "read-only-flow",
        "Read only flow",
        (
            WorkflowStep(
                "report",
                "Report step",
                StepKind.REPORT,
                "Definition accepted.",
            ),
        ),
    )


def listed_texts(panel: DesktopApprovalPanel) -> list[str]:
    return [panel._step_list.item(index).text() for index in range(panel._step_list.count())]


def click_run(page: MyAutomationsPage) -> None:
    """The Run control is an inline confirm: click to arm, click to confirm."""
    QTest.mouseClick(page._run_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(page._run_button, Qt.MouseButton.LeftButton)


def make_desktop_service(tmp_path) -> tuple[WorkflowService, FakeDesktopActions]:
    """A real controller service around fake providers — never a real desktop."""
    desktop = FakeDesktopActions()
    browser = FakeBrowserProvider()
    service = WorkflowService(
        history=ExecutionHistory(connect(tmp_path / "history.db")),
        workflow_directory=tmp_path / "workflows",
        desktop_actions=desktop,
        browser_actions=browser,
        window_inspector=lambda target_json: ("title=demo",),
        ui_element_inspector=lambda target_json: ("automation_id=x",),
    )
    return service, desktop


def make_page(qtbot, service: WorkflowService) -> MyAutomationsPage:
    page = MyAutomationsPage()
    qtbot.addWidget(page)
    page.set_service(service)
    page.show()
    return page


def show_panel(qtbot, workflow: Workflow) -> DesktopApprovalPanel:
    """A panel exactly as the page presents one: shown by show_for only."""
    panel = DesktopApprovalPanel()
    qtbot.addWidget(panel)
    panel.show_for(workflow)
    panel.show()
    return panel


# ------------- widget: the panel alone --------------------------------------


def test_panel_is_hidden_until_a_mutating_automation_is_shown(qtbot) -> None:
    panel = DesktopApprovalPanel()
    qtbot.addWidget(panel)

    assert panel.isVisible() is False
    assert panel._approve_button.isEnabled() is False
    assert panel.show_for(read_only_workflow()) is False
    assert panel.isVisible() is False
    assert panel._approve_button.isEnabled() is False

    shown = panel.show_for(mixed_mutating_workflow())

    assert shown is True
    assert panel.isVisible() is True
    assert panel._approve_button.isEnabled() is True


def test_read_only_automation_gets_no_panel_and_no_rows(qtbot) -> None:
    """A read-only automation must run without approval: panel stays hidden."""
    panel = DesktopApprovalPanel()
    qtbot.addWidget(panel)

    shown = panel.show_for(read_only_workflow())

    assert shown is False
    assert panel.isVisible() is False
    assert panel._step_list.count() == 0
    assert panel._approve_button.isEnabled() is False
    assert panel.listed_kind_names() == ()


def test_panel_lists_exactly_the_mutating_steps_in_order(qtbot) -> None:
    panel = DesktopApprovalPanel()
    qtbot.addWidget(panel)
    workflow = mixed_mutating_workflow()

    panel.show_for(workflow)

    assert panel.listed_kind_names() == mutating_kind_names(workflow)
    assert panel.listed_kind_names() == ("TYPE_TEXT", "CLICK_UI_ELEMENT")
    assert listed_texts(panel) == [
        DESKTOP_APPROVAL_STEP_TEMPLATE.format(
            action=DESKTOP_APPROVAL_KIND_TYPE_TEXT, step_name="Type into demo"
        ),
        DESKTOP_APPROVAL_STEP_TEMPLATE.format(
            action=DESKTOP_APPROVAL_KIND_CLICK_UI_ELEMENT, step_name="Click demo button"
        ),
    ]


def test_approve_click_emits_a_real_gate_approval_bound_to_the_listed_steps(qtbot) -> None:
    panel = show_panel(qtbot, mixed_mutating_workflow())
    listed_kinds = panel.listed_kind_names()
    bound_workflow = panel._workflow  # the exact automation the list showed
    got: list[object] = []
    panel.approved.connect(got.append)

    QTest.mouseClick(panel._approve_button, Qt.MouseButton.LeftButton)

    assert len(got) == 1
    approval = got[0]
    assert isinstance(approval, DesktopApproval)
    assert approval.approved_at is not None
    # The approval is bound to exactly the workflow the list showed: the same
    # steps, no more, no less.
    assert approval.workflow is bound_workflow
    assert mutating_kind_names(approval.workflow) == listed_kinds
    assert mutating_kind_names(approval.workflow) == ("TYPE_TEXT", "CLICK_UI_ELEMENT")
    assert panel.isVisible() is False


def test_gate_refusal_stays_inline_and_emits_nothing(qtbot) -> None:
    """The gate can refuse a mix the desktop policy cannot run; the panel
    shows that reason inline, in plain language, and emits nothing."""
    panel = show_panel(qtbot, unapprovable_mix_workflow())
    approved: list[object] = []
    panel.approved.connect(approved.append)

    QTest.mouseClick(panel._approve_button, Qt.MouseButton.LeftButton)

    assert approved == []
    assert panel._rejection_label.isVisible()
    assert "cannot be approved" in panel._rejection_label.text()
    assert "REPORT" in panel._rejection_label.text()


def test_cancel_click_emits_cancelled_without_approval(qtbot) -> None:
    panel = show_panel(qtbot, mixed_mutating_workflow())
    approved: list[object] = []
    cancelled: list[bool] = []
    panel.approved.connect(approved.append)
    panel.cancelled.connect(lambda: cancelled.append(True))

    QTest.mouseClick(panel._cancel_button, Qt.MouseButton.LeftButton)

    assert cancelled == [True]
    assert approved == []
    assert panel.isVisible() is False
    assert panel._approve_button.isEnabled() is False


def test_approve_is_inert_before_any_automation_is_shown(qtbot) -> None:
    """Guard: a fresh panel may not produce an approval from stray clicks."""
    panel = DesktopApprovalPanel()
    qtbot.addWidget(panel)
    approved: list[object] = []
    panel.approved.connect(approved.append)

    QTest.mouseClick(panel._approve_button, Qt.MouseButton.LeftButton)

    assert approved == []


# ------------- page: wiring into the My automations run flow -----------------


def test_unapproved_mutating_automation_cannot_run(qtbot, tmp_path) -> None:
    service, desktop = make_desktop_service(tmp_path)
    service.save(typing_workflow())
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)

    click_run(page)

    assert page._approval_panel.isVisibleTo(page) is True
    assert page._thread is None
    assert desktop.calls == []
    assert tuple(service.history()) == ()


def test_approved_mutating_automation_can_run_through_the_gate_and_policy(qtbot, tmp_path) -> None:
    service, desktop = make_desktop_service(tmp_path)
    service.save(mixed_mutating_workflow())
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)

    click_run(page)
    qtbot.waitUntil(lambda: page._approval_panel.isVisibleTo(page), timeout=5000)
    QTest.mouseClick(page._approval_panel._approve_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page._worker is None, timeout=10000)

    assert [kind for kind, _target in desktop.calls] == ["TYPE_TEXT", "CLICK_UI_ELEMENT"]
    runs = tuple(service.history())
    assert len(runs) == 1
    assert runs[0].status.value == "SUCCEEDED"
    assert page._approval_panel.isVisibleTo(page) is False
    assert "Run Succeeded" in page._details_label.text()


def test_cancelling_the_panel_runs_nothing(qtbot, tmp_path) -> None:
    service, desktop = make_desktop_service(tmp_path)
    service.save(typing_workflow())
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)

    click_run(page)
    qtbot.waitUntil(lambda: page._approval_panel.isVisibleTo(page), timeout=5000)
    QTest.mouseClick(page._approval_panel._cancel_button, Qt.MouseButton.LeftButton)

    assert page._approval_panel.isVisibleTo(page) is False
    assert page._thread is None
    assert desktop.calls == []
    assert tuple(service.history()) == ()
    # The page is usable again: a new run can be requested after a decline.
    assert page._run_button.isEnabled() is True


def test_selection_change_hides_a_waiting_panel_and_stops_its_approval(qtbot, tmp_path) -> None:
    """A panel is approval for one automation; switching rows must discard it."""
    service, desktop = make_desktop_service(tmp_path)
    service.save(read_only_workflow())
    service.save(typing_workflow())
    page = make_page(qtbot, service)
    # The redesigned list keeps filenames as row data only: the visible title
    # lives in the AutomationRow widget (item.setText("")), so identify the
    # row through its widget title and the stored path, not item text.
    row = page._workflow_list.itemWidget(page._workflow_list.item(1))
    assert row is not None
    assert row._name_label.text() == "Typing flow"
    assert Path(page._workflow_list.item(1).data(Qt.UserRole)).name == "typing-flow.json"
    page._workflow_list.setCurrentRow(1)

    click_run(page)
    qtbot.waitUntil(lambda: page._approval_panel.isVisibleTo(page), timeout=5000)
    page._workflow_list.setCurrentRow(0)

    assert page._approval_panel.isVisibleTo(page) is False
    assert page._approval_panel._approve_button.isEnabled() is False
    assert page._thread is None
    assert desktop.calls == []
    assert tuple(service.history()) == ()


def test_read_only_automation_runs_without_the_panel(qtbot, tmp_path) -> None:
    service, desktop = make_desktop_service(tmp_path)
    service.save(read_only_workflow())
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)

    click_run(page)
    qtbot.waitUntil(lambda: page._worker is None, timeout=10000)

    assert page._approval_panel.isVisibleTo(page) is False
    assert desktop.calls == []
    runs = tuple(service.history())
    assert len(runs) == 1
    # A single report step observed; it did not perform anything.
    assert runs[0].status.value == "OBSERVATION_ONLY"
