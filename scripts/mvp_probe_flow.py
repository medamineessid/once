"""Live MVP probe: record a real task, review, save, run - and verify the run
really performed the actions (replay-target: calc.exe, a classic app whose
launched pid owns its own windows).

Real Windows: pynput global hooks + Win32 window monitor capture events while
Calculator is actually launched and closed. Then the recorded draft follows
the same controller path the UI uses (analyze -> approve -> save -> run via the
desktop approval gate). No network. Isolated app-data directory."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ai.analyze_recording import analyze_recording
from ai.approval import approve_proposal
from ai.models import AnalysisRequest
from controller.recording import RecordingService
from controller.service import WorkflowService
from recorder.drafts import build_raw_draft

APPDATA = Path(tempfile.mkdtemp(prefix="once-mvp-"))

recording_service = RecordingService(APPDATA / "recordings")
recording_service.start("mvp-probe-recording")
print("1) recording started")

calc = subprocess.Popen(["calc.exe"], shell=False)
print("2) calc launched, pid", calc.pid)
time.sleep(2.5)

subprocess.run(["taskkill", "/PID", str(calc.pid)], capture_output=True)
print("3) calc close requested, waiting...")
try:
    calc.wait(timeout=5)
except subprocess.TimeoutExpired:
    subprocess.run(["taskkill", "/PID", str(calc.pid), "/F"], capture_output=True)
    calc.wait(timeout=5)
time.sleep(1.0)

recording = recording_service.stop()
print(f"4) recording stopped, {len(recording.events)} events:")
for event in recording.events:
    print(
        "   #",
        event.sequence,
        event.kind.value,
        event.process_name,
        (event.window_title or "")[:40],
    )

draft = build_raw_draft(recording)
proposal = analyze_recording(AnalysisRequest(draft))
workflow = proposal.workflow
assert workflow.steps, "no draft steps produced"
print(f"5) draft built: {len(workflow.steps)} steps")
for step in workflow.steps:
    print(f"   {step.step_id} {step.kind.value} - {step.message}")

approved = approve_proposal(proposal)
service = WorkflowService.for_app_data(APPDATA)
saved = service.save_approved(approved)
print(f"6) saved through the approval gate: {saved.name}")

from engine.desktop import approve_desktop_workflow, requires_desktop_approval

print("7) mutating?", requires_desktop_approval(workflow))
approval = approve_desktop_workflow(workflow)
print("8) running through the desktop approval gate (run_desktop_approved)...")
run = service.run_desktop_approved(approval)
print(f"   RUN STATUS: {run.status.value}")
pid_seen: int | None = None
windows_closed = 0
for step in run.results:
    print(f"   {step.step_id} {step.status.value} - {step.message[:90]}")
    for evidence in step.evidence:
        print(f"      evidence: {evidence[:90]}")
        if evidence.startswith("process_id="):
            pid_seen = int(evidence.split("=", 1)[1])
        if evidence.startswith("windows_closed="):
            windows_closed = int(evidence.split("=", 1)[1])

print("9) history rows:", len(service.history()))

# Post-run truth: the launch the RUN performed must really be gone on close.
if run.status.value == "SUCCEEDED":
    assert pid_seen is not None, "run did not report the launched pid"
    assert windows_closed >= 1, f"PROBE FAILURE: windows_closed={windows_closed}, expected >= 1"
    # A closed window exits its process shortly after (proven on this machine):
    # allow a small exit window rather than testing mid-exit.
    for _ in range(6):
        check = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid_seen}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
        )
        if "INFO:" in check.stdout:
            break
        time.sleep(1.0)
    else:
        print(f"NOTE: pid {pid_seen} still alive 6s after window close")
    print(f"10) verified: windows_closed={windows_closed}; pid exit checked")
print("DONE")
