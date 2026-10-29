"""My automations page wiring tests (UI migration slice 3)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from engine.errors import OnceError, WorkflowValidationError
from engine.replay import ReplayPreview
from engine.workflow import StepKind, Workflow, WorkflowRun, WorkflowStatus, WorkflowStep
from ui.pages.my_automations import MyAutomationsPage


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def make_workflow(workflow_id: str, name: str) -> Workflow:
    return Workflow(
        workflow_id=workflow_id,
        name=name,
        steps=(
            WorkflowStep(
                step_id="inspect",
                name="Inspect workflow",
                kind=StepKind.REPORT,
                message=f"{workflow_id} definition accepted.",
            ),
        ),
    )


def make_run(workflow: Workflow) -> WorkflowRun:
    now = datetime.now(UTC)
    return WorkflowRun(
        run_id="run-1",
        workflow_id=workflow.workflow_id,
        status=WorkflowStatus.SUCCEEDED,
        results=(),
        started_at=now,
        finished_at=now,
    )


class FakeService:
    """Record-keeping stand-in for WorkflowService in page tests only."""

    def __init__(self, workflows: dict[Path, Workflow]):
        self.workflows = dict(workflows)
        self.call_log: list[tuple[str, object]] = []
        self.release = Event()  # set to unblock a started run_workflow
        self.run_error: OnceError | None = None
        self.non_executable_workflows: set[str] = set()
        self.load_error: WorkflowValidationError | None = None
        self._first_run_started = Event()
        # Real WorkflowService interface: the shell's Settings page reads the
        # authorized root through the service, so the fake mirrors it.
        self._allowed_root: Path | None = None

    @property
    def allowed_root(self) -> Path | None:
        return self._allowed_root

    def set_allowed_root(self, root: Path | None) -> None:
        self._allowed_root = root

    def list_saved(self) -> tuple[Path, ...]:
        self.call_log.append(("list_saved", None))
        return tuple(sorted(self.workflows, key=lambda item: item.name.casefold()))

    def load(self, path: Path) -> Workflow:
        self.call_log.append(("load", path))
        if self.load_error is not None:
            raise self.load_error
        return self.workflows[path]

    def preview_replay(self, workflow: Workflow) -> ReplayPreview:
        self.call_log.append(("preview", workflow))
        return ReplayPreview(
            workflow_id=workflow.workflow_id,
            steps=(f"Preview of {workflow.workflow_id}",),
            executable=workflow.workflow_id not in self.non_executable_workflows,
        )

    def run_workflow(self, workflow, allowed_root=None, cancel_check=None, progress_callback=None):
        self.call_log.append(("run", workflow))
        self._first_run_started.set()
        if self.run_error is not None:
            raise self.run_error
        if not self.release.wait(2.0):  # bounded block controlled by the test
            raise OnceError("Automated test deadlock guard: run was never released.")
        return make_run(workflow)

    @property
    def first_run_started(self) -> Event:
        return self._first_run_started

    def history(self) -> tuple[WorkflowRun, ...]:
        return ()

    def run_calls(self) -> list[Workflow]:
        return [workflow for kind, workflow in self.call_log if kind == "run"]

    def preview_calls(self) -> list[Workflow]:
        return [workflow for kind, workflow in self.call_log if kind == "preview"]


def two_saved_workflows() -> dict[Path, Workflow]:
    alpha = make_workflow("alpha-workflow", "Alpha workflow")
    beta = make_workflow("beta-workflow", "Beta workflow")
    return {Path("alpha-workflow.json"): alpha, Path("beta-workflow.json"): beta}


def make_page(qtbot, service: FakeService) -> MyAutomationsPage:
    page = MyAutomationsPage()
    qtbot.addWidget(page)
    page.set_service(service)
    page.show()
    return page


def confirm_no(monkeypatch) -> list[tuple[str, str]]:
    seen = []

    def fake_question(parent, title, text, buttons=None, default=None):
        seen.append((title, text))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
    return seen


def confirm_yes(monkeypatch) -> list[tuple[str, str]]:
    seen = []

    def fake_question(parent, title, text, buttons=None, default=None):
        seen.append((title, text))
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
    return seen


def test_page_lists_saved_automations(qtbot):
    service = FakeService(two_saved_workflows())
    page = make_page(qtbot, service)

    assert page._workflow_list.count() == 2
    assert page._workflow_list.item(0).text() == "alpha-workflow.json"
    assert page._workflow_list.item(1).text() == "beta-workflow.json"
    assert page._workflow_list.item(0).data(Qt.UserRole) == Path("alpha-workflow.json")


def test_empty_state_shows_placeholder(qtbot):
    service = FakeService({})
    page = make_page(qtbot, service)

    assert page._workflow_list.count() == 0
    assert "No saved automations" in page._details_label.text()


def test_refresh_picks_up_newly_saved_automation(qtbot):
    service = FakeService({})
    page = make_page(qtbot, service)
    assert page._workflow_list.count() == 0

    service.workflows[Path("beta-workflow.json")] = make_workflow("beta-workflow", "Beta workflow")
    page.refresh()

    assert page._workflow_list.count() == 1
    assert page._workflow_list.item(0).text() == "beta-workflow.json"


def test_details_match_selected_automation(qtbot):
    service = FakeService(two_saved_workflows())
    page = make_page(qtbot, service)

    page._workflow_list.setCurrentRow(0)
    first_details = page._details_label.text()
    assert "alpha-workflow" in first_details
    assert "REPORT" in first_details
    assert "alpha-workflow definition accepted." in first_details

    page._workflow_list.setCurrentRow(1)
    second_details = page._details_label.text()
    assert second_details != first_details
    assert "beta-workflow" in second_details
    assert "alpha-workflow definition accepted." not in second_details


def test_open_uses_saved_path_and_shows_read_only_steps(qtbot):
    service = FakeService(two_saved_workflows())
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(1)
    emitted: list[Path] = []
    page.opened_workflow.connect(lambda path: emitted.append(path))

    page._open_selected()

    assert service.run_calls() == []
    assert service.preview_calls() == []
    assert ("load", Path("beta-workflow.json")) in service.call_log
    assert emitted == [Path("beta-workflow.json")]


def test_preview_shows_steps_and_never_calls_run(qtbot):
    service = FakeService(two_saved_workflows())
    service.non_executable_workflows = {"beta-workflow"}
    page = make_page(qtbot, service)

    page._workflow_list.setCurrentRow(0)
    page._preview_selected()
    details = page._details_label.text()
    assert "Preview of alpha-workflow" in details
    assert "Status: this replay can be executed." in details
    assert "cannot" not in details

    page._workflow_list.setCurrentRow(1)
    page._preview_selected()
    details = page._details_label.text()
    assert "Preview of beta-workflow" in details
    assert "unsupported" in details
    assert "cannot be executed" in details

    assert service.run_calls() == []
    assert len(service.preview_calls()) == 2


def test_run_without_confirmation_calls_nothing(qtbot, monkeypatch):
    service = FakeService(two_saved_workflows())
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)
    seen = confirm_no(monkeypatch)

    page._run_selected()

    assert len(seen) == 1
    assert service.run_calls() == []
    assert page._run_button.isEnabled() is True


def test_selection_load_error_shows_inline_no_modal(qtbot, monkeypatch):
    service = FakeService(two_saved_workflows())
    service.load_error = WorkflowValidationError("File is not a valid workflow.")
    page = make_page(qtbot, service)
    popped: list[bool] = []

    def fake_warning(parent, title, text, buttons=None, default=None):
        popped.append(True)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_warning))

    page._workflow_list.setCurrentRow(0)

    assert popped == []
    assert "File is not a valid workflow." in page._details_label.text()


def test_load_error_is_surfaced_and_runs_nothing(qtbot, monkeypatch):
    service = FakeService(two_saved_workflows())
    service.load_error = WorkflowValidationError("File is not a valid workflow.")
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)
    confirm_yes(monkeypatch)
    warnings: list[tuple[str, str]] = []

    def fake_warning(parent, title, text):
        warnings.append((title, text))

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_warning))

    page._run_selected()

    assert warnings == [("Workflow error", "File is not a valid workflow.")]
    assert service.run_calls() == []
    assert page._run_button.isEnabled() is True


def test_run_with_confirmation_calls_run_once_with_loaded_workflow(qtbot, monkeypatch):
    service = FakeService(two_saved_workflows())
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)
    confirm_yes(monkeypatch)
    assert page._run_button.isEnabled() is True

    page._run_selected()
    assert page._run_button.isEnabled() is False
    service.release.set()
    qtbot.waitUntil(lambda: page._worker is None, timeout=5000)

    assert page._run_button.isEnabled() is True
    assert service.run_calls() == [service.workflows[Path("alpha-workflow.json")]]


def test_run_button_stays_disabled_until_run_finishes(qtbot, monkeypatch):
    service = FakeService(two_saved_workflows())
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)
    confirm_yes(monkeypatch)

    page._run_selected()
    assert page._preview_button.isEnabled() is False
    assert page._open_button.isEnabled() is False
    service.release.set()
    qtbot.waitUntil(lambda: page._worker is None, timeout=5000)
    assert page._preview_button.isEnabled() is True
    assert page._open_button.isEnabled() is True


def test_failing_run_shows_error(qtbot, monkeypatch):
    service = FakeService(two_saved_workflows())
    service.run_error = OnceError("Controlled failure injection from the test.")
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)
    confirm_yes(monkeypatch)
    warnings: list[tuple[str, str]] = []

    def fake_warning(parent, title, text):
        warnings.append((title, text))

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_warning))

    page._run_selected()
    service.release.set()
    qtbot.waitUntil(lambda: page._worker is None, timeout=5000)

    assert "Controlled failure injection from the test." in page._details_label.text()
    assert warnings == [("Workflow error", "Controlled failure injection from the test.")]
    assert page._run_button.isEnabled() is True


def test_run_shows_finished_run_status(qtbot, monkeypatch):

    # A service whose run completes immediately exercises climb-down code paths.
    service = FakeService(two_saved_workflows())
    service.release.set()
    page = make_page(qtbot, service)
    page._workflow_list.setCurrentRow(0)
    confirm_yes(monkeypatch)

    page._run_selected()
    qtbot.waitUntil(lambda: page._worker is None, timeout=5000)

    assert "SUCCEEDED" in page._details_label.text()


def test_shell_injects_service_into_page(qtbot):
    from ui.shell import MainWindow

    window = MainWindow(service=FakeService({}))
    qtbot.addWidget(window)

    assert window.my_automations_page._service is window._service
