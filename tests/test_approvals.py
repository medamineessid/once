"""Fakes-only tests for one-time application approval through the abstraction."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from ai.models import ProviderDraft
from controller.approvals import (
    ApplicationApprovalStore,
    ApplicationIdentity,
    DatabaseApplicationApprovalStore,
    launch_identities_from_events,
)
from controller.service import WorkflowService
from engine.workflow import StepKind, Workflow, WorkflowStep
from recorder.models import RecordedEvent, RecordedEventKind
from storage.database import connect
from storage.history import ExecutionHistory
from ui.pages.review import ReviewPage


class FakeApprovalStore:
    """A deterministic in-memory fake of the approval Protocol."""

    def __init__(self) -> None:
        self.approved: dict[tuple[str | None, str | None], ApplicationIdentity] = {}

    def is_approved(self, identity: ApplicationIdentity) -> bool:
        key = (identity.executable_sha256, identity.executable_path)
        return key in self.approved

    def approve(self, identity: ApplicationIdentity) -> None:
        key = (identity.executable_sha256, identity.executable_path)
        self.approved[key] = identity


def make_exe_service(tmp_path: Path) -> WorkflowService:
    """A paper service with only the injected approval store configured."""
    return WorkflowService(
        history=ExecutionHistory(connect(tmp_path / "history.db")),
        workflow_directory=tmp_path / "workflows",
        approval_store=DatabaseApplicationApprovalStore(tmp_path / "approvals.db"),
    )


def _window_event(
    sequence: int,
    *,
    name: str | None,
    path: str | None,
    sha: str | None,
) -> RecordedEvent:
    return RecordedEvent(
        sequence=sequence,
        timestamp_ns=1000 + sequence,
        kind=RecordedEventKind.WINDOW_OPEN,
        window_title="window",
        process_name=name,
        executable_path=path,
        executable_sha256=sha,
    )


def sample_exes_draft() -> ProviderDraft:
    """A draft that launches by recorded exe path (engine-validated)."""
    workflow = Workflow(
        workflow_id="exes-identity-demo",
        name="Open the recorded app",
        steps=(
            WorkflowStep(
                step_id="s1",
                name="Launch recorded app",
                kind=StepKind.LAUNCH_APPLICATION,
                message="Opens the application you recorded.",
                target='{"executable": "C:\\\\Apps\\\\Demo.exe"}',
            ),
            WorkflowStep(step_id="s2", name="Report", kind=StepKind.REPORT, message="Done."),
        ),
    )
    return ProviderDraft(goal="Run the recorded task", workflow=workflow)


def test_database_store_starts_unapproved_and_persists_one_approval(
    tmp_path: Path,
) -> None:
    store = DatabaseApplicationApprovalStore(tmp_path / "approvals.db")
    identity = ApplicationIdentity(
        name="Graceful.exe",
        executable_path=r"C:\Program Files\Graceful\graceful.exe",
        executable_sha256="abc123",
    )
    assert not store.is_approved(identity)

    store.approve(identity)

    assert store.is_approved(identity)
    assert not store.is_approved(
        ApplicationIdentity(executable_path=identity.executable_path, executable_sha256="other")
    )
    store.close()

    reopened = DatabaseApplicationApprovalStore(tmp_path / "approvals.db")
    assert reopened.is_approved(identity)
    reopened.close()


def test_launch_identities_merge_duplicates_and_stay_deterministic() -> None:
    events = (
        _window_event(3, name="App.exe", path=r"C:\Apps\App.exe", sha="sha-b"),
        _window_event(1, name="App.exe", path=r"C:\Apps\App.exe", sha="sha-b"),
        _window_event(2, name="Slow.exe", path=r"C:\Apps\Slow.exe", sha="sha-a"),
        _window_event(4, name="Eventless", path=None, sha=None),
    )

    identities = launch_identities_from_events(events)

    assert [identity.executable_sha256 for identity in identities] == ["sha-a", "sha-b"]
    assert {identity.name for identity in identities} == {"App.exe", "Slow.exe"}


def test_service_reports_pending_until_the_recorded_identity_is_approved(
    tmp_path: Path,
) -> None:
    store = DatabaseApplicationApprovalStore(tmp_path / "approvals.db")
    service = WorkflowService(
        history=ExecutionHistory(connect(tmp_path / "history.db")),
        approval_store=store,
    )
    events = (_window_event(1, name="Notepad.exe", path=r"C:\Windows\notepad.exe", sha="hash1"),)

    pending = service.unapproved_application_identities(events)
    assert [identity.display_name for identity in pending] == ["Notepad"]
    assert not service.is_application_approved(pending[0])

    service.approve_application(pending[0])

    assert service.unapproved_application_identities(events) == ()
    assert service.is_application_approved(pending[0])


def test_service_without_an_approval_store_stays_transparent() -> None:
    service = WorkflowService()
    events = (_window_event(1, name="App.exe", path=r"C:\Apps\App.exe", sha="sha-c"),)

    assert service.unapproved_application_identities(events) == ()
    assert service.is_application_approved(ApplicationIdentity(executable_path=r"C:\Apps\App.exe"))


def test_fake_store_satisfies_the_same_protocol_calls() -> None:
    """The Protocol can be faked exactly the way tests inject it."""
    store: ApplicationApprovalStore = FakeApprovalStore()
    identity = ApplicationIdentity(executable_path=r"C:\Apps\App.exe", executable_sha256="x")

    assert not store.is_approved(identity)
    store.approve(identity)
    assert store.is_approved(identity)


def test_review_page_blocks_saving_until_one_time_approval(qtbot, tmp_path) -> None:
    service = make_exe_service(tmp_path)
    page = ReviewPage()
    qtbot.addWidget(page)
    page.show()
    page.set_service(service)
    page.load_proposal(sample_exes_draft())
    identity = ApplicationIdentity(
        name="Demo.exe",
        executable_path=r"C:\Apps\Demo.exe",
        executable_sha256="sha-d",
    )

    page.set_application_identities((identity,))

    assert not page._approve_button.isVisible()
    assert page._applications_container.isVisible()
    assert "Demo" in page._applications_label.text()

    QTest.mouseClick(page._approve_applications, Qt.MouseButton.LeftButton)

    assert service.is_application_approved(identity)
    page.set_application_identities(service.unapproved_application_identities(()))
    assert page._approve_button.isVisible()
    assert not page._applications_container.isVisible()
