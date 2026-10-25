"""Live end-to-end Notepad demonstration for the desktop automation engine.

This script runs against a REAL Windows desktop. It is not part of the
automated suite. Safety rules it follows:

- the target file is a fresh file in a temporary directory;
- the launch goes through the validated LAUNCH_APPLICATION step (exact argv,
  shell disabled, registry or absolute .exe path);
- window and element targets are discovered read-only and must be unique
  before the mutating workflow is built;
- the mutating workflow passes approve_desktop_workflow before execution and
  only then runs through the desktop policy;
- only the window opened by this run is closed at the end.

Run with:  C:\\Users\\DELL\\once\\.venv\\Scripts\\python.exe scripts\\notepad_demo.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

import json
import tempfile
import time
from pathlib import Path

from engine.desktop import approve_desktop_workflow
from engine.replay import DESKTOP_INTERACTION_POLICY, ReplayExecutor, ReplayPreview
from engine.workflow import (
    StepKind,
    StepStatus,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)
from integrations.windows_desktop import PywinautoDesktopActions

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEMO_TEXT = "Once desktop automation demo - safe to delete"
POLL_SECONDS = 0.5
DISCOVERY_TIMEOUT_SECONDS = 20.0


def close_leftover_demo_windows(desktop) -> int:
    """Close any window left by an earlier demo run (matched by demo file name)."""
    closed = 0
    for wrapper in desktop.windows():
        info = wrapper.element_info
        if getattr(info, "class_name", None) == "Notepad" and "once-demo-note" in (
            getattr(info, "name", "") or ""
        ):
            try:
                wrapper.close()
                closed += 1
            except (OSError, RuntimeError, AttributeError):  # hygiene is best effort
                pass
    return closed


def main() -> int:
    print("== Once desktop automation: live Notepad demo ==")
    actions = PywinautoDesktopActions()
    desktop = actions._default_desktop()
    leftovers = close_leftover_demo_windows(desktop)
    if leftovers:
        print(f"hygiene: closed {leftovers} leftover demo window(s) before starting.")
        time.sleep(1.0)

    # 1. Fresh, disposable target file inside a temporary directory.
    demo_dir = Path(tempfile.mkdtemp(prefix="once-notepad-demo-"))
    target_file = demo_dir / "once-demo-note.txt"
    target_file.write_text("", encoding="utf-8")
    print(f"target file (fresh): {target_file}")

    # 2. Launch step: approved workflow #1 (launch only).
    notepad = Path("C:/Windows/System32/notepad.exe")
    if not notepad.is_file():
        print(f"DEMO STOPPED: {notepad} is missing; refusing to guess a launcher.")
        return 1
    launch = Workflow(
        "once-notepad-launch",
        "Launch Notepad with the demo file",
        (
            WorkflowStep(
                "launch",
                "Launch",
                StepKind.LAUNCH_APPLICATION,
                "Notepad opened with the demo file.",
                target=json.dumps({"executable": str(notepad), "arguments": [str(target_file)]}),
            ),
        ),
    )
    WorkflowRunner.validate(launch)
    approval_a = approve_desktop_workflow(launch)
    executor = ReplayExecutor(DESKTOP_INTERACTION_POLICY)
    run_a = executor.execute(approval_a.workflow, allowed_root=demo_dir, desktop_actions=actions)
    for result in run_a.results:
        print(f"[launch] {result.status.value}: {result.message}")
        for evidence in result.evidence:
            print(f"         {evidence}")
    if run_a.status.value != "SUCCEEDED":
        print("DEMO STOPPED: the launch step did not succeed.")
        return 1

    # 3. Read-only discovery of OUR window (unique title containing the stem).
    deadline = time.monotonic() + DISCOVERY_TIMEOUT_SECONDS
    window_match = None
    while time.monotonic() < deadline and window_match is None:
        candidates = [
            wrapper
            for wrapper in desktop.windows()
            if getattr(wrapper.element_info, "class_name", None) == "Notepad"
            and "once-demo-note" in (getattr(wrapper.element_info, "name", "") or "")
        ]
        if len(candidates) == 1:
            window_match = candidates[0]
            break
        if len(candidates) > 1:
            print("DEMO STOPPED: several Notepad windows match the demo file name.")
            return 1
        time.sleep(POLL_SECONDS)
    if window_match is None:
        print("DEMO STOPPED: the demo Notepad window did not appear.")
        return 1
    info = window_match.element_info
    window_title = info.name
    window_pid = getattr(info, "process_id", None)
    print(f"discovered unique window: title={window_title!r} pid={window_pid}")

    # Read-only discovery of the text control (unique Document descendant).
    doc_candidates = [
        wrapper
        for wrapper in window_match.descendants()
        if getattr(wrapper.element_info, "control_type", None) == "Document"
    ]
    if len(doc_candidates) != 1:
        print(
            "DEMO STOPPED: the text control is not uniquely identified "
            f"({len(doc_candidates)} Document descendants)."
        )
        return 1
    doc_info = doc_candidates[0].element_info
    element_identity = {
        "automation_id": getattr(doc_info, "automation_id", None) or "",
        "control_type": getattr(doc_info, "control_type", None),
        "class_name": getattr(doc_info, "class_name", None),
    }
    print(f"discovered text control: {element_identity}")
    element_identity = {k: v for k, v in element_identity.items() if v}

    # 4. Mutating workflow #2: wait -> type -> save -> verify file.
    steps = (
        WorkflowStep(
            "wait",
            "Wait",
            StepKind.WAIT_WINDOW,
            "The demo window is present.",
            target=json.dumps({"title": window_title, "class_name": "Notepad"}),
            timeout_seconds=10.0,
        ),
        WorkflowStep(
            "type",
            "Type",
            StepKind.TYPE_TEXT,
            DEMO_TEXT,
            target=json.dumps(
                {
                    "window": {"title": window_title, "class_name": "Notepad"},
                    "element": {
                        "control_type": element_identity["control_type"],
                        "class_name": element_identity["class_name"],
                    },
                    "text": DEMO_TEXT,
                }
            ),
        ),
        WorkflowStep(
            "save",
            "Save",
            StepKind.PRESS_SHORTCUT,
            "Ctrl+S delivered to the demo window only.",
            # The title gains an unsaved-changes marker after typing, so the
            # shortcut identifies the window by process id + class instead.
            target=json.dumps(
                {
                    "window": {"process_id": window_pid, "class_name": "Notepad"},
                    "keys": "ctrl+s",
                }
            ),
        ),
        WorkflowStep(
            "verify",
            "Verify",
            StepKind.VERIFY_FILE_TEXT,
            "The saved file contains the demo text.",
            target=json.dumps({"path": str(target_file), "contains": DEMO_TEXT}),
        ),
    )
    workflow = Workflow("once-notepad-demo", "Once Notepad demo", steps)
    preview = ReplayPreview("once-notepad-demo", (), True)
    _ = preview
    WorkflowRunner.validate(workflow)
    replay_check = executor.preview(workflow)
    print(f"desktop policy preview: executable={replay_check.executable}")
    if not replay_check.executable:
        print("DEMO STOPPED: the desktop policy refused the workflow.")
        return 1
    approval_b = approve_desktop_workflow(workflow)
    print(
        "approval recorded for exactly these steps:",
        [step.step_id for step in approval_b.workflow.steps],
    )

    run_b = executor.execute(approval_b.workflow, allowed_root=demo_dir, desktop_actions=actions)
    for result in run_b.results:
        print(f"[{result.step_id}] {result.status.value}: {result.message}")
        for evidence in result.evidence:
            print(f"         {evidence}")

    success = run_b.status.value == "SUCCEEDED" and all(
        result.status in (StepStatus.SUCCEEDED, StepStatus.VERIFIED) for result in run_b.results
    )
    print(f"run status: {run_b.status.value}")
    content = target_file.read_text(encoding="utf-8", errors="replace")
    print(f"file content after run ({len(content)} chars): {content!r}")

    # 5. Close ONLY the window this run opened (best effort, outside the engine).
    try:
        window_match.close()
        print("cleanup: the demo window was closed.")
    except (OSError, RuntimeError, AttributeError) as error:
        print(f"cleanup: the demo window stayed open ({error}); close it manually.")

    if success and DEMO_TEXT in content and content == DEMO_TEXT:
        print("RESULT: PASS - live desktop round trip verified.")
        return 0
    print("RESULT: FAIL - see the step messages above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
