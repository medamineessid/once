"""Tests for the documentation gate.

Every file a new contributor is told to find should exist and be reachable from
the README, and the curated pages should respect their line limits. The checks
live here so a doc-only PR keeps these constraints honest.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
START_HERE_LINKS = (
    ("CONTEXT.md", "docs/CONTEXT.md"),
    ("STATE.md", "docs/STATE.md"),
    ("decisions.md", "docs/decisions.md"),
    ("AGENTS.md", "AGENTS.md"),
    ("WORKFLOW.md", "docs/WORKFLOW.md"),
    ("COLLABORATOR.md", "docs/COLLABORATOR.md"),
)
STATE_LAST_UPDATED_RE = re.compile(r"^## Last updated\s*$", re.M)
DECISION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
CONTEXT_MAX = 100
STATE_MAX = 80


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_start_here_links_exist() -> None:
    lines = [line.strip() for line in _read(ROOT / "README.md").splitlines()]
    missing: list[str] = []
    for label, target in START_HERE_LINKS:
        if not (ROOT / target).exists():
            missing.append(f"{target} is missing")
            continue
        if not any(f"`{label}`" in line or f"`{target}`" in line for line in lines):
            missing.append(f"README does not link `{target}`")
    assert not missing, f"README does not link every Start here file: {missing}"


def test_state_has_a_last_updated_line() -> None:
    state = ROOT / "docs" / "STATE.md"
    assert state.exists(), "docs/STATE.md is missing"
    assert STATE_LAST_UPDATED_RE.search(_read(state)), (
        "docs/STATE.md has no '## Last updated' heading"
    )


def test_context_and_state_are_under_their_line_limits() -> None:
    context = ROOT / "docs" / "CONTEXT.md"
    state = ROOT / "docs" / "STATE.md"
    if not context.exists():
        pytest.skip("docs/CONTEXT.md not present yet")
    if not state.exists():
        pytest.skip("docs/STATE.md not present yet")
    context_lines = _read(context).splitlines()
    state_lines = _read(state).splitlines()
    assert len(context_lines) <= CONTEXT_MAX, (
        f"docs/CONTEXT.md is {len(context_lines)} lines (limit {CONTEXT_MAX})"
    )
    assert len(state_lines) <= STATE_MAX, (
        f"docs/STATE.md is {len(state_lines)} lines (limit {STATE_MAX})"
    )


def test_decisions_blocks_have_dated_heading_and_content() -> None:
    decisions = ROOT / "docs" / "decisions.md"
    assert decisions.exists(), "docs/decisions.md is missing"
    text = _read(decisions)
    headings = DECISION_HEADING_RE.findall(text)
    assert headings, "docs/decisions.md has no decision blocks"
    for heading in headings:
        assert heading.startswith(("2026-", "2025-", "2024-")), (
            f"docs/decisions.md block heading must be dated: {heading!r}"
        )
    bodies = re.split(r"^##\s+.+?$", text, flags=re.M)[1:]
    for body in bodies:
        assert body.strip(), "docs/decisions.md decision block must have content"
