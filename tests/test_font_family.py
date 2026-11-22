"""Strict font family test for Once UI.

The fonts must actually resolve through Qt: the display face must report
"Anton" and the UI face must report "Inter". The check runs in a fresh
subprocess because creating and destroying QApplication inside pytest can
segfault on this machine; a non-zero exit is a test failure, never a skip.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_PROBE = r"""
import sys
from PySide6.QtGui import QFont, QFontInfo
from PySide6.QtWidgets import QApplication

from ui.fonts import load_fonts
from ui.styles import DISPLAY_FONT, UI_FONT

app = QApplication.instance() or QApplication([sys.argv[0]])
registered = load_fonts()
print("registered families:", list(registered))

problems = []
for label, family in (("display", DISPLAY_FONT), ("ui", UI_FONT)):
    font = QFont(family)
    info = QFontInfo(font)
    print(f"{label}: requested={family!r} resolved={info.family()!r}")
    if info.family() != family:
        problems.append(f"{label} font resolved to {info.family()!r}, expected {family!r}")

if problems:
    for problem in problems:
        print("PROBLEM:", problem)
    raise SystemExit(1)
raise SystemExit(0)
"""


def test_display_and_ui_fonts_resolve_strictly() -> None:
    """Fail (never skip) unless Anton and Inter are the resolved families."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    print(result.stdout)
    print(result.stderr)
    assert result.returncode == 0, (
        "Font resolution failed.\n"
        f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
