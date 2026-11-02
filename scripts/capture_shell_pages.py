"""Capture every reachable shell page at several window sizes.

Runs the real shell construction path (the same wiring app.py uses for
--shell) under the offscreen Qt platform, saves PNGs with stable file names
"<width>x<height>-<page>.png", and prints the saved paths. Used by
scripts/capture_screenshots.ps1 (P1.6).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(REPO))

from PySide6.QtWidgets import QApplication  # noqa: E402

from controller.recording import RecordingService  # noqa: E402
from controller.service import WorkflowService  # noqa: E402
from ui.shell import MainWindow, ShellPages  # noqa: E402

SIZES = [(1280, 800), (1366, 768), (1920, 1080)]
PAGES = [
    ("home", ShellPages.HOME),
    ("my-automations", ShellPages.MY_AUTOMATIONS),
    ("activity", ShellPages.ACTIVITY),
    ("settings", ShellPages.SETTINGS),
    ("create-automation", ShellPages.CREATE),
    ("editor", ShellPages.EDITOR),
]
# main() appends the palette-less captures (recording mode, opened review),
# so the caller can assert the full expected count without re-running logic.
EXPECTED_PAGE_COUNT = len(PAGES) + 2


def settle(app: QApplication) -> None:
    for _ in range(8):
        app.processEvents()
        app.sendPostedEvents()


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "docs/screenshots/latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(tempfile.mkdtemp(prefix="once-shots-"))

    app = QApplication(sys.argv)
    service = WorkflowService.for_app_data(data_dir)
    recording_service = RecordingService(data_dir / "recordings")
    window = MainWindow(
        service,
        recording_service,
        verifier_config=None,
        verifier_note=None,
        app_data_dir=data_dir,
    )
    window.show()
    settle(app)

    # The recording flow is the create page in its dedicated recording mode
    # (reached exactly the way Home's record card does it).
    PAGES.append(("recording", None))

    # Give the review capture something real to show: the demo workflow opened
    # through the same path the sidebar list uses.
    saved_path = service.save(service.demo_workflow())
    window._open_workflow(saved_path)
    settle(app)
    PAGES.append(("review", None))

    written: list[Path] = []
    for width, height in SIZES:
        for page_name, page in PAGES:
            if page is None:
                if page_name == "review":
                    window._open_workflow(saved_path)
                elif page_name == "recording":
                    window._show_recording()
            elif page_name == "create-automation":
                # Restore the typed-description mode explicitly: a later
                # recording capture must not leak its page state here.
                window._show_create_automation()
            elif page_name == "editor":
                # Fresh definition through the shell's own entry point, so the
                # canvas and the A2a inspector capture in their real state.
                window._show_editor()
            else:
                window._show_page(page)
            settle(app)
            window.resize(width, height)
            settle(app)
            png = window.grab()
            target = out_dir / f"{width}x{height}-{page_name}.png"
            if not png.save(str(target), "PNG"):
                raise SystemExit(f"capture failed: {target}")
            written.append(target)

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
