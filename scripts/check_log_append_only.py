"""Fail when a tracked file changed anywhere except at its end.

The previous gate used `git diff --numstat`, which counts a deletion whenever
the base copy of a file ends without a trailing newline and the new copy adds
one. That produced a false positive against `main` for
`docs/ai_engineering_log.md`: the only "deleted" line was the final line,
unchanged in content, followed by a new newline.

This check compares the two copies directly instead of trusting a line diff.
The new content must start with the old content, byte for byte, after CRLF
normalisation. Adding a trailing newline or appending new lines passes; editing,
reordering or deleting anything that came before fails.

Usage:
    python scripts/check_log_append_only.py <base-ref> <path>

Exit codes: 0 append-only (or file absent at base), 1 violation, 2 usage error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

EXIT_OK = 0
EXIT_APPEND_VIOLATION = 1
EXIT_USAGE_ERROR = 2


def normalise_newlines(data: bytes) -> bytes:
    """Return data with CRLF and lone CR folded to LF."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def is_append_only(base: bytes | None, head: bytes) -> bool:
    """True when head keeps every byte of base and only adds to the end."""
    if base is None:
        return True
    return normalise_newlines(head).startswith(normalise_newlines(base))


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


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    # Justification: argv is fixed by this module, no shell, and the only
    # variable inputs are the ref and path that git itself validates.
    return subprocess.run(("git", *args), capture_output=True, check=False)  # noqa: S603, S607


def exists_at(ref: str, path: str) -> bool:
    """True when path exists in the tree of ref."""
    return _git("cat-file", "-e", f"{ref}:{path}").returncode == 0


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
    args = parser.parse_args(argv)

    if not exists_at(args.base_ref, args.path):
        print(f"PASS: {args.path} does not exist at {args.base_ref}; nothing to preserve")
        return EXIT_OK

    base = read_at(args.base_ref, args.path)
    if base is None:
        print(f"ERROR: could not read {args.path} at {args.base_ref}")
        return EXIT_USAGE_ERROR

    head = read_at("HEAD", args.path)
    if head is None:
        print(f"FAIL: {args.path} was deleted since {args.base_ref}")
        print("The log is append-only: restore the file and add your entry at the end.")
        return EXIT_APPEND_VIOLATION

    if is_append_only(base, head):
        print(f"PASS: {args.path} only grew since {args.base_ref}")
        return EXIT_OK

    offset = first_difference(base, head)
    print(f"FAIL: {args.path} changed earlier content since {args.base_ref} (byte {offset})")
    print("The log is append-only: add new entries at the end and do not edit earlier lines.")
    return EXIT_APPEND_VIOLATION


if __name__ == "__main__":
    sys.exit(main())
