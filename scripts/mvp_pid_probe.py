"""Diagnose: does the launched Notepad pid own its top-level windows?"""

from __future__ import annotations

import subprocess
import sys
import time

sys.path.insert(0, r"C:\Users\DELL\once")
from pywinauto import Desktop

proc = subprocess.Popen(["notepad.exe"])
time.sleep(2.5)
windows = Desktop(backend="win32").windows()
found = []
for wrapper in windows:
    try:
        info = wrapper.element_info
        pid = info.process_id
        if pid == proc.pid:
            found.append(info.name[:40])
    except Exception:
        continue
print("launched pid:", proc.pid)
print("top-level windows whose pid == launched pid:", found)
matchable = [
    (w.element_info.process_id, (w.element_info.name or "")[:40])
    for w in windows
    if "notepad" in str(getattr(w.element_info, "class_name", "")).lower()
    or (w.element_info.process_id and "Notepad" in str(getattr(w.element_info, "name", "")))
]
print("notepad-ish windows (pid, title):", matchable[:6])
proc.terminate()
proc.wait(timeout=5)
print("closed via terminate")
