"""Each guard rule must fail on a real violation and pass on a clean change."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_pr_guards as guards  # noqa: E402
import pytest  # noqa: E402


def _change(path: str, *added: str, deleted: bool = False) -> guards.Change:
    return guards.Change(path, tuple(added), deleted)


def test_deleted_test_file_fails() -> None:
    failures = guards.check_deleted_tests((_change("tests/test_engine.py", deleted=True),))
    assert failures == ["test file deleted: tests/test_engine.py"]


def test_deleted_source_file_is_not_a_guard_failure() -> None:
    assert guards.check_deleted_tests((_change("ui/old_widget.py", deleted=True),)) == []


def test_skip_without_reason_fails() -> None:
    changes = (_change("tests/test_thing.py", "    @pytest.mark.skip(reason='later')"),)
    assert guards.check_skips(changes)


def test_skip_with_a_reason_passes() -> None:
    changes = (
        _change(
            "tests/test_thing.py",
            "    @pytest.mark.skip(reason='no symlinks')  # allowed-skip: no symlink support",
        ),
    )
    assert guards.check_skips(changes) == []


def test_dependency_change_needs_the_label() -> None:
    changes = (_change("requirements-dev.txt", "ruff==0.17.1"),)
    assert guards.check_dependencies(changes, frozenset())
    assert guards.check_dependencies(changes, frozenset({"dependency-approved"})) == []


def test_owner_only_path_is_refused_for_a_collaborator() -> None:
    changes = (_change("engine/executor.py", "x = 1"),)
    assert guards.check_owner_only(changes, owner=False)
    assert guards.check_owner_only(changes, owner=True) == []


def test_scope_requires_a_task_line() -> None:
    failures = guards.check_scope(
        (_change("README.md"),), "no task here", owner=False, brief_dir=Path()
    )
    assert failures == ["PR body needs a line 'Task: tasks/TASK-0NN.md'"]


def test_scope_rejects_a_file_outside_the_brief(tmp_path: Path) -> None:
    brief = tmp_path / "tasks" / "TASK-001.md"
    brief.parent.mkdir(parents=True)
    brief.write_text(
        "# TASK-001\n\n## Files allowed\n\n- `tests/scenarios/lab.py`\n- `tests/scenarios/`\n\n"
        "## Files forbidden\n\n- `engine/`\n",
        encoding="utf-8",
    )
    body = "Task: tasks/TASK-001.md"
    allowed = guards.check_scope(
        (_change("tests/scenarios/lab.py", "x = 1"),), body, owner=False, brief_dir=tmp_path
    )
    refused = guards.check_scope(
        (_change("ui/pages/home.py", "x = 1"),), body, owner=False, brief_dir=tmp_path
    )
    assert allowed == []
    assert refused == ["file outside the task brief: ui/pages/home.py"]


def test_owner_pull_request_skips_the_scope_rule() -> None:
    assert guards.check_scope((_change("ui/pages/home.py")), "", owner=True, brief_dir=Path()) == []


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("tests/scenarios/lab.py", "tests/scenarios/", True),
        ("tests/scenarios/lab.py", "tests/test_*.py", False),
        ("ui/strings.py", "ui/strings.py", True),
    ],
)
def test_pattern_matching(path: str, pattern: str, expected: bool) -> None:
    assert guards._matches(path, pattern) is expected


def test_diff_parsing_collects_added_lines_and_deletions() -> None:
    diff = (
        "diff --git a/tests/test_a.py b/tests/test_a.py\n"
        "--- a/tests/test_a.py\n"
        "+++ b/tests/test_a.py\n"
        "+@pytest.mark.skip\n"
        "diff --git a/requirements.txt b/requirements.txt\n"
        "--- a/requirements.txt\n"
        "+++ b/requirements.txt\n"
        "+send2trash==1.8.3\n"
    )
    changes = guards.changes_from_diff(diff, deleted=("tests/gone.py",))
    by_path = {change.path: change for change in changes}
    assert by_path["tests/test_a.py"].added == ("@pytest.mark.skip",)
    assert by_path["requirements.txt"].added == ("send2trash==1.8.3",)
    assert by_path["tests/gone.py"].deleted is True


def test_every_rule_runs_together() -> None:
    changes = (
        _change("tests/test_gone.py", deleted=True),
        _change("requirements.txt", "x==1"),
        _change("tests/test_new.py", "    pytest.skip('later')"),
    )
    failures = guards.run_guards(
        changes, body="", labels=frozenset(), author="collaborator", brief_dir=Path()
    )
    assert any("test file deleted" in failure for failure in failures)
    assert any("dependency-approved" in failure for failure in failures)
    assert any("skip without" in failure for failure in failures)
