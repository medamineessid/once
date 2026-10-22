from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import pytest

from engine.errors import PlanError
from engine.filters import by_date, by_extension, by_name
from engine.scanner import scan_folder


def test_scan_empty_folder(make_tree):
    root = make_tree({})

    result = scan_folder(root)

    assert result.entries == ()
    assert result.skipped == ()


def test_scan_mixed_files_and_directories(make_tree):
    root = make_tree(
        {
            "alpha.txt": "a\n",
            "beta.JPG": "b\n",
            "inner": None,
            "inner/nested.txt": "n\n",
        }
    )

    result = scan_folder(root)

    assert {entry.name for entry in result.entries} == {"alpha.txt", "beta.JPG"}
    assert any("Folder" in item.reason for item in result.skipped)


def test_scan_hides_hidden_files_by_default_but_can_include_them(make_tree):
    root = make_tree({".hidden.txt": "hidden\n", "visible.txt": "visible\n"})

    default = scan_folder(root)
    with_hidden = scan_folder(root, include_hidden=True)

    assert {entry.name for entry in default.entries} == {"visible.txt"}
    assert {entry.name for entry in with_hidden.entries} == {".hidden.txt", "visible.txt"}


def test_scan_skips_symlink_when_supported(make_tree):
    root = make_tree({"real.txt": "ok\n"})
    link = root / "link.txt"
    try:
        link.symlink_to(root / "real.txt")
    except OSError, NotImplementedError:
        pytest.skip("symbolic links are not available on this machine")

    result = scan_folder(root)

    assert "link.txt" not in {entry.name for entry in result.entries}
    assert any("Shortcut or link" in item.reason for item in result.skipped)


def test_scan_missing_directory_raises_plan_error(make_tree):
    missing = make_tree() / "does-not-exist"

    with pytest.raises(PlanError, match=r"missing|not a directory|unreadable"):
        scan_folder(missing)


def test_scan_handles_unicode_names_and_suffix_rules(make_tree):
    root = make_tree({"é.txt": "é\n", "archive.tar.gz": "x\n", ".gitignore": "# comment\n"})

    result = scan_folder(root, include_hidden=True)
    names = {entry.name: entry for entry in result.entries}

    assert names["é.txt"].suffix == ".txt"
    assert names["archive.tar.gz"].suffix == ".gz"
    assert names[".gitignore"].suffix == ""
    assert names[".gitignore"].stem == ".gitignore"


def test_filters_work_on_extensions_names_and_dates(make_tree):
    root = make_tree(
        {
            "photo.jpg": "x\n",
            "photo.JPEG": "x\n",
            "notes.txt": "x\n",
            "archive.tar.gz": "x\n",
            "old.csv": "x\n",
        }
    )

    photo_files = by_extension(scan_folder(root, include_hidden=True).entries, {".jpg", ".jpeg"})
    assert {entry.name for entry in photo_files} == {"photo.jpg", "photo.JPEG"}

    named = by_name(scan_folder(root, include_hidden=True).entries, contains="photo")
    assert {entry.name for entry in named} == {"photo.jpg", "photo.JPEG"}

    today = date.today()
    timestamp = int(datetime.now().timestamp() * 1_000_000_000)
    for path in root.iterdir():
        os.utime(path, ns=(timestamp, timestamp))

    dates = by_date(
        scan_folder(root, include_hidden=True).entries,
        field="modified",
        start=today,
        end=today + timedelta(days=1),
    )
    assert dates


def test_scan_is_deterministic_and_read_only(make_tree, snapshot_tree):
    root = make_tree({"zeta.txt": "z\n", "alpha.txt": "a\n", "sub": None, "sub/deep.txt": "d\n"})

    before = snapshot_tree(root)
    first = scan_folder(root)
    after = snapshot_tree(root)
    second = scan_folder(root)

    assert before == after
    assert first.entries == second.entries
    assert first.skipped == second.skipped
