"""Tests for scripts/check_log_append_only.py.

The engineering log must only ever grow. These tests pin the six behaviours the
gate relies on, plus CRLF tolerance and the command-line exit codes.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = PROJECT_ROOT / "scripts" / "check_log_append_only.py"


def _load_checker() -> object:
    spec = importlib.util.spec_from_file_location("check_log_append_only", CHECKER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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


def _run_checker(
    repo: Path, base: str, mode: str | None = None
) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(CHECKER_PATH), base, "log.md"]
    if mode is not None:
        argv.extend(("--mode", mode))
    return subprocess.run(
        argv,
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


def test_cli_fails_when_a_line_is_inserted_in_the_middle(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    base = _commit(tmp_path, "first entry\nsecond entry\n", "first")
    _commit(tmp_path, "first entry\nINSERTED\nsecond entry\n", "insert in the middle")

    completed = _run_checker(tmp_path, base)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "FAIL" in completed.stdout
    assert "add new entries at the end" in completed.stdout


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


# --- boundary mode (temporary exception, see the module docstring) -----------

OLD_LOG = "# Once log\n\n## A\nbody A\n## B\nbody B\n"


def test_boundary_new_entry_between_old_entries_passes() -> None:
    new_log = "# Once log\n\n## A\nbody A\n## NEW\nbody NEW\n## B\nbody B\n"

    assert checker.is_append_only(OLD_LOG.encode(), new_log.encode(), "boundary") is True


def test_boundary_entry_appended_at_the_end_passes() -> None:
    new_log = OLD_LOG + "## C\nbody C\n"

    assert checker.is_append_only(OLD_LOG.encode(), new_log.encode(), "boundary") is True


def test_boundary_line_inserted_inside_an_entry_fails() -> None:
    new_log = "# Once log\n\n## A\ninjected inside A\nbody A\n## B\nbody B\n"

    assert checker.is_append_only(OLD_LOG.encode(), new_log.encode(), "boundary") is False


def test_boundary_edited_old_line_fails() -> None:
    new_log = OLD_LOG.replace("body A", "body A edited")

    assert checker.is_append_only(OLD_LOG.encode(), new_log.encode(), "boundary") is False


def test_boundary_deleted_old_line_fails() -> None:
    new_log = OLD_LOG.replace("body B\n", "")

    assert checker.is_append_only(OLD_LOG.encode(), new_log.encode(), "boundary") is False


def test_boundary_swapped_old_entries_fail() -> None:
    new_log = "# Once log\n\n## B\nbody B\n## A\nbody A\n"

    assert checker.is_append_only(OLD_LOG.encode(), new_log.encode(), "boundary") is False


def test_boundary_is_crlf_tolerant() -> None:
    crlf_base = OLD_LOG.replace("\n", "\r\n").encode()
    new_log = OLD_LOG + "## C\nbody C\n"

    assert checker.is_append_only(crlf_base, new_log.encode(), "boundary") is True


def test_boundary_reports_the_position_of_each_insertion() -> None:
    new_log = "# Once log\n\n## A\nbody A\n## NEW\nbody NEW\n## B\nbody B\n"

    insertions, survived = checker.find_insertions(OLD_LOG.encode(), new_log.encode())

    assert survived is True
    assert len(insertions) == 1
    assert insertions[0].at_boundary is True
    assert insertions[0].before_text == "## B"
    assert "before ## B" in insertions[0].describe()


def test_prefix_mode_still_rejects_a_middle_insertion() -> None:
    new_log = "# Once log\n\n## A\nbody A\n## NEW\nbody NEW\n## B\nbody B\n"

    assert checker.is_append_only(OLD_LOG.encode(), new_log.encode(), "prefix") is False


# --- boundary mode: blank separator lines are not entry content --------------
# These mirror the real lane merge: an entry inserted after the header, with the
# base's spare blank line aligning to a blank inside the inserted entry's
# separator, and two blank lines inserted into a separator run.


SEPARATED_LOG = "# Once log\n\n## A\nbody A\n\n\n## B\nbody B\n"


def test_boundary_entry_inserted_before_a_blank_run_passes() -> None:
    new_log = "# Once log\n\n## NEW\nbody NEW\n\n## A\nbody A\n\n\n## B\nbody B\n"

    assert checker.is_append_only(SEPARATED_LOG.encode(), new_log.encode(), "boundary") is True


def test_boundary_blank_lines_inserted_into_a_separator_pass() -> None:
    new_log = "# Once log\n\n## A\nbody A\n\n\n\n\n## B\nbody B\n"

    insertions, survived = checker.find_insertions(SEPARATED_LOG.encode(), new_log.encode())

    assert survived is True
    assert [item.is_blank_padding for item in insertions] == [True]
    assert checker.is_append_only(SEPARATED_LOG.encode(), new_log.encode(), "boundary") is True


def test_boundary_line_inserted_before_a_body_line_fails() -> None:
    new_log = "# Once log\n\n## A\ninjected\nbody A\n\n\n## B\nbody B\n"

    insertions, survived = checker.find_insertions(SEPARATED_LOG.encode(), new_log.encode())

    assert survived is True
    assert len(insertions) == 1
    assert insertions[0].before_text == "body A"
    assert insertions[0].at_boundary is False
    assert checker.is_append_only(SEPARATED_LOG.encode(), new_log.encode(), "boundary") is False


def test_boundary_reports_the_heading_after_the_blank_run() -> None:
    new_log = "# Once log\n\n## NEW\nbody NEW\n\n## A\nbody A\n\n\n## B\nbody B\n"

    insertions, _ = checker.find_insertions(SEPARATED_LOG.encode(), new_log.encode())

    assert len(insertions) == 1
    assert insertions[0].before_text == "## A"


def test_cli_boundary_mode_reports_a_pass(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    base = _commit(tmp_path, OLD_LOG, "first")
    _commit(tmp_path, OLD_LOG + "## C\nbody C\n", "second")

    completed = _run_checker(tmp_path, base, "boundary")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS" in completed.stdout
    assert "insertion" in completed.stdout


# --- argument validation (Sonar S8705: no argument injection) ----------------


def test_ref_must_look_like_a_git_revision() -> None:
    assert checker._validated_ref("origin/main") == "origin/main"
    assert checker._validated_ref("4bfc619") == "4bfc619"
    assert checker._validated_ref("refs/heads/lane-a-merged") == "refs/heads/lane-a-merged"


def test_ref_starting_with_a_dash_is_refused() -> None:
    with pytest.raises(ValueError, match="Not a git ref"):
        checker._validated_ref("--output=/tmp/evil")


def test_ref_with_a_space_is_refused() -> None:
    with pytest.raises(ValueError, match="Not a git ref"):
        checker._validated_ref("origin/main --upload-pack=calc")


def test_path_must_stay_inside_the_repository() -> None:
    assert checker._validated_path("docs/ai_engineering_log.md") == "docs/ai_engineering_log.md"
    assert checker._validated_path("docs\\ai_engineering_log.md") == "docs\\ai_engineering_log.md"


def test_path_with_parent_traversal_is_refused() -> None:
    with pytest.raises(ValueError, match="Not a repository-relative file path"):
        checker._validated_path("docs/../../etc/passwd")


def test_absolute_path_is_refused() -> None:
    with pytest.raises(ValueError, match="Not a repository-relative file path"):
        checker._validated_path("/etc/passwd")


def test_path_starting_with_a_dash_is_refused() -> None:
    with pytest.raises(ValueError, match="Not a repository-relative file path"):
        checker._validated_path("-c core.pager=calc")


def test_cli_rejects_a_traversing_path(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "first entry\n", "first")
    base = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    completed = subprocess.run(
        (sys.executable, str(CHECKER_PATH), base, "../escape.md"),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert "Not a repository-relative file path" in completed.stderr
