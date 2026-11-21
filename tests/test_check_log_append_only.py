"""Tests for scripts/check_log_append_only.py.

The engineering log must only ever grow. These tests pin the six behaviours the
gate relies on, plus CRLF tolerance and the command-line exit codes.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = PROJECT_ROOT / "scripts" / "check_log_append_only.py"


def _load_checker() -> object:
    spec = importlib.util.spec_from_file_location("check_log_append_only", CHECKER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def test_appended_lines_pass() -> None:
    assert checker.is_append_only(b"a\nb\n", b"a\nb\nc\nd\n") is True


def test_trailing_newline_only_passes() -> None:
    # The false positive this gate replaces: main's copy ended without a newline.
    assert checker.is_append_only(b"a\n- Human review:", b"a\n- Human review:\n") is True


def test_edited_middle_line_fails() -> None:
    assert checker.is_append_only(b"a\nb\nc\n", b"a\nB\nc\n") is False


def test_deleted_last_line_fails() -> None:
    assert checker.is_append_only(b"a\nb\n", b"a\n") is False


def test_deleted_block_fails() -> None:
    assert checker.is_append_only(b"a\nb\nc\nd\n", b"a\nd\n") is False


def test_file_absent_at_base_passes() -> None:
    assert checker.is_append_only(None, b"anything at all") is True


def test_crlf_base_matches_lf_head() -> None:
    assert checker.is_append_only(b"a\r\nb\r\n", b"a\nb\nc\n") is True


def test_first_difference_reports_offset() -> None:
    assert checker.first_difference(b"abc\n", b"abX\n") == 2


GIT_ISOLATION = (
    "-c",
    "core.autocrlf=false",
    "-c",
    "core.eol=lf",
    "-c",
    "user.email=tests@example.invalid",
    "-c",
    "user.name=Once Tests",
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    argv = ("git", *GIT_ISOLATION, *args)
    return subprocess.run(argv, cwd=repo, capture_output=True, text=True, check=True)


def _commit(repo: Path, text: str, message: str) -> str:
    (repo / "log.md").write_text(text, encoding="utf-8", newline="")
    _git(repo, "add", "log.md")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _run_checker(repo: Path, base: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (sys.executable, str(CHECKER_PATH), base, "log.md"),
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_passes_when_entries_are_appended(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    base = _commit(tmp_path, "first entry\n", "first")
    _commit(tmp_path, "first entry\nsecond entry\n", "second")

    completed = _run_checker(tmp_path, base)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS" in completed.stdout


def test_cli_fails_when_an_earlier_line_changes(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    base = _commit(tmp_path, "first entry\n", "first")
    _commit(tmp_path, "EDITED entry\nsecond entry\n", "second")

    completed = _run_checker(tmp_path, base)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "FAIL" in completed.stdout


def test_cli_passes_when_the_base_has_no_such_file(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "other.md").write_text("other\n", encoding="utf-8", newline="")
    _git(tmp_path, "add", "other.md")
    _git(tmp_path, "commit", "-m", "only other file")
    base = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    _commit(tmp_path, "first entry\n", "add log")

    completed = _run_checker(tmp_path, base)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "does not exist" in completed.stdout
