"""The documentation index keeps the living set honest.

Every document the index lists must exist and still carry its three-line header
(Status, Last verified, Owner), every local link in the README must resolve, and
everything under ``docs/archive`` must say it is historical. A stale page fails
here instead of misleading a reader.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "README.md"
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.M)
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
HEADER_FIELDS = ("Status:", "Last verified:", "Owner:")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rows() -> list[str]:
    return ROW.findall(_read(INDEX))


def test_the_index_lists_the_core_documents() -> None:
    rows = _rows()
    assert len(rows) >= 25, f"the index lists only {len(rows)} documents"
    for name in ("docs/STATE.md", "docs/PLAN.md", "docs/UI_DEFECTS.md", "README.md"):
        assert name in rows, f"the index does not list {name}"


def test_every_indexed_document_exists_and_keeps_its_header() -> None:
    missing: list[str] = []
    unheadered: list[str] = []
    for name in _rows():
        path = ROOT / name
        if not path.exists():
            missing.append(name)
            continue
        head = "\n".join(_read(path).splitlines()[:12])
        absent = [field for field in HEADER_FIELDS if field not in head]
        unheadered.extend(f"{name} has no {field!r}" for field in absent)
    assert not missing, f"the index lists documents that do not exist: {missing}"
    assert not unheadered, f"indexed documents lost their header: {unheadered}"


def test_readme_local_links_resolve() -> None:
    broken: list[str] = []
    for target in LINK.findall(_read(ROOT / "README.md")):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        clean = target.split("#", 1)[0]
        if clean and not (ROOT / clean).exists():
            broken.append(target)
    assert not broken, f"README links that do not resolve: {broken}"


def test_archive_files_say_they_are_historical() -> None:
    archived = sorted((ROOT / "docs" / "archive").rglob("*.md"))
    assert archived, "docs/archive has no markdown files"
    for path in archived:
        assert "Status: Historical" in _read(path), f"{path.name} has no historical note"


def test_the_naming_rule_is_written_down() -> None:
    text = _read(INDEX)
    assert "lowercase-with-hyphens" in text
    assert "UPPERCASE" in text
