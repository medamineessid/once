"""Decisive probe: does the real provider close path work on calc live?

Reproduces launch_application -> close_application with the actual
PywinautoDesktopActions (uia backend), and separately checks
window_matches under uia for the launched pid."""

from __future__ import annotations

import sys
import time

sys.path.insert(0, r"C:\Users\DELL\once")

import json

from integrations.uia_targeting import window_matches
from integrations.windows_desktop import PywinautoDesktopActions

provider = PywinautoDesktopActions()
print("launching via provider.launch_application...")
result = provider.launch_application(json.dumps({"application": "calc"}))
print("launch:", result.status.value, list(result.evidence))
pid = None
for evidence in result.evidence:
    if evidence.startswith("process_id="):
        pid = int(evidence.split("=", 1)[1])
assert pid is not None

time.sleep(3.0)
print(f"after 3s: checking window_matches for pid {pid} on the uia desktop...")
from pywinauto import Desktop as _D

matched = []
for wrapper in _D(backend="uia").windows():
    info = wrapper.element_info
    if window_matches(wrapper, {"process_id": pid}):
        matched.append((info.process_id, (info.name or "")[:30]))
print("window_matches hits:", matched)

print("close via provider.close_application...")
close = provider.close_application(json.dumps({"application": "calc"}))
print("close:", close.status.value, close.message[:80], list(close.evidence))

check = subprocess_run = __import__("subprocess").run(
    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
    capture_output=True,
    text=True,
)
print("post-close process alive?", "INFO:" not in check.stdout)
