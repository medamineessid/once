"""Record, approve and run "open Notepad, type once test, close it" twice.

Run with:  .venv/Scripts/python.exe scripts/prove_notepad_flow.py

This uses the REAL Windows desktop: the recorder watches a real launch, real
keystrokes and a real window close, the deterministic local provider turns the
observation into steps, the workflow passes the desktop approval gate, and the
engine runs it twice in a row.

Clean-up: only the Notepad window this script creates is typed into and closed.
Any Notepad window that already existed is left alone, and the script says so.

Why the Ctrl+Z step: Windows 11 Notepad asks to save when a modified document is
closed. Typing then undoing returns the document to its unmodified state, so the
close is clean and the proof is about replay, not about dismissing dialogs.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pywinauto import Desktop, keyboard

from ai.models import AnalysisRequest, ProviderDraft
from ai.provider import deterministic_recording_provider
from controller.service import WorkflowService
from engine.desktop import approve_desktop_workflow
from integrations.recorder import PynputRecorder, UIAElementProvider
from recorder.drafts import build_raw_draft
from recorder.models import RecordedEvent, Recording
from recorder.redaction import redact_events

NOTEPAD = Path("C:/Windows/System32/notepad.exe")
TASKLIST = Path("C:/Windows/System32/tasklist.exe")
TYPED_TEXT = "once test"
OUT = Path("shots/after")


def notepad_windows() -> list:
    return [
        wrapper
        for wrapper in Desktop(backend="uia").windows()
        if getattr(wrapper.element_info, "class_name", None) == "Notepad"
    ]


def handles(windows: list) -> set[int]:
    return {getattr(wrapper.element_info, "handle", 0) for wrapper in windows}


def wait_for_new_window(before: set[int], timeout: float = 12.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        new = [w for w in notepad_windows() if getattr(w.element_info, "handle", 0) not in before]
        if len(new) == 1:
            return new[0]
        time.sleep(0.3)
    return None


def notepad_processes() -> list[str]:
    """The process list a person would check with Get-Process, filtered to Notepad."""
    try:
        output = subprocess.run(  # noqa: S603 - fixed absolute path, no shell
            [str(TASKLIST), "/FI", "IMAGENAME eq Notepad.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:  # honest, not silent
        return [f"tasklist failed: {error}"]
    return [line.strip() for line in output.splitlines() if line.strip() and "INFO:" not in line]


def assert_clean_start() -> str | None:
    """Refuse to start while an earlier attempt's Notepad window is still open.

    Two identically titled windows make every title-based step ambiguous, so a
    leftover is not silently ignored: the run stops and names it.
    """
    leftovers = [
        w.element_info.name
        for w in notepad_windows()
        if "once test" in (w.element_info.name or "").casefold()
    ]
    if leftovers:
        return f"an earlier Notepad window is still open: {leftovers[0]!r}"
    return None


def record_once() -> tuple[list[RecordedEvent], dict]:
    """Drive one visible Notepad session while the real recorder observes it."""
    before = handles(notepad_windows())
    existing = [w.element_info.name for w in notepad_windows()]
    events: list[RecordedEvent] = []
    recorder = PynputRecorder(
        events,
        element_provider=UIAElementProvider(),
        keyboard_enabled=True,
        text_flush_seconds=0.3,
    )
    facts: dict = {"pre_existing_windows": existing}
    recorder.start()
    time.sleep(1.0)
    subprocess.Popen([str(NOTEPAD)])  # noqa: S603 - fixed system path, no shell
    window = wait_for_new_window(before)
    if window is None:
        recorder.stop()
        facts["aborted"] = "the new Notepad window did not appear"
        return events, facts
    window.set_focus()
    time.sleep(0.6)
    keyboard.send_keys("once{SPACE}test")
    time.sleep(1.0)  # the recorder flushes buffered text after 0.3 s
    # Back to an unmodified document: Windows 11 Notepad asks to save otherwise,
    # and that prompt would keep the window open at replay time.
    for _attempt in range(3):
        keyboard.send_keys("^z")
        time.sleep(0.7)
        if not (window.element_info.name or "").startswith("*"):
            break
    facts["title_before_close"] = window.element_info.name
    window.close()
    time.sleep(1.2)
    recorder.stop()
    facts["window_title_at_close"] = window.element_info.name
    return events, facts


def main() -> int:
    if not NOTEPAD.is_file():
        print(f"ABORT: {NOTEPAD} is missing; refusing to guess a launcher.")
        return 1
    print("== Once: record -> approve -> run, on the real desktop ==")
    unclean = assert_clean_start()
    if unclean is not None:
        print(f"ABORT: {unclean}")
        return 1
    processes_before = notepad_processes()
    print(f"Notepad processes before: {len(processes_before)}")
    for line in processes_before:
        print(f"  {line}")

    events, facts = record_once()
    if "aborted" in facts:
        print(f"ABORT: {facts['aborted']}")
        return 1
    print(f"recorded events: {len(events)}")
    for event in events:
        print(
            f"  {event.sequence:>2} {event.kind.value:<20} "
            f"title={event.window_title!r} text={event.text!r} key={event.key!r}"
        )

    recording = Recording(
        recording_id="prove-notepad",
        started_at_ns=int(time.time() * 1e9),
        events=redact_events(tuple(events)),
    )
    draft = build_raw_draft(recording)
    provider = deterministic_recording_provider()
    response = provider.analyze(AnalysisRequest(draft=draft))
    if not isinstance(response, ProviderDraft):
        print("ABORT: the provider returned a question, not a draft.")
        return 1
    workflow = response.workflow
    print(f"draft: {len(workflow.steps)} steps")
    for step in workflow.steps:
        print(f"  {step.kind.value:<20} {step.name:<28} {step.message[:60]}")

    approval = approve_desktop_workflow(workflow, allow_observations=True)
    print("approved for exactly:", [step.kind.value for step in approval.workflow.steps])

    data = Path("shots/after").resolve() / "_notepad-run-data"
    data.mkdir(parents=True, exist_ok=True)
    service = WorkflowService.for_app_data(data)
    runs = []
    for attempt in (1, 2):
        before = handles(notepad_windows())
        started = time.monotonic()
        run = service.run_desktop_approved(approval)
        elapsed = round(time.monotonic() - started, 2)
        print(f"run {attempt}: {run.status.value} in {elapsed}s")
        for result in run.results:
            print(f"  {result.status.value:<10} {result.message}")
            for evidence in result.evidence:
                print(f"             {evidence}")
        time.sleep(1.0)
        leftover = [
            w for w in notepad_windows() if getattr(w.element_info, "handle", 0) not in before
        ]
        print(f"  new Notepad windows left behind: {len(leftover)}")
        runs.append(
            {
                "attempt": attempt,
                "status": run.status.value,
                "seconds": elapsed,
                "steps": [
                    {
                        "kind": next(
                            (s.kind.value for s in workflow.steps if s.step_id == r.step_id),
                            "",
                        ),
                        "status": r.status.value,
                        "message": r.message,
                    }
                    for r in run.results
                ],
                "leftover_windows": len(leftover),
            }
        )

    processes_after = notepad_processes()
    print(f"Notepad processes after: {len(processes_after)}")
    for line in processes_after:
        print(f"  {line}")
    service.close()

    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "recorded_events": [
            {"kind": e.kind.value, "window_title": e.window_title, "text": e.text} for e in events
        ],
        "pre_existing_notepad_windows": facts.get("pre_existing_windows", []),
        "draft_steps": [
            {"kind": s.kind.value, "name": s.name, "target": s.target} for s in workflow.steps
        ],
        "runs": runs,
        "notepad_processes_before": processes_before,
        "notepad_processes_after": processes_after,
    }
    (OUT / "notepad-flow.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    ok = all(run["status"] in ("SUCCEEDED", "PARTIALLY_PERFORMED") for run in runs) and all(
        run["leftover_windows"] == 0 for run in runs
    )
    print(f"wrote {OUT / 'notepad-flow.json'}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
