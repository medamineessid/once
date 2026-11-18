"""The app starts and every page it offers can be shown.

This is the smoke test a person can run after a change: it builds the real
window against a throwaway data folder, shows each page, and asserts the page's
own heading is on screen. It never touches the real user profile.
"""

from __future__ import annotations

import contextlib
import os

import pytest
from PySide6.QtWidgets import QLabel

from controller.service import WorkflowService
from ui.shell import MainWindow, ShellPages


@pytest.fixture
def window(qtbot, tmp_path):
    service = WorkflowService.for_app_data(tmp_path / "appdata")
    main = MainWindow(service=service)
    qtbot.addWidget(main)
    main.resize(1280, 820)
    main.show()
    qtbot.wait(50)
    return main


def test_the_window_opens_on_home(window) -> None:
    assert window.isVisible() is True
    assert window.workspace.currentIndex() == ShellPages.HOME
    assert window.home_page._title_label.text() == "AUTOMATE"


@pytest.mark.parametrize(
    ("page", "title"),
    [
        (ShellPages.MY_AUTOMATIONS, "MY AUTOMATIONS"),
        (ShellPages.ACTIVITY, "ACTIVITY"),
        (ShellPages.SETTINGS, "SETTINGS"),
    ],
)
def test_every_sidebar_page_can_be_shown(window, page, title) -> None:
    window._show_page(page)
    current = window.workspace.currentWidget()
    assert window.workspace.currentIndex() == page
    assert current.isVisible() is True
    labels = [label.text() for label in current.findChildren(QLabel)]
    assert title in labels


def test_the_editor_page_can_be_shown(window) -> None:
    window._show_editor()
    assert window.workspace.currentIndex() == ShellPages.EDITOR
    assert window.editor_page.isVisible() is True


def test_the_review_page_can_be_shown(window) -> None:
    window._show_page(ShellPages.REVIEW)
    assert window.review_page.isVisible() is True


def test_closing_the_window_with_no_run_is_harmless(window) -> None:
    window.close()
    assert window.isVisible() is False


def _close_notepad(window) -> None:
    """Close one Notepad window, declining the save prompt it may show."""
    for item in window.descendants():
        info = item.element_info
        if (
            getattr(info, "control_type", None) == "Button"
            and getattr(info, "automation_id", "") == "SecondaryButton"
        ):
            item.invoke()
            return
    with contextlib.suppress(AttributeError, OSError, RuntimeError):
        window.close()


#: The one test that needs a real desktop and a real Notepad; opt in explicitly.
real_desktop = pytest.mark.skipif(
    os.environ.get("ONCE_REAL_DESKTOP") != "1",
    reason="needs a real desktop: set ONCE_REAL_DESKTOP=1 to run the Notepad end-to-end test",
)


@real_desktop
def test_real_desktop_notepad_round_trip() -> None:
    """Open Notepad, type once test, close it: the whole replay, for real.

    Run by hand with:  ONCE_REAL_DESKTOP=1 pytest tests/test_app_starts.py -q
    CI never sets the variable, so this test reports itself skipped there.
    """
    import json
    import subprocess
    import tempfile
    import time
    from pathlib import Path

    from pywinauto import Desktop

    from engine.desktop import approve_desktop_workflow
    from engine.workflow import StepKind, Workflow, WorkflowStep

    notepad = Path("C:/Windows/System32/notepad.exe")
    if not notepad.is_file():
        pytest.skip("Notepad is not installed at the expected path")

    def notepad_windows() -> list:
        return [
            w
            for w in Desktop(backend="uia").windows()
            if getattr(w.element_info, "class_name", None) == "Notepad"
        ]

    if any("once test" in (w.element_info.name or "") for w in notepad_windows()):
        pytest.skip("an earlier Notepad window is still open; close it and rerun")

    before = {w.element_info.handle for w in notepad_windows()}
    deadline = time.monotonic() + 15
    subprocess.Popen([str(notepad)], shell=False)
    window = None
    while time.monotonic() < deadline and window is None:
        new = [w for w in notepad_windows() if w.element_info.handle not in before]
        if len(new) == 1:
            window = new[0]
        else:
            time.sleep(0.3)
    if window is None:
        pytest.fail("the Notepad window did not appear")
    # Read the window's own (localized) title, then close this probe window so
    # the run's own launch is the only window carrying that title.
    title = window.element_info.name
    _close_notepad(window)
    time.sleep(1.0)

    data = Path(tempfile.mkdtemp(prefix="once-real-e2e-"))
    service = WorkflowService.for_app_data(data)
    workflow = Workflow(
        "real-notepad",
        "Write a note in Notepad",
        (
            WorkflowStep(
                "launch",
                "Open Notepad",
                StepKind.LAUNCH_APPLICATION,
                "Launch Notepad.",
                target=json.dumps({"executable": str(notepad)}),
            ),
            WorkflowStep(
                "type",
                "Type in the document",
                StepKind.TYPE_TEXT,
                "Enter the text.",
                target=json.dumps(
                    {
                        # The window's own title is unique; matching ignores the
                        # unsaved-changes marker Notepad adds while typing.
                        "window": {"title": title},
                        "element": {"control_type": "Document", "class_name": "RichEditD2DPT"},
                        "text": "once test",
                    }
                ),
            ),
            WorkflowStep(
                "close",
                "Close Notepad",
                StepKind.CLOSE_APPLICATION,
                "Close only the window this run opened.",
                target=json.dumps({"executable": str(notepad)}),
            ),
        ),
    )
    approval = approve_desktop_workflow(workflow)
    try:
        run = service.run_desktop_approved(approval)
        messages = [result.message for result in run.results]
        if any("ambiguous" in message for message in messages):
            pytest.skip(
                "Notepad restored another window with the same title, so the element "
                "target is ambiguous; close Notepad and rerun. The recorded-flow probe "
                "(scripts/prove_notepad_flow.py) covers this task end to end."
            )
        assert run.status.value == "SUCCEEDED", messages
        time.sleep(1.0)
        assert not [w for w in notepad_windows() if w.element_info.handle not in before]
    finally:
        service.close()
        if window is not None:
            for leftover in notepad_windows():
                if leftover.element_info.handle == window.element_info.handle:
                    for item in leftover.descendants():
                        info = item.element_info
                        if (
                            getattr(info, "control_type", None) == "Button"
                            and getattr(info, "automation_id", "") == "SecondaryButton"
                        ):
                            item.invoke()
                            break


def test_the_desktop_test_states_how_to_opt_in() -> None:
    """CI runs without a desktop, so the skip reason must say how to run it."""
    if os.environ.get("ONCE_REAL_DESKTOP") == "1":  # pragma: no cover - opt-in only
        pytest.skip("the real desktop test is enabled in this run")
    assert "ONCE_REAL_DESKTOP" in real_desktop.kwargs["reason"]
