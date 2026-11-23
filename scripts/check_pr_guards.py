"""Pull-request guards for collaborators.

Fails a pull request when it:

1. deletes a test file;
2. adds a skip or xfail without a ``# allowed-skip: <reason>`` comment;
3. changes a dependency file without the ``dependency-approved`` label;
4. touches files outside the task brief named by ``Task: tasks/TASK-0NN.md``
   (owner pull requests skip rule 4), or touches an owner-only path.

Every rule is a pure function over ``Change`` records so it can be unit-tested
without git, GitHub or a network.

Usage (CI):
    python scripts/check_pr_guards.py --base origin/main --event-path "$GITHUB_EVENT_PATH"

Usage (locally):
    python scripts/check_pr_guards.py --base origin/main --body-file body.txt \
        --labels lane/tests --author somecollaborator
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Marker a collaborator must add next to an intentional skip.
SKIP_MARKER = "allowed-skip:"

#: Files whose change needs the owner's ``dependency-approved`` label.
DEPENDENCY_FILES = frozenset(
    {"requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.cfg"}
)

#: Accounts whose pull requests skip the task-brief scope rule.
OWNER_LOGINS = frozenset({"medamineessid"})

#: Paths only the owner may change, whatever a brief says.
OWNER_ONLY = (
    "engine/",
    "storage/",
    "recorder/",
    "controller/",
    "integrations/",
    ".github/",
    "ui/styles/__init__.py",
    "docs/ai_engineering_log.md",
    "scripts/verify.ps1",
    "scripts/check_log_append_only.py",
)

#: Only a line that *starts* with one of these is an executed skip. Matching
#: anywhere would flag the guard's own source and the tests that describe it.
_SKIP_PATTERN = re.compile(
    r"^(@pytest\.mark\.(?:skip|xfail)\b|@unittest\.skip\b|pytest\.skip\(|self\.skipTest\(|@skip\b)"
)
_TASK_LINE = re.compile(r"^Task:\s*(tasks/[\w./-]+\.md)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Change:
    """One changed file, with the lines the pull request adds."""

    path: str
    added: tuple[str, ...] = ()
    deleted: bool = False


def is_test_path(path: str) -> bool:
    return path.startswith("tests/") and path.endswith(".py")


def check_deleted_tests(changes: tuple[Change, ...]) -> list[str]:
    """Rule 1: a test file may never be deleted."""
    return [
        f"test file deleted: {change.path}"
        for change in changes
        if change.deleted and is_test_path(change.path)
    ]


def check_skips(changes: tuple[Change, ...]) -> list[str]:
    """Rule 2: a skip needs an explicit, reasoned marker."""
    failures: list[str] = []
    for change in changes:
        if not is_test_path(change.path):
            continue
        previous = ""
        for line in change.added:
            stripped = line.strip()
            if (
                _SKIP_PATTERN.match(stripped)
                and not stripped.startswith("#")
                and SKIP_MARKER not in line
                and SKIP_MARKER not in previous
            ):
                failures.append(
                    f"skip without '# {SKIP_MARKER} <reason>' in {change.path}: {line.strip()}"
                )
            previous = line
    return failures


def check_dependencies(changes: tuple[Change, ...], labels: frozenset[str]) -> list[str]:
    """Rule 3: dependency changes need the owner's label."""
    if "dependency-approved" in labels:
        return []
    return [
        f"{change.path} changed without the dependency-approved label"
        for change in changes
        if change.path in DEPENDENCY_FILES
    ]


def _section(text: str, title: str) -> list[str]:
    """Lines under ``## <title>`` until the next heading."""
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower().rstrip(":").startswith(title)
            continue
        if inside:
            lines.append(line)
    return lines


def allowed_patterns(brief: str) -> tuple[str, ...]:
    """Backticked paths from the brief's "Files allowed" section."""
    patterns: list[str] = []
    for line in _section(brief, "files allowed"):
        match = re.search(r"`([^`]+)`", line)
        if match:
            patterns.append(match.group(1))
    return tuple(patterns)


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if any(character in pattern for character in "*?["):
        return fnmatch.fnmatch(path, pattern)
    return path == pattern


def check_owner_only(changes: tuple[Change, ...], *, owner: bool) -> list[str]:
    """Owner-only paths, enforced for collaborators regardless of the brief."""
    if owner:
        return []
    return [
        f"owner-only path changed: {change.path}"
        for change in changes
        if any(
            change.path == path or (path.endswith("/") and change.path.startswith(path))
            for path in OWNER_ONLY
        )
    ]


def check_scope(
    changes: tuple[Change, ...],
    body: str,
    *,
    owner: bool,
    brief_dir: Path,
) -> list[str]:
    """Rule 4: only files the task brief allows may change."""
    if owner:
        return []
    match = _TASK_LINE.search(body)
    if match is None:
        return ["PR body needs a line 'Task: tasks/TASK-0NN.md'"]
    brief_path = brief_dir / match.group(1)
    if not brief_path.exists():
        return [f"task brief not found: {match.group(1)}"]
    patterns = allowed_patterns(brief_path.read_text(encoding="utf-8"))
    if not patterns:
        return [f"task brief lists no allowed files: {match.group(1)}"]
    return [
        f"file outside the task brief: {change.path}"
        for change in changes
        if not any(_matches(change.path, pattern) for pattern in patterns)
    ]


def changes_from_diff(diff_text: str, deleted: tuple[str, ...] = ()) -> tuple[Change, ...]:
    """Parse ``git diff --unified=0`` output into ``Change`` records."""
    entries: dict[str, list[str]] = {}
    current: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current = None
            continue
        if line.startswith("+++ b/"):
            current = line[6:]
            entries.setdefault(current, [])
            continue
        if line.startswith("+++ /dev/null") or line.startswith("--- /dev/null"):
            continue
        if current is not None and line.startswith("+") and not line.startswith("+++"):
            entries[current].append(line[1:])
    changes = [Change(path, tuple(lines), path in set(deleted)) for path, lines in entries.items()]
    for path in deleted:
        if path not in entries:
            changes.append(Change(path, (), True))
    return tuple(changes)


def run_guards(
    changes: tuple[Change, ...],
    *,
    body: str,
    labels: frozenset[str],
    author: str,
    brief_dir: Path,
) -> list[str]:
    """Every rule, in one list of human-readable failures."""
    owner = author in OWNER_LOGINS
    failures: list[str] = []
    failures.extend(check_deleted_tests(changes))
    failures.extend(check_skips(changes))
    failures.extend(check_dependencies(changes, labels))
    failures.extend(check_owner_only(changes, owner=owner))
    failures.extend(check_scope(changes, body, owner=owner, brief_dir=brief_dir))
    return failures


def _git(*arguments: str) -> str:
    # Fixed argument list, no shell: the only inputs are refs from the event.
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", *arguments],  # noqa: S607 - git from PATH is intended in CI
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="base ref of the pull request")
    parser.add_argument("--head", default="HEAD", help="head ref of the pull request")
    parser.add_argument("--event-path", help="GitHub event JSON for body, labels and author")
    parser.add_argument("--body-file", help="file holding the pull request body")
    parser.add_argument("--labels", nargs="*", default=[], help="label names on the pull request")
    parser.add_argument("--author", default="", help="pull request author login")
    parser.add_argument("--brief-dir", default=".", help="repository root holding tasks/")
    args = parser.parse_args(argv)

    body = ""
    labels = set(args.labels)
    author = args.author
    if args.event_path:
        event = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
        pull_request = event.get("pull_request") or {}
        body = pull_request.get("body") or ""
        labels = {label["name"] for label in pull_request.get("labels", [])}
        author = (pull_request.get("user") or {}).get("login", author)
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")

    diff_text = _git("diff", "--no-color", "--unified=0", f"{args.base}...{args.head}")
    deleted = tuple(
        line
        for line in _git(
            "diff", "--name-only", "--diff-filter=D", f"{args.base}...{args.head}"
        ).splitlines()
        if line
    )
    changes = changes_from_diff(diff_text, deleted)
    failures = run_guards(
        changes,
        body=body,
        labels=frozenset(labels),
        author=author,
        brief_dir=Path(args.brief_dir),
    )
    print(f"pr-guards: {len(changes)} changed file(s), {len(failures)} failure(s)")
    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        print("PR GUARDS FAILED")
        return 1
    print("PR GUARDS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
