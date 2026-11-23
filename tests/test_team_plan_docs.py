"""Tests for the team-plan documentation PR.

These checks keep the plan, briefs, lane permissions and review prompt from
drifting apart. They are documentation tests: they do not claim any product
capability is working.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "PLAN.md"
BRIEF_IDS = tuple(range(7, 19))
UI_BRIEF_IDS = tuple(range(8, 14))
REQUIRED_HEADINGS = (
    "## Goal",
    "## Files allowed",
    "## Files forbidden",
    "## Acceptance commands (run yourself)",
    "## Screenshots",
    "## Out of scope",
    "## Notes",
)
OWNER_ONLY = (
    "/engine/ @medamineessid",
    "/integrations/ @medamineessid",
    "/recorder/ @medamineessid",
    "/storage/ @medamineessid",
    "/controller/ @medamineessid",
    "/docs/ai_engineering_log.md @medamineessid",
    "/docs/STATE.md @medamineessid",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading) :]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _brief(number: int) -> str:
    return _read(ROOT / "tasks" / f"TASK-{number:03d}.md")


def test_plan_exists_and_is_under_120_lines() -> None:
    assert PLAN.exists(), "docs/PLAN.md is missing"
    lines = _read(PLAN).splitlines()
    assert len(lines) <= 120, f"docs/PLAN.md is {len(lines)} lines (limit 120)"


def test_readme_links_the_plan_from_start_here() -> None:
    readme = _read(ROOT / "README.md")
    assert "## Start here" in readme, "README has no Start here section"
    section = _section(readme, "## Start here")
    assert "`docs/PLAN.md`" in section, "Start here does not link docs/PLAN.md"


def test_all_team_briefs_follow_the_template() -> None:
    for number in BRIEF_IDS:
        text = _brief(number)
        path_name = f"TASK-{number:03d}.md"
        assert text.startswith(f"# TASK-{number:03d} — "), f"{path_name} has no title"
        for heading in REQUIRED_HEADINGS:
            assert heading in text, f"{path_name} is missing {heading}"
        assert "Label: `lane/" in text, f"{path_name} has no lane label"
        assert "Size: `" in text, f"{path_name} has no size"
        forbidden = _section(text, "## Files forbidden")
        assert "engine/" in forbidden, f"{path_name} does not forbid engine/"
        assert "docs/ai_engineering_log.md" in forbidden, (
            f"{path_name} does not forbid the engineering log"
        )
        acceptance = _section(text, "## Acceptance commands (run yourself)")
        assert "ruff check ." in acceptance, f"{path_name} has no ruff check"
        assert "ruff format --check ." in acceptance, f"{path_name} has no ruff format check"


def test_no_team_brief_is_blocked() -> None:
    for number in BRIEF_IDS:
        text = _brief(number)
        path_name = f"TASK-{number:03d}.md"
        assert "## Status: BLOCKED" not in text, f"{path_name} is still BLOCKED"
        assert "Blocked by TASK-" not in text, f"{path_name} still names a blocker"
        assert "(BLOCKED)" not in text.splitlines()[0], (
            f"{path_name} still says BLOCKED in its title"
        )


def test_ui_briefs_are_unblocked_sample_fed_and_audit_ready() -> None:
    for number in UI_BRIEF_IDS:
        text = _brief(number)
        path_name = f"TASK-{number:03d}.md"
        assert "## Status: BLOCKED" not in text, f"{path_name} must be startable"
        assert "Blocked by TASK-007" not in text, f"{path_name} is gated on the audit"
        flat = " ".join(text.split())
        assert "scripts/ui_audit.py" in text, f"{path_name} has no post-audit command"
        assert "TASK-007 has landed" in flat, f"{path_name} has no audit timing note"
        assert "docs/ui-reference/" in text, f"{path_name} has no reference captures"
        assert "Screenshots before and after, app window only, one sentence per image" in text, (
            f"{path_name} has no screenshot rule"
        )
        allowed = _section(text, "## Files allowed")
        assert "ui/styles/__init__.py" in allowed, f"{path_name} does not allow styles explicitly"
        if number in (12, 13):
            assert "tests/fixtures/" in allowed, f"{path_name} has no sample-data path"


def test_ui_briefs_cover_every_current_defect_once() -> None:
    groups = {8: ("V1", "V2", "V4"), 9: ("V3", "V5", "V8"), 10: ("V6", "V7", "V9", "V10")}
    all_ids: list[str] = []
    for number, expected in groups.items():
        text = _brief(number)
        for defect in expected:
            assert f"{defect} " in text or f"{defect}\n" in text or f"{defect}," in text, (
                f"TASK-{number:03d}.md does not name {defect}"
            )
        all_ids.extend(expected)
    assert sorted(all_ids, key=lambda item: int(item[1:])) == [f"V{i}" for i in range(1, 11)]


def test_current_defect_doc_uses_v_numbers_and_marks_historical_d_items() -> None:
    defects = _read(ROOT / "docs" / "UI_DEFECTS.md")
    for number in range(1, 11):
        assert f"### V{number} —" in defects, f"UI_DEFECTS.md has no V{number} entry"
    assert "## Old D1\u2013D10 status" in defects, "old D-items are not marked historical"
    for number in range(1, 11):
        assert f"D{number}" in defects, f"UI_DEFECTS.md omits old D{number} status"
    assert defects.count(".py:") >= 10, "old D-status table needs file:line evidence"
    audit = _read(ROOT / "docs" / "UX_AUDIT.md")
    assert "Historical" in audit.splitlines()[2], "UX_AUDIT.md has no historical note"
    assert "docs/UI_DEFECTS.md" in audit[:600], "UX_AUDIT.md does not point to V-defects"


def test_ui_reference_captures_are_app_window_size_and_under_300kb() -> None:
    folder = ROOT / "docs" / "ui-reference"
    readme = _read(folder / "README.md")
    assert "repo captures" in readme, "provenance note is missing"
    captures = sorted(folder.glob("*.png"))
    assert len(captures) == 4, f"expected 4 captures, found {len(captures)}"
    for capture in captures:
        size = capture.stat().st_size
        assert size < 300_000, f"{capture.name} is {size} bytes (limit 300000)"
        with capture.open("rb") as handle:
            assert handle.read(8) == b"\x89PNG\r\n\x1a\n", f"{capture.name} is not a PNG"
    defects = _read(ROOT / "docs" / "UI_DEFECTS.md")
    assert "docs/ui-reference/" in defects, "defect list has no capture references"


def test_plan_has_the_demo_finish_line_and_lane_a_changes() -> None:
    plan = " ".join(_read(PLAN).split())
    for phrase in (
        "record once",
        "more tabs",
        "lower in the list",
        "replay finds the right thing or asks",
        "never",
        "clicks wrong",
        "A5 Chrome case",
        "DevTools tab and page APIs",
        "existing resolver",
        "stretch goal",
        "standing duty",
        "A2",
        "A4",
        "V1\u2013V10",
    ):
        assert phrase in plan, f"PLAN.md is missing {phrase!r}"


def test_plan_has_week_zero_and_the_recurring_rhythm() -> None:
    plan = " ".join(_read(PLAN).split())
    for phrase in (
        "Week 0",
        "protect `main`",
        "auto-delete merged branches",
        "remove SonarCloud",
        "Kickoff call",
        "gets the app running",
        "Daily 3-line update",
        "done, next, stuck",
        "Friday integration",
        "demo script on a clean copy",
        "list what",
        "Explain-back",
        "5 lines",
        "out loud",
        "Peer review",
        "lane B and C read each other's PRs for clarity",
        "the owner merges",
    ):
        assert phrase in plan, f"PLAN.md is missing {phrase!r}"


def test_docs_versus_code_rule_replaces_state_drift_rule() -> None:
    for path in (PLAN, ROOT / "docs" / "COLLABORATOR.md", ROOT / "docs" / "REVIEW_PROMPT.md"):
        text = _read(path)
        lower = text.lower()
        assert "docs-versus-code rule" in lower, f"{path.name} has no docs-versus-code rule"
        assert "state drift rule" not in lower, f"{path.name} still has the old rule name"
        assert "re-read repo state before acting" in lower, f"{path.name} has no session rule"


def test_codeowners_records_owner_only_paths_and_lane_notes() -> None:
    codeowners = _read(ROOT / ".github" / "CODEOWNERS")
    for line in OWNER_ONLY:
        assert line in codeowners, f"CODEOWNERS is missing {line}"
    assert "Lane B may edit ui/" in codeowners
    assert "Lane C may edit tests/" in codeowners


def test_review_prompt_has_the_three_verdicts() -> None:
    prompt = _read(ROOT / "docs" / "REVIEW_PROMPT.md")
    for verdict in ("APPROVE", "REQUEST CHANGES", "ESCALATE"):
        assert verdict in prompt, f"REVIEW_PROMPT.md is missing {verdict}"
    assert "Could not verify" in prompt
