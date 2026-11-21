"""Fail when a tracked file's earlier content changed or disappeared.

The previous gate used `git diff --numstat`, which counts a deletion whenever
the base copy of a file ends without a trailing newline and the new copy adds
one. That produced a false positive against `main` for
`docs/ai_engineering_log.md`.

Two modes are supported.

``prefix`` (permanent default)
    The new content must start with the old content, byte for byte. Appending
    lines, or adding a trailing newline, passes. Anything else fails.

``boundary`` (temporary exception)
    Every base line must still be present, in order, unedited, and every
    inserted block must sit at an entry boundary: the next non-blank line after
    the block must be a line that starts with ``## `` (a log entry heading), or
    there must be no such line (end of file). Blank lines are separators rather
    than entry content, so a block may land in a blank run directly before a
    heading. A block that lands before a body line is inside an entry and is
    rejected.

``boundary`` exists only because the lane merge inserted entries out of order;
``verify.ps1`` must be switched back to ``prefix`` once PR #1 has merged.

Usage:
    python scripts/check_log_append_only.py <base-ref> <path> [--mode prefix|boundary]

Exit codes: 0 append-only (or file absent at base), 1 violation, 2 usage error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass

EXIT_OK = 0
EXIT_APPEND_VIOLATION = 1
EXIT_USAGE_ERROR = 2

HEADING_PREFIX = "## "
MODE_PREFIX = "prefix"
MODE_BOUNDARY = "boundary"


def normalise_newlines(data: bytes) -> bytes:
    """Return data with CRLF and lone CR folded to LF."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def first_difference(base: bytes, head: bytes) -> int | None:
    """Return the offset where head stops matching base, or None when it does not."""
    old = normalise_newlines(base)
    new = normalise_newlines(head)
    limit = min(len(old), len(new))
    for index in range(limit):
        if old[index] != new[index]:
            return index
    if len(new) < len(old):
        return len(new)
    return None


def _split_lines(data: bytes) -> list[str]:
    return normalise_newlines(data).decode("utf-8", errors="surrogateescape").split("\n")


@dataclass(frozen=True)
class Insertion:
    """One contiguous block of new lines, and where it landed."""

    first_head_line: int
    lines: tuple[str, ...]
    base_cursor: int
    before_text: str | None

    @property
    def at_end(self) -> bool:
        """True when nothing but blank lines follows the block in the base copy."""
        return self.before_text is None

    @property
    def at_boundary(self) -> bool:
        """True when the next real line is an entry heading, or there is none.

        Blank lines are separators, not entry content, so a block that lands in
        a separator run (directly before a heading once the blank padding is
        skipped) is still at a boundary. A block that lands before a body line
        is inside an entry and is rejected.
        """
        if self.before_text is None:
            return True
        return self.before_text.startswith(HEADING_PREFIX)

    @property
    def is_blank_padding(self) -> bool:
        """True when the block contains only blank lines."""
        return all(item == "" for item in self.lines)

    def describe(self) -> str:
        """Return a one-line human readable position."""
        start = self.first_head_line + 1
        end = self.first_head_line + len(self.lines)
        where = "at end of file" if self.before_text is None else f"before {self.before_text[:60]}"
        return f"lines {start}-{end} ({len(self.lines)} line(s)) {where}"


def find_insertions(base: bytes | None, head: bytes) -> tuple[list[Insertion], bool]:
    """Locate inserted blocks and report whether the base survived intact.

    Returns (insertions, base_survived). base_survived is False when a base
    line was deleted, reordered or edited.
    """
    if base is None:
        return [], True

    base_lines = _split_lines(base)
    head_lines = _split_lines(head)

    insertions: list[Insertion] = []
    pending: list[str] = []
    pending_start = 0
    cursor = 0

    for index, line in enumerate(head_lines):
        if cursor < len(base_lines) and line == base_lines[cursor]:
            if pending:
                insertions.append(_make_insertion(pending, pending_start, cursor, base_lines))
                pending = []
            cursor += 1
        else:
            if not pending:
                pending_start = index
            pending.append(line)

    if pending:
        insertions.append(_make_insertion(pending, pending_start, cursor, base_lines))

    return insertions, cursor == len(base_lines)


def _next_real_line(base_lines: list[str], cursor: int) -> str | None:
    """Return the next non-blank base line at or after cursor, or None at the end."""
    for line in base_lines[cursor:]:
        if line != "":
            return line
    return None


def _make_insertion(
    lines: list[str], start: int, base_cursor: int, base_lines: list[str]
) -> Insertion:
    return Insertion(
        first_head_line=start,
        lines=tuple(lines),
        base_cursor=base_cursor,
        before_text=_next_real_line(base_lines, base_cursor),
    )


def is_append_only(base: bytes | None, head: bytes, mode: str = MODE_PREFIX) -> bool:
    """True when head only adds to base under the given mode."""
    if base is None:
        return True
    if mode == MODE_PREFIX:
        return normalise_newlines(head).startswith(normalise_newlines(base))
    if mode == MODE_BOUNDARY:
        insertions, survived = find_insertions(base, head)
        return survived and all(item.at_boundary for item in insertions)
    raise ValueError(f"unknown mode: {mode}")


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    # Justification: no shell, argv is a fixed tuple, and every variable value
    # is checked by _validated_ref/_validated_path before it reaches this call.
    return subprocess.run(("git", *args), capture_output=True, check=False)  # noqa: S603, S607


_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@{}^~+-]*$")


def _validated_ref(ref: str) -> str:
    """Return ref unchanged when it can only name a git revision."""
    if not _REF_PATTERN.fullmatch(ref):
        raise ValueError(
            f"Not a git ref: {ref!r}. Use a branch, tag or commit id such as origin/main."
        )
    return ref


def _validated_path(path: str) -> str:
    """Return path unchanged when it can only name a file inside the repository.

    A leading dash would be read as a git option and a ``..`` component would
    escape the repository, so both are refused instead of being passed on.
    """
    normalised = path.replace("\\", "/")
    parts = normalised.split("/")
    bad = (
        not normalised
        or normalised.startswith("/")
        or path.startswith("-")
        or any(part in ("", ".", "..") for part in parts)
        or any(ord(character) < 32 for character in path)
    )
    if bad:
        raise ValueError(f"Not a repository-relative file path: {path!r}.")
    return path


def exists_at(ref: str, path: str) -> bool:
    """True when path exists in the tree of ref."""
    return read_at(ref, path) is not None


def read_at(ref: str, path: str) -> bytes | None:
    """Return the raw bytes of path at ref, or None when it cannot be read."""
    completed = _git("show", f"{ref}:{path}")
    if completed.returncode != 0:
        return None
    return completed.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that a file only grew relative to a base ref.",
    )
    parser.add_argument("base_ref", help="Git ref to compare against, e.g. origin/main")
    parser.add_argument("path", help="Repository-relative path to check")
    parser.add_argument(
        "--mode",
        choices=(MODE_PREFIX, MODE_BOUNDARY),
        default=MODE_PREFIX,
        help="prefix: new content must start with old. boundary: insertions only at entry edges.",
    )
    args = parser.parse_args(argv)

    try:
        base_ref = _validated_ref(args.base_ref)
        log_path = _validated_path(args.path)
    except ValueError as error:
        parser.error(str(error))

    if not exists_at(base_ref, log_path):
        print(f"PASS: {log_path} does not exist at {base_ref}; nothing to preserve")
        return EXIT_OK

    base = read_at(base_ref, log_path)
    if base is None:
        print(f"ERROR: could not read {log_path} at {base_ref}")
        return EXIT_USAGE_ERROR

    head = read_at("HEAD", log_path)
    if head is None:
        print(f"FAIL: {log_path} was deleted since {base_ref}")
        print("The log is append-only: restore the file and add your entry at the end.")
        return EXIT_APPEND_VIOLATION

    if args.mode == MODE_BOUNDARY:
        insertions, survived = find_insertions(base, head)
        for item in insertions:
            marker = "ok" if item.at_boundary else "VIOLATION"
            print(f"  insertion {item.describe()} [{marker}]")
        if not survived:
            print(f"FAIL: {log_path} lost, reordered or edited an earlier line")
            print("The log is append-only: earlier entries must stay exactly as they were.")
            return EXIT_APPEND_VIOLATION
        stray = [item for item in insertions if not item.at_boundary]
        if stray:
            print(f"FAIL: {len(stray)} insertion(s) landed inside an existing entry")
            print("Insert new entries between entries or at the end of the file.")
            return EXIT_APPEND_VIOLATION
        print(f"PASS: {log_path} only gained whole entries since {base_ref}")
        return EXIT_OK

    if is_append_only(base, head, MODE_PREFIX):
        print(f"PASS: {log_path} only grew since {base_ref}")
        return EXIT_OK

    offset = first_difference(base, head)
    print(f"FAIL: {log_path} changed earlier content since {base_ref} (byte {offset})")
    print("The log is append-only: add new entries at the end and do not edit earlier lines.")
    return EXIT_APPEND_VIOLATION


if __name__ == "__main__":
    sys.exit(main())
