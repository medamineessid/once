"""Capture real Once windows for visual review.

Usage: python scripts/capture_ui_shots.py <output-dir>

Set ONCE_CAPTURE_LOCALAPPDATA to a staging LOCALAPPDATA that contains Once/.
The real user profile is never read; the caller must prepare the staging copy.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtTest import QTest

from app import build_window
from ui.components.delete_confirm import DeleteConfirmDialog
from ui.shell import ShellPages

REPO_ROOT = Path(__file__).resolve().parents[1]
SHOTS_ROOT = REPO_ROOT / "shots"


def resolve_output_dir(raw: str) -> Path:
    """Return the requested capture folder, or refuse it.

    Captures are written next to the repository's other screenshots. Accepting
    only a folder inside ``shots/`` or the system temp folder keeps a mistyped
    or hostile argument from creating or filling a folder elsewhere.
    """
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    for root in (SHOTS_ROOT.resolve(), Path(tempfile.gettempdir()).resolve()):
        if resolved == root or root in resolved.parents:
            return resolved
    raise ValueError(f"Refusing to write captures outside shots/ or the temp folder: {resolved}")


def save_window(window, path: Path) -> None:
    window.raise_()
    window.activateWindow()
    QTest.qWait(450)
    pixmap = window.screen().grabWindow(int(window.winId()))
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"Could not save {path}")
    print(f"{path.name}: {pixmap.width()}x{pixmap.height()}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: capture_ui_shots.py <output-dir>")
        return 2
    try:
        out = resolve_output_dir(sys.argv[1])
    except ValueError as error:
        print(error)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    app, window, service, _recording = build_window(["--shell"])
    window.resize(1280, 820)
    window.show()
    QTest.qWait(900)

    window._show_page(ShellPages.HOME)
    save_window(window, out / "home.png")

    window._show_page(ShellPages.MY_AUTOMATIONS)
    save_window(window, out / "my-automations.png")

    saved = tuple(service.list_saved())
    workflow = service.load(saved[0]) if saved else None
    if saved and workflow is not None:
        window._open_workflow(saved[0])
        save_window(window, out / "automation-details.png")
        window._open_review_workflow_editor(workflow)
        save_window(window, out / "editor.png")

    window._show_page(ShellPages.ACTIVITY)
    failed = next(
        (
            run
            for run in service.history()
            if getattr(getattr(run, "status", None), "value", "") == "FAILED"
        ),
        None,
    )
    if failed is not None:
        window.activity_page.select_run(failed.run_id)
    save_window(window, out / "activity.png")
    if failed is not None:
        save_window(window, out / "failed-run.png")

    window._show_page(ShellPages.SETTINGS)
    save_window(window, out / "settings.png")

    window._show_page(ShellPages.MY_AUTOMATIONS)
    dialog = DeleteConfirmDialog(
        "Delete 'Recorded task draft'? This cannot be undone.", parent=window
    )
    dialog.show()
    QTest.qWait(300)
    save_window(dialog, out / "dialog.png")
    dialog.close()

    window.resize(960, 600)
    window._show_page(ShellPages.HOME)
    save_window(window, out / "home-minimum.png")

    window.resize(1600, 1000)
    save_window(window, out / "home-large.png")

    window.close()
    service.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
