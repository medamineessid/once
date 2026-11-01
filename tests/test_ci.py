"""Tests for the GitHub Actions CI workflow and verification script (Lane C).

Covers Task C1: CI Green and Required.
Ensures that the CI workflow runs on Windows, targets Python 3.14, executes
the verification gate (scripts/verify.ps1), handles failure codes properly,
and avoids bashisms in PowerShell commands.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "tests.yml"
VERIFY_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "verify.ps1"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


def test_ci_workflow_exists_and_has_stable_check_name() -> None:
    assert WORKFLOW_PATH.is_file(), f"Missing workflow at {WORKFLOW_PATH}"
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Workflow must have a clean name and job name suitable for required status checks
    assert "name: CI" in text
    assert "runs-on: windows-latest" in text
    # Verify events
    assert "push:" in text
    assert "pull_request:" in text
    assert "branches: [ main ]" in text or "branches: [main]" in text


def test_ci_workflow_targets_supported_python_version() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    pyproject_text = PYPROJECT_PATH.read_text(encoding="utf-8")

    # pyproject.toml targets py314
    assert 'target-version = "py314"' in pyproject_text

    # Workflow specifies Python 3.14
    assert "python-version: '3.14'" in text or 'python-version: "3.14"' in text
    assert "sys.version_info[:2] == (3, 14)" in text


def test_ci_workflow_uses_full_git_history_and_offscreen_qt() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Full depth checkout is needed for git diff append-only check against origin/main
    assert "fetch-depth: 0" in text

    # Qt must run offscreen for headless CI
    assert "QT_QPA_PLATFORM: offscreen" in text


def test_ci_workflow_avoids_bashisms_in_powershell_steps() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Forbidden bash patterns in PowerShell run blocks
    forbidden_bashisms = ["export ", "set -e", "&&", "||", "fi\n", "then\n"]
    for bashism in forbidden_bashisms:
        assert bashism not in text, f"Found bashism '{bashism}' in workflow"


def test_ci_workflow_executes_verification_gate_and_propagates_failures() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Runs verify.ps1
    assert "verify.ps1" in text
    # Checks failure exit code
    assert "$LASTEXITCODE" in text


def test_verify_script_covers_all_required_checks() -> None:
    assert VERIFY_SCRIPT_PATH.is_file(), f"Missing script at {VERIFY_SCRIPT_PATH}"
    text = VERIFY_SCRIPT_PATH.read_text(encoding="utf-8")

    required_check_names = [
        "pytest -q",
        "ruff check .",
        "ruff format --check .",
        "app.py --smoke-test",
        "app.py --shell --smoke-test",
        "engineering log append-only",
    ]
    for check in required_check_names:
        assert check in text, f"Missing required check '{check}' in verify.ps1"

    # Must exit 1 if real checks failed
    assert "if ($script:RealChecksFailed)" in text
    assert "exit 1" in text
    assert "ALL CHECKS PASSED" in text


def test_verify_script_supports_venv_and_fallback_python() -> None:
    text = VERIFY_SCRIPT_PATH.read_text(encoding="utf-8")

    # Supports both default .venv and alternative/global python
    assert "$defaultVenvPython" in text
    assert "python.exe" in text
    assert "origin/main" in text
