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
BLOCKED_IDS = frozenset({8, 9, 10, 11, 12, 13, 17, 18})
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
        path = ROOT / "tasks" / f"TASK-{number:03d}.md"
        assert path.exists(), f"{path.name} is missing"
        text = _read(path)
        assert text.startswith(f"# TASK-{number:03d} — "), f"{path.name} has no title"
        for heading in REQUIRED_HEADINGS:
            assert heading in text, f"{path.name} is missing {heading}"
        assert "Label: `lane/" in text, f"{path.name} has no lane label"
        assert "Size: `" in text, f"{path.name} has no size"
        forbidden = _section(text, "## Files forbidden")
        assert "engine/" in forbidden, f"{path.name} does not forbid engine/"
        assert "docs/ai_engineering_log.md" in forbidden, (
            f"{path.name} does not forbid the engineering log"
        )
        acceptance = _section(text, "## Acceptance commands (run yourself)")
        assert "ruff check ." in acceptance, f"{path.name} has no ruff check"
        assert "ruff format --check ." in acceptance, f"{path.name} has no ruff format check"


def test_blocked_briefs_name_their_blocker() -> None:
    for number in BRIEF_IDS:
        path = ROOT / "tasks" / f"TASK-{number:03d}.md"
        text = _read(path)
        if number in BLOCKED_IDS:
            assert "## Status: BLOCKED" in text, f"{path.name} must be BLOCKED"
            assert "Blocked by TASK-" in text, f"{path.name} has no blocker"
        else:
            assert "## Status: BLOCKED" not in text, (
                f"{path.name} is marked BLOCKED without a dependency"
            )


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
