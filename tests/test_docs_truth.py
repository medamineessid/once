"""Small documentation checks for flags the README tells users to run."""

from __future__ import annotations

from pathlib import Path


def test_readme_names_the_real_classic_window_flag() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "--classic" in readme
    assert "--legacy" not in readme
