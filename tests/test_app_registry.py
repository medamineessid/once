"""The approved-application registry: the only source of launch permission.

Every application here is a fake executable written into ``tmp_path``; no real
application is launched and no application is named anywhere in the code.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.workflow import StepStatus
from integrations.windows_desktop import PywinautoDesktopActions
from storage.app_registry import SqliteApplicationRegistry, executable_sha256
from storage.database import connect


class FakeProcess:
    pid = 4242


def fake_app(tmp_path: Path, name: str = "harmless.exe", content: bytes = b"once-v1") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def registry_for(path: Path) -> SqliteApplicationRegistry:
    return SqliteApplicationRegistry(connect(path))


def target(executable: Path, arguments: list[str] | None = None) -> str:
    payload: dict[str, object] = {"executable": str(executable)}
    if arguments is not None:
        payload["arguments"] = arguments
    return json.dumps(payload)


def provider_for(
    registry: SqliteApplicationRegistry | None,
    launched: list[list[str]] | None = None,
) -> PywinautoDesktopActions:
    calls = launched if launched is not None else []

    def fake_popen(argv: list[str]) -> FakeProcess:
        calls.append(argv)
        return FakeProcess()

    return PywinautoDesktopActions(approvals=registry, popen=fake_popen)


# ------------------------------------------------------------------- storage


def test_propose_records_a_pending_application_with_its_content_hash(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    registry = registry_for(tmp_path / "once.db")

    record = registry.propose(app, "Harmless app")

    assert record.approved is False
    assert record.close_supported is True
    assert record.sha256 == executable_sha256(app)
    assert registry.find(app) == record


def test_approve_records_the_version_on_disk(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    registry = registry_for(tmp_path / "once.db")
    registry.propose(app, "Harmless app")

    approved = registry.approve(app)

    assert approved.approved is True
    assert approved.display_name == "Harmless app"


def test_a_changed_executable_needs_a_new_approval(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    registry = registry_for(tmp_path / "once.db")
    registry.approve(app, display_name="Harmless app")
    app.write_bytes(b"once-v2")

    assert registry.find(app).sha256 != executable_sha256(app)  # type: ignore[union-attr]
    reapproved = registry.approve(app)
    assert reapproved.sha256 == executable_sha256(app)
    assert reapproved.approved is True


def test_close_supported_is_stored_data_for_that_application(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    registry = registry_for(tmp_path / "once.db")
    registry.approve(app, display_name="Harmless app", close_supported=False)

    assert registry.find(app).close_supported is False  # type: ignore[union-attr]
    assert registry.set_close_supported(app, True).close_supported is True


def test_list_is_ordered_by_display_name_and_forget_removes_the_record(tmp_path: Path) -> None:
    registry = registry_for(tmp_path / "once.db")
    second = fake_app(tmp_path, "b.exe")
    first = fake_app(tmp_path, "a.exe")
    registry.approve(second, display_name="Second")
    registry.approve(first, display_name="First")

    assert [record.display_name for record in registry.list()] == ["First", "Second"]

    registry.forget(first)
    assert registry.find(first) is None
    assert [record.display_name for record in registry.list()] == ["Second"]


def test_nothing_is_seeded_from_code(tmp_path: Path) -> None:
    """A fresh database knows no applications at all."""
    assert registry_for(tmp_path / "once.db").list() == ()


# ------------------------------------------------------------------- adapter


def test_unknown_application_is_refused_and_never_launched(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    launched: list[list[str]] = []
    provider = provider_for(registry_for(tmp_path / "once.db"), launched)

    result = provider.launch_application(target(app))

    assert result.status is StepStatus.FAILED
    assert "permission" in result.message
    assert "approval_needed=true" in result.evidence
    assert "approval_reason=not_recorded" in result.evidence
    assert f"sha256={executable_sha256(app)}" in result.evidence
    assert launched == []


def test_approved_application_launches_with_the_exact_argv(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    registry = registry_for(tmp_path / "once.db")
    registry.approve(app, display_name="Harmless app")
    launched: list[list[str]] = []
    provider = provider_for(registry, launched)

    result = provider.launch_application(target(app, ["--flag"]))

    assert result.status is StepStatus.SUCCEEDED
    assert launched == [[str(app), "--flag"]]
    assert "display_name=Harmless app" in result.evidence
    assert "close_supported=true" in result.evidence


def test_a_changed_executable_is_refused(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    registry = registry_for(tmp_path / "once.db")
    registry.approve(app, display_name="Harmless app")
    app.write_bytes(b"once-tampered")
    launched: list[list[str]] = []
    provider = provider_for(registry, launched)

    result = provider.launch_application(target(app))

    assert result.status is StepStatus.FAILED
    assert "changed since it was approved" in result.message
    assert "approval_reason=hash_mismatch" in result.evidence
    assert launched == []


def test_a_pending_application_is_not_launched(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    registry = registry_for(tmp_path / "once.db")
    registry.propose(app, "Harmless app")
    launched: list[list[str]] = []
    provider = provider_for(registry, launched)

    result = provider.launch_application(target(app))

    assert result.status is StepStatus.FAILED
    assert "waiting for your approval" in result.message
    assert "approval_reason=pending_approval" in result.evidence
    assert launched == []


def test_a_launch_without_an_approval_source_fails_closed(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    launched: list[list[str]] = []
    provider = provider_for(None, launched)

    result = provider.launch_application(target(app))

    assert result.status is StepStatus.FAILED
    assert "approval_needed=true" in result.evidence
    assert launched == []


def test_close_fails_closed_when_the_record_forbids_closing(tmp_path: Path) -> None:
    app = fake_app(tmp_path)
    registry = registry_for(tmp_path / "once.db")
    registry.approve(app, display_name="Harmless app", close_supported=False)
    provider = provider_for(registry)

    assert provider.launch_application(target(app)).status is StepStatus.SUCCEEDED

    result = provider.close_application(target(app))

    assert result.status is StepStatus.FAILED
    assert "cannot close this application" in result.message
    assert "close_supported=false" in result.evidence
