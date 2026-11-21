"""Prove record -> approve -> run twice on a real Windows desktop.

Uses only a disposable data folder and Character Map, a single-window safe
Windows accessory with a text field and no save prompt. The recorded window is
the exact process and handle created by this run. Notepad was deliberately not
used: this machine had a pre-existing unsaved Notepad document, and Windows 11
Notepad hosts multiple documents in one process.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pywinauto import Desktop, keyboard

from ai.approval import approve_proposal, preview_proposal
from ai.models import AnalysisRequest
from ai.provider import deterministic_recording_provider
from controller.recording import RecordingService
from controller.service import WorkflowService
from engine.desktop import approve_desktop_workflow
from recorder.drafts import build_raw_draft

APP = Path(r"C:\Windows\System32\charmap.exe")
TEXT = "once test"


def charmap_windows(desktop: Desktop) -> dict[int, str]:
    result: dict[int, str] = {}
    for window in desktop.windows():
        info = window.element_info
        title = str(getattr(info, "name", ""))
        if getattr(info, "class_name", None) == "#32770" and (
            "caract" in title.casefold() or "character map" in title.casefold()
        ):
            result[int(getattr(info, "handle", 0))] = title
    return result


def wait_for_new_window(desktop: Desktop, process_id: int, timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for window in desktop.windows():
            info = window.element_info
            if getattr(info, "process_id", None) == process_id:
                return window
        time.sleep(0.2)
    raise RuntimeError("The new Character Map window did not appear.")


def close_new_window(window) -> None:
    try:
        window.close()
    except (AttributeError, OSError, RuntimeError) as error:
        raise RuntimeError(f"The disposable Character Map window did not close: {error}") from error


def record_task(data: Path) -> tuple[object, int]:
    desktop = Desktop(backend="uia")
    service = RecordingService(data / "recordings")
    recording_id = f"charmap-{uuid4().hex[:8]}"
    service.start(recording_id)
    process = subprocess.Popen([str(APP)], shell=False)  # noqa: S603
    try:
        window = wait_for_new_window(desktop, process.pid)
        handle = int(getattr(window.element_info, "handle", 0))
        window.set_focus()
        time.sleep(0.3)
        # Focus the "Characters to copy" edit before typing.
        for child in window.descendants():
            info = child.element_info
            if getattr(info, "automation_id", None) == "104":
                child.set_focus()
                break
        time.sleep(0.2)
        keyboard.send_keys("once{SPACE}test")
        time.sleep(1.2)  # let the recorder flush idle typing before the close event
        close_new_window(window)
        time.sleep(0.8)
    finally:
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=5)
        recording = service.stop()
    return recording, handle


def main() -> int:
    if not APP.is_file():
        print("FAIL: Character Map is missing.")
        return 1
    root = Path(tempfile.mkdtemp(prefix="once-core-flow-"))
    data = root / "Once"
    data.mkdir()

    print(f"data folder: {data}")
    print(f"safe app: {APP}")
    recording, own_handle = record_task(data)
    print(f"recording id: {recording.recording_id}, events={len(recording.events)}")
    for event in recording.events:
        print(f"  {event.sequence}: {event.kind.value} {event.window_title or ''}")

    request = AnalysisRequest(build_raw_draft(recording))
    proposal = deterministic_recording_provider().analyze(request)
    workflow = proposal.workflow
    preview = preview_proposal(proposal)
    approved_proposal = approve_proposal(proposal)
    print(f"approved proposal: {approved_proposal.approved_at.isoformat()}")
    print(f"preview desktop approval required: {preview.needs_desktop_approval}")
    for line in preview.steps:
        print(f"  {line}")

    desktop_approval = approve_desktop_workflow(workflow, allow_observations=True)
    service = WorkflowService.for_app_data(data)
    service.approve_workflow_applications(workflow)

    results = []
    for attempt in (1, 2):
        print(f"\n=== run {attempt} ===")
        run = service.run_desktop_approved(desktop_approval)
        print(f"status: {run.status.value}")
        for item in run.results:
            print(f"  {item.step_id}: {item.status.value}: {item.message}")
            for evidence in item.evidence:
                print(f"      {evidence}")
        windows = charmap_windows(Desktop(backend="uia"))
        own_remaining = own_handle in windows
        print(f"our original window remains: {own_remaining}")
        results.append(
            {
                "attempt": attempt,
                "status": run.status.value,
                "steps": [
                    {
                        "step_id": item.step_id,
                        "status": item.status.value,
                        "message": item.message,
                        "evidence": list(item.evidence),
                    }
                    for item in run.results
                ],
                "our_window_remains": own_remaining,
            }
        )

    service.close()
    report = {
        "data_folder": str(data),
        "app": str(APP),
        "recording_id": recording.recording_id,
        "own_window_handle": own_handle,
        "runs": results,
    }
    out = Path("shots/after")
    out.mkdir(parents=True, exist_ok=True)
    (out / "core-flow.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nreport: {out / 'core-flow.json'}")
    ok = all(item["status"] == "SUCCEEDED" for item in results) and all(
        item["our_window_remains"] is False for item in results
    )
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
