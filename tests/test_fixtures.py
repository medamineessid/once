"""Tests for the shared test fixtures and their tmp_path isolation (S12)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

FIXED_MTIME_NS = 1_700_000_000_000_000_000


def test_S12_fixtures_stay_inside_tmp_path(
    tmp_path: Path,
    make_tree: Callable[..., Path],
    snapshot_tree: Callable[[Path], tuple[tuple[str, int, int, bool], ...]],
    app_data_dir: Path,
) -> None:
    root = make_tree({"a.txt": "a\n"})

    assert root.resolve().is_relative_to(tmp_path.resolve())
    assert app_data_dir.resolve().is_relative_to(tmp_path.resolve())

    snapshot = snapshot_tree(root)
    assert snapshot == (("a.txt", 2, FIXED_MTIME_NS, False),)


def test_make_tree_builds_default_tree_deterministically(
    make_tree: Callable[..., Path],
    snapshot_tree: Callable[[Path], tuple[tuple[str, int, int, bool], ...]],
) -> None:
    root = make_tree()

    assert snapshot_tree(root) == snapshot_tree(root)
    assert [entry[0] for entry in snapshot_tree(root)] == [
        "alpha.txt",
        "beta.txt",
        "empty_dir",
        "sub",
        "sub/nested.txt",
    ]
