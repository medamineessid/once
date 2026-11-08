"""End-to-end tests for the desktop application approval registry path.

Verifies that:
1. An application approved in SqliteApplicationRegistry or DatabaseApplicationApprovalStore
   launches by recorded executable path and SHA-256 through PywinautoDesktopActions.
2. An unapproved executable is refused with an approval_needed message and never calls popen.
3. A modified executable (SHA-256 mismatch) is refused with hash_mismatch and never calls popen.
4. CLOSE_APPLICATION closes only the PID launched by the current run.
5. WorkflowService.for_app_data wires the persisted approval store into PywinautoDesktopActions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from controller.approvals import ApplicationIdentity, DatabaseApplicationApprovalStore
from controller.service import WorkflowService
from engine.desktop import approve_desktop_workflow
from engine.replay import DESKTOP_INTERACTION_POLICY, ReplayExecutor
from engine.workflow import StepKind, StepStatus, Workflow, WorkflowStep
from integrations.windows_desktop import PywinautoDesktopActions
from storage.app_registry import SqliteApplicationRegistry
from storage.database import connect


class _FakeProcess:
    def __init__(self, pid: int = 7777) -> None:
        self.pid = pid


class _FakeElementInfo:
    def __init__(self, name: str, process_id: int, handle: int = 101) -> None:
        self.name = name
        self.process_id = process_id
        self.handle = handle
        self.class_name = "TestWindowClass"
        self.control_type = "Window"


class _FakeWindow:
    def __init__(self, info: _FakeElementInfo) -> None:
        self.element_info = info
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeDesktop:
    def __init__(self, windows: list[_FakeWindow]) -> None:
        self._windows = windows

    def windows(self) -> list[_FakeWindow]:
        return [w for w in self._windows if not w.closed]


def _make_stub_exe(
    tmp_path: Path, name: str = "sample_tool.exe", content: bytes = b"PE-stub-1"
) -> Path:
    exe = tmp_path / name
    exe.write_bytes(content)
    return exe


def test_registry_approved_app_launches_and_closes_by_pid(tmp_path: Path) -> None:
    exe = _make_stub_exe(tmp_path)
    connection = connect(tmp_path / "once.db")
    registry = SqliteApplicationRegistry(connection)
    registry.propose(exe, "Sample Tool")
    registry.approve(exe)

    launched_argvs: list[list[str]] = []
    own_window = _FakeWindow(_FakeElementInfo("Sample Tool", process_id=7777, handle=101))
    other_window = _FakeWindow(_FakeElementInfo("User Window", process_id=9999, handle=202))
    desktop = _FakeDesktop([own_window, other_window])

    actions = PywinautoDesktopActions(
        desktop_factory=lambda: desktop,
        approvals=registry,
        popen=lambda argv: launched_argvs.append(argv) or _FakeProcess(7777),
        is_visible=lambda w: not w.closed,
        has_owner=lambda _w: False,
        process_alive=lambda pid: pid == 9999 or not own_window.closed,
    )

    target = json.dumps({"executable": str(exe)})
    workflow = Workflow(
        "open-close-tool",
        "Open and close tool",
        (
            WorkflowStep("s1", "Open tool", StepKind.LAUNCH_APPLICATION, "Open.", target=target),
            WorkflowStep("s2", "Close tool", StepKind.CLOSE_APPLICATION, "Close.", target=target),
        ),
    )
    approval = approve_desktop_workflow(workflow)
    run = ReplayExecutor(DESKTOP_INTERACTION_POLICY).execute(
        approval.workflow,
        allowed_root=None,
        desktop_actions=actions,
    )

    assert run.status.value == "SUCCEEDED"
    assert [r.status for r in run.results] == [StepStatus.SUCCEEDED, StepStatus.SUCCEEDED]
    assert launched_argvs == [[str(exe)]]
    assert own_window.closed is True
    assert other_window.closed is False
    assert "process_id=7777" in run.results[0].evidence
    assert "windows_closed=1" in run.results[1].evidence


def test_unapproved_app_is_refused_without_launching(tmp_path: Path) -> None:
    exe = _make_stub_exe(tmp_path)
    connection = connect(tmp_path / "once.db")
    registry = SqliteApplicationRegistry(connection)

    launched_argvs: list[list[str]] = []
    actions = PywinautoDesktopActions(
        desktop_factory=lambda: _FakeDesktop([]),
        approvals=registry,
        popen=lambda argv: launched_argvs.append(argv) or _FakeProcess(),
    )

    target = json.dumps({"executable": str(exe)})
    result = actions.launch_application(target)

    assert result.status is StepStatus.FAILED
    assert "permission" in result.message.lower() or "approve" in result.message.lower()
    assert "approval_needed=true" in result.evidence
    assert "approval_reason=not_recorded" in result.evidence
    assert launched_argvs == []


def test_hash_mismatch_is_refused_without_launching(tmp_path: Path) -> None:
    exe = _make_stub_exe(tmp_path, content=b"version-1")
    connection = connect(tmp_path / "once.db")
    registry = SqliteApplicationRegistry(connection)
    registry.approve(exe, display_name="Sample Tool")

    # Modify the binary after approval.
    exe.write_bytes(b"version-2-tampered")

    launched_argvs: list[list[str]] = []
    actions = PywinautoDesktopActions(
        desktop_factory=lambda: _FakeDesktop([]),
        approvals=registry,
        popen=lambda argv: launched_argvs.append(argv) or _FakeProcess(),
    )

    result = actions.launch_application(json.dumps({"executable": str(exe)}))

    assert result.status is StepStatus.FAILED
    assert "changed since it was approved" in result.message
    assert "approval_reason=hash_mismatch" in result.evidence
    assert launched_argvs == []


def test_ui_approval_store_bridges_to_engine_desktop_actions(tmp_path: Path) -> None:
    """Approving via DatabaseApplicationApprovalStore lets PywinautoDesktopActions launch."""
    exe = _make_stub_exe(tmp_path, content=b"trusted-binary")
    sha256 = hashlib.sha256(exe.read_bytes()).hexdigest()

    service = WorkflowService.for_app_data(tmp_path / "appdata")
    identity = ApplicationIdentity(
        name="Sample Tool",
        executable_path=str(exe),
        executable_sha256=sha256,
    )
    assert service.is_application_approved(identity) is False
    service.approve_application(identity)
    assert service.is_application_approved(identity) is True

    store = DatabaseApplicationApprovalStore(tmp_path / "appdata" / "once.db")
    record = store.find(exe)
    assert record is not None
    assert record.approved is True
    assert record.sha256 == sha256
    assert service._desktop_actions._approvals is not None
    assert service._desktop_actions._approvals.find(exe) is not None


def test_mixed_desktop_and_report_workflow_runs_as_partially_performed(tmp_path: Path) -> None:
    """A recorded draft with LAUNCH + REPORT + CLOSE reports PARTIALLY_PERFORMED."""
    exe = _make_stub_exe(tmp_path)
    connection = connect(tmp_path / "once.db")
    registry = SqliteApplicationRegistry(connection)
    registry.approve(exe, display_name="Sample Tool")

    own_window = _FakeWindow(_FakeElementInfo("Sample Tool", process_id=7777, handle=101))
    desktop = _FakeDesktop([own_window])
    actions = PywinautoDesktopActions(
        desktop_factory=lambda: desktop,
        approvals=registry,
        popen=lambda _argv: _FakeProcess(7777),
        is_visible=lambda w: not w.closed,
        has_owner=lambda _w: False,
        process_alive=lambda _pid: not own_window.closed,
    )

    target = json.dumps({"executable": str(exe)})
    workflow = Workflow(
        "mixed-recorded-flow",
        "Mixed recorded flow",
        (
            WorkflowStep("s1", "Open tool", StepKind.LAUNCH_APPLICATION, "Open.", target=target),
            WorkflowStep("s2", "Observed click", StepKind.REPORT, "Click at (50, 60)."),
            WorkflowStep("s3", "Close tool", StepKind.CLOSE_APPLICATION, "Close.", target=target),
        ),
    )
    approval = approve_desktop_workflow(workflow, allow_observations=True)
    service = WorkflowService(desktop_actions=actions)
    run = service.run_desktop_approved(approval)

    assert run.status.value == "PARTIALLY_PERFORMED"
    assert [r.status for r in run.results] == [
        StepStatus.SUCCEEDED,
        StepStatus.OBSERVED,
        StepStatus.SUCCEEDED,
    ]


def test_run_desktop_approved_auto_registers_workflow_executables(tmp_path: Path) -> None:
    """When a human approves a desktop run via DesktopApproval, any LAUNCH_APPLICATION
    executable in the approved workflow is registered in the approval store before execution."""
    exe = _make_stub_exe(tmp_path, name="editor_tool.exe", content=b"editor-built-exe")
    service = WorkflowService.for_app_data(tmp_path / "appdata")
    launched_argvs: list[list[str]] = []
    service._desktop_actions = PywinautoDesktopActions(
        desktop_factory=lambda: _FakeDesktop([]),
        approvals=service._approval_store,  # type: ignore[arg-type]
        popen=lambda argv: launched_argvs.append(argv) or _FakeProcess(8888),
    )

    target = json.dumps({"executable": str(exe)})
    workflow = Workflow(
        "editor-built-launch",
        "Editor built launch",
        (WorkflowStep("s1", "Launch tool", StepKind.LAUNCH_APPLICATION, "Launch.", target=target),),
    )
    approval = approve_desktop_workflow(workflow)
    run = service.run_desktop_approved(approval)

    assert run.status.value == "SUCCEEDED"
    assert launched_argvs == [[str(exe)]]
    assert service._approval_store is not None
    assert service._approval_store.find(exe) is not None  # type: ignore[attr-defined]
