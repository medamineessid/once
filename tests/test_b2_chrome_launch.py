"""B2: Browser launch validation and desktop executable launch checks."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from engine.errors import WorkflowValidationError
from engine.workflow import (
    ApprovedApplication,
    StepKind,
    StepStatus,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)
from integrations.chrome_devtools import BrowserError, ChromeApplicationRegistry
from integrations.windows_desktop import PywinautoDesktopActions

FAKE_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class FakeProcess:
    pid = 4242


class FakeApprovals:
    def find(self, executable: Path) -> ApprovedApplication:
        return ApprovedApplication(
            executable=executable,
            sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            display_name="Test App",
            approved=True,
            close_supported=True,
        )


def launch_step(target: dict[str, object], step_id: str = "launch") -> WorkflowStep:
    return WorkflowStep(step_id, "Launch", StepKind.LAUNCH_APPLICATION, "", json.dumps(target))


def test_executable_path_is_accepted_for_launch() -> None:
    WorkflowRunner.validate(Workflow("w", "w", (launch_step({"executable": str(FAKE_CHROME)}),)))


def test_application_name_field_is_refused_in_favor_of_executable() -> None:
    with pytest.raises(WorkflowValidationError, match="unknown launch fields: application"):
        WorkflowRunner.validate(Workflow("w", "w", (launch_step({"application": "cmd"}),)))


def test_chrome_registry_rejects_unknown_browser_names() -> None:
    registry = ChromeApplicationRegistry()
    with pytest.raises(BrowserError, match="does not contain"):
        registry.resolve("edge")


def test_a_non_browser_launch_passes_exact_argv() -> None:
    launched: list[list[str]] = []

    def fake_popen(argv: list[str]) -> FakeProcess:
        launched.append(argv)
        return FakeProcess()

    provider = PywinautoDesktopActions(
        desktop_factory=lambda: None,
        approvals=FakeApprovals(),
        popen=fake_popen,
    )

    result = provider.launch_application(
        json.dumps({"executable": sys.executable, "arguments": ["--version"]})
    )

    assert result.status is StepStatus.SUCCEEDED
    assert launched == [[sys.executable, "--version"]]


@pytest.mark.windows_only
def test_default_chrome_candidates_are_absolute_windows_paths() -> None:
    for candidate in ChromeApplicationRegistry.CANDIDATES:
        assert candidate.is_absolute()
        assert candidate.name == "chrome.exe"
        assert candidate.parent.name == "Application"
