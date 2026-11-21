"""Pin down the replay close failure: immediate close + uia latency curve."""

from __future__ import annotations

import json
import subprocess
import sys
import time

sys.path.insert(0, r"C:\Users\DELL\once")

from pywinauto import Desktop

from integrations.uia_targeting import window_matches
from integrations.windows_desktop import PywinautoDesktopActions


def kill(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)


def first_hit(pid: int, backend: str, budget: float = 12.0) -> float:
    """Seconds until `window_matches` finds pid on this backend, from now."""
    started = time.monotonic()
    while time.monotonic() - started < budget:
        for wrapper in Desktop(backend=backend).windows():
            if window_matches(wrapper, {"process_id": pid}):
                return time.monotonic() - started
        time.sleep(0.25)
    return -1.0


# Phase 1: provider-direct launch then IMMEDIATE close (no settle).
provider = PywinautoDesktopActions()
result = provider.launch_application(json.dumps({"application": "calc"}))
pid1 = int(next(e.split("=", 1)[1] for e in result.evidence if e.startswith("process_id=")))
print(f"phase1: launch pid {pid1}; closing IMMEDIATELY...")
close = provider.close_application(json.dumps({"application": "calc"}))
print("phase1 close:", close.status.value, list(close.evidence))
if close.status.value != "SUCCEEDED":
    hit = first_hit(pid1, "uia")
    print(f"phase1: uia first-hit latency for pid {pid1}: {hit:.2f}s")
    if hit < 0:
        win32_hit = first_hit(pid1, "win32", budget=4.0)
        print(f"phase1: win32 first-hit: {win32_hit:.2f}s")

kill(pid1)

# Phase 2: measure uia latency curve for a fresh instance (windows polled until seen).
result = provider.launch_application(json.dumps({"application": "calc"}))
pid2 = int(next(e.split("=", 1)[1] for e in result.evidence if e.startswith("process_id=")))
print(f"phase2: fresh launch pid {pid2}; polling uia every 0.25s from t=0...")
t0 = time.monotonic()
seen_at = None
while time.monotonic() - t0 < 14.0:
    elapsed = time.monotonic() - t0
    hits = [
        w.element_info.process_id
        for w in Desktop(backend="uia").windows()
        if window_matches(w, {"process_id": pid2})
    ]
    if hits:
        seen_at = elapsed
        print(f"   t={elapsed:.2f}s uia FIRST SEES pid {pid2}")
        break
    win32_hits = [
        w.element_info.process_id
        for w in Desktop(backend="win32").windows()
        if w.element_info.process_id == pid2
    ]
    print(f"   t={elapsed:.2f}s uia: none; win32: {win32_hits or 'none'}")
    time.sleep(0.25)

if seen_at is None:
    print("   pid never seen in 14s!")
kill(pid2)
time.sleep(1.0)
kill(pid2)
print("cleanup sent")
