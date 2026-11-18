"""Exercise the real Ctrl+Alt+Q kill switch during a live Character Map run."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pywinauto import Desktop, keyboard

from controller.service import WorkflowService
from engine.desktop import approve_desktop_workflow
from engine.workflow import StepKind, Workflow, WorkflowStep
from integrations.kill_switch import HotkeyKillSwitch

APP = Path(r"C:\Windows\System32\charmap.exe")
WAIT_TIMEOUT = 4.0


def charmap_windows() -> list[dict[str, Any]]:
    return [
        {
            "title": getattr(window.element_info, "name", None),
            "pid": getattr(window.element_info, "process_id", None),
            "handle": getattr(window.element_info, "handle", None),
        }
        for window in Desktop(backend="uia").windows()
        if getattr(window.element_info, "class_name", None) == "#32770"
        and "caract" in (getattr(window.element_info, "name", "") or "").casefold()
    ]


def main() -> int:
    leftovers = charmap_windows()
    if leftovers:
        print(f"ABORT: {len(leftovers)} Character Map window(s) already open; refusing to guess.")
        return 1
    workflow = Workflow(
        "kill-switch-live",
        "Kill switch live check",
        (
            WorkflowStep(
                "launch",
                "Launch Character Map",
                StepKind.LAUNCH_APPLICATION,
                "Open Character Map.",
                target=json.dumps({"executable": str(APP)}),
            ),
            WorkflowStep(
                "wait",
                "Wait for a window that will not exist",
                StepKind.WAIT_WINDOW,
                "This bounded wait gives the kill switch time to act.",
                target=json.dumps({"title": "Once kill-switch wait window"}),
                timeout_seconds=WAIT_TIMEOUT,
            ),
            WorkflowStep(
                "close",
                "Close Character Map",
                StepKind.CLOSE_APPLICATION,
                "Close only the window this run opened.",
                target=json.dumps({"executable": str(APP)}),
            ),
        ),
    )
    approval = approve_desktop_workflow(workflow)
    kill_switch = HotkeyKillSwitch()
    data = Path(tempfile.mkdtemp(prefix="once-kill-switch-")) / "Once"
    data.mkdir()
    service = WorkflowService.for_app_data(data)
    service._kill_switch = kill_switch  # type: ignore[attr-defined]  # probe injection only

    result: dict[str, Any] = {}

    def run() -> None:
        try:
            result["run"] = service.run_desktop_approved(approval)
            result["triggered"] = kill_switch.triggered
        except Exception as error:  # probe must report the real failure
            result["error"] = f"{type(error).__name__}: {error}"

    thread = threading.Thread(target=run, daemon=True)
    started = time.monotonic()
    thread.start()
    time.sleep(1.5)
    # The low-level keyboard hook needs an interactive foreground window.
    for window in Desktop(backend="uia").windows():
        info = window.element_info
        if (
            getattr(info, "class_name", None) == "#32770"
            and "caract" in (getattr(info, "name", "") or "").casefold()
        ):
            window.set_focus()
            break
    time.sleep(0.3)
    print("sending Ctrl+Alt+Q with pywinauto...")
    keyboard.send_keys("^%q")
    thread.join(timeout=WAIT_TIMEOUT + 12)
    elapsed = time.monotonic() - started
    if thread.is_alive():
        print("FAIL: the run did not stop after the hotkey.")
        service.close()
        return 1

    if "error" in result:
        print(f"FAIL: {result['error']}")
        service.close()
        return 1
    run_obj = result["run"]
    print(f"status: {run_obj.status.value}")
    for item in run_obj.results:
        print(f"  {item.step_id}: {item.status.value}: {item.message}")
    print(f"kill switch triggered: {result['triggered']}")
    print(f"elapsed: {elapsed:.1f}s")
    time.sleep(0.5)
    remaining = charmap_windows()
    print(f"remaining Character Map windows: {len(remaining)}")
    report = {
        "status": run_obj.status.value,
        "triggered": result["triggered"],
        "elapsed_seconds": round(elapsed, 2),
        "steps": [
            {"step_id": step.step_id, "status": step.status.value, "message": step.message}
            for step in run_obj.results
        ],
        "remaining_charmap_windows": remaining,
    }
    out = Path("shots/after")
    out.mkdir(parents=True, exist_ok=True)
    (out / "kill-switch.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    service.close()
    ok = run_obj.status.value == "CANCELLED" and result["triggered"] and not remaining
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
