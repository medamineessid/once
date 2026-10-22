"""Shared pytest fixtures.

Every fixture here works inside pytest's ``tmp_path``; none reads or writes a
real user folder (safety invariant S12).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

# Run Qt headlessly for the whole test session unless the caller chose another
# platform explicitly. This must be set before PySide6 is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIXED_MTIME_NS = 1_700_000_000_000_000_000

DEFAULT_TREE: Mapping[str, str | None] = {
    "alpha.txt": "alpha\n",
    "beta.txt": "beta\n",
    "empty_dir": None,
    "sub": None,
    "sub/nested.txt": "nested\n",
}


@pytest.fixture
def make_tree(tmp_path: Path) -> Callable[..., Path]:
    """Return a factory that builds a deterministic test directory tree."""

    def _make_tree(
        structure: Mapping[str, str | None] | None = None,
        root: Path | None = None,
    ) -> Path:
        tree_root = root if root is not None else tmp_path / "tree"
        tree_root.mkdir(parents=True, exist_ok=True)
        entries = structure if structure is not None else DEFAULT_TREE
        for relative in sorted(entries):
            content = entries[relative]
            target = tree_root / relative
            if content is None:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            os.utime(target, ns=(FIXED_MTIME_NS, FIXED_MTIME_NS))

        # Stamp directories last, deepest first, so later writes do not leave
        # parent mtimes depending on the wall clock.
        directories = sorted(
            (path for path in tree_root.rglob("*") if path.is_dir()),
            reverse=True,
        )
        for directory in directories:
            os.utime(directory, ns=(FIXED_MTIME_NS, FIXED_MTIME_NS))
        os.utime(tree_root, ns=(FIXED_MTIME_NS, FIXED_MTIME_NS))
        return tree_root

    return _make_tree


@pytest.fixture
def snapshot_tree() -> Callable[[Path], tuple[tuple[str, int, int, bool], ...]]:
    """Return a factory that snapshots paths, sizes, mtimes and directory flags.

    Entries are sorted by POSIX-style relative path, so comparing two snapshots
    detects created, removed, renamed or modified entries. The root itself is
    not included.
    """

    def _snapshot(root: Path) -> tuple[tuple[str, int, int, bool], ...]:
        entries: list[tuple[str, int, int, bool]] = []
        for current, directory_names, file_names in os.walk(root, followlinks=False):
            current_path = Path(current)
            for name in sorted([*directory_names, *file_names]):
                path = current_path / name
                stat_result = path.stat(follow_symlinks=False)
                relative = path.relative_to(root).as_posix()
                entries.append(
                    (relative, stat_result.st_size, stat_result.st_mtime_ns, path.is_dir())
                )
        entries.sort(key=lambda entry: entry[0])
        return tuple(entries)

    return _snapshot


@pytest.fixture
def app_data_dir(tmp_path: Path) -> Path:
    """Provide an isolated stand-in for ``%LOCALAPPDATA%/Once``."""
    directory = tmp_path / "appdata" / "Once"
    directory.mkdir(parents=True)
    return directory
