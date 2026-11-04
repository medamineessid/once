"""B2: Chrome is a registered desktop application launched on its own profile.

Every launch here is a fake: no browser is started and no window is touched.
The real-application checks are marked ``windows_only`` and never mutate anything.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

from engine.errors import ExecutionError, WorkflowValidationError
from engine.workflow import StepKind, StepStatus, Workflow, WorkflowRunner, WorkflowStep
from integrations.windows_desktop import (
    CHROME_PROFILE_SWITCHES,
    PywinautoDesktopActions,
    WindowsApplicationRegistry,
    chrome_install_candidates,
)

FAKE_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class FakeProcess:
    pid = 4242


def launch_step(target: dict[str, object], step_id: str = "launch") -> WorkflowStep:
    return WorkflowStep(step_id, "Launch", StepKind.LAUNCH_APPLICATION, "", json.dumps(target))


def provider_with(
    candidates: tuple[Path, ...], launched: list[list[str]]
) -> PywinautoDesktopActions:
    def fake_popen(argv: list[str]) -> FakeProcess:
        launched.append(argv)
        return FakeProcess()

    return PywinautoDesktopActions(
        desktop_factory=lambda: None,
        registry=WindowsApplicationRegistry(chrome_candidates=candidates),
        popen=fake_popen,
    )


def test_chrome_is_an_allow_listed_application_name() -> None:
    WorkflowRunner.validate(Workflow("w", "w", (launch_step({"application": "chrome"}),)))


def test_unknown_application_names_are_still_refused() -> None:
    with pytest.raises(WorkflowValidationError, match="registry does not allow"):
        WorkflowRunner.validate(Workflow("w", "w", (launch_step({"application": "cmd"}),)))


def test_registry_resolves_chrome_from_a_standard_location(tmp_path) -> None:
    installed = tmp_path / "chrome.exe"
    installed.write_bytes(b"stub")
    registry = WindowsApplicationRegistry(chrome_candidates=(installed,))

    assert registry.resolve("chrome") == installed
    assert registry.resolve("CHROME") == installed


def test_registry_explains_a_missing_chrome_install(tmp_path) -> None:
    registry = WindowsApplicationRegistry(chrome_candidates=(tmp_path / "absent" / "chrome.exe",))

    with pytest.raises(ExecutionError, match="standard install locations"):
        registry.resolve("chrome")


def test_launching_chrome_uses_a_temporary_profile(tmp_path) -> None:
    launched: list[list[str]] = []
    installed = tmp_path / "chrome.exe"
    installed.write_bytes(b"stub")
    provider = provider_with((installed,), launched)

    result = provider.launch_application(json.dumps({"application": "chrome"}))

    assert result.status is StepStatus.SUCCEEDED
    assert len(launched) == 1
    profile_arguments = [
        argument for argument in launched[0] if argument.startswith("--user-data-dir=")
    ]
    assert len(profile_arguments) == 1
    profile = profile_arguments[0].split("=", 1)[1]
    assert Path(profile).is_absolute()
    assert Path(profile).parent == Path(tempfile.gettempdir())
    assert "isolated_profile=true" in result.evidence
    assert any(evidence.startswith("process_id=") for evidence in result.evidence)


def test_launching_chrome_refuses_to_choose_the_profile(tmp_path) -> None:
    launched: list[list[str]] = []
    installed = tmp_path / "chrome.exe"
    installed.write_bytes(b"stub")
    provider = provider_with((installed,), launched)

    for switch in sorted(CHROME_PROFILE_SWITCHES):
        result = provider.launch_application(
            json.dumps({"application": "chrome", "arguments": [f"{switch}=C:\\profile"]})
        )

        assert result.status is StepStatus.FAILED
        assert switch in result.message
    assert launched == []


def test_a_non_browser_launch_is_unchanged(tmp_path) -> None:
    launched: list[list[str]] = []

    def fake_popen(argv: list[str]) -> FakeProcess:
        launched.append(argv)
        return FakeProcess()

    provider = PywinautoDesktopActions(
        desktop_factory=lambda: None,
        registry=WindowsApplicationRegistry(chrome_candidates=(tmp_path / "chrome.exe",)),
        popen=fake_popen,
    )

    result = provider.launch_application(
        json.dumps({"executable": sys.executable, "arguments": ["--version"]})
    )

    assert result.status is StepStatus.SUCCEEDED
    assert launched == [[sys.executable, "--version"]]
    assert not any("isolated_profile" in evidence for evidence in result.evidence)


@pytest.mark.windows_only
def test_default_chrome_candidates_are_absolute_windows_paths() -> None:
    candidates = chrome_install_candidates()

    assert candidates
    for candidate in candidates:
        assert candidate.is_absolute()
        assert candidate.name == "chrome.exe"
        assert candidate.parent.name == "Application"


@pytest.mark.windows_only
def test_real_chrome_resolves_on_this_machine_or_is_reported_absent() -> None:
    """Manual verification helper: is Chrome actually installed here?"""
    registry = WindowsApplicationRegistry()
    installed = [candidate for candidate in registry.chrome_candidates() if candidate.is_file()]
    if not installed:
        pytest.skip("Chrome is not installed on this machine; the fake tests cover resolution.")

    resolved = registry.resolve("chrome")

    assert resolved.is_file()
    assert resolved.name == "chrome.exe"
