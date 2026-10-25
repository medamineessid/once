"""Launch Notepad and print its UI Automation tree (live inspection probe)."""

import os
import subprocess
import sys
import time
from pathlib import Path

from pywinauto import Desktop

exe = Path(os.environ["SystemRoot"]) / "System32" / "notepad.exe"
print("notepad exists:", exe.is_file(), exe)
process = subprocess.Popen([str(exe)], shell=False, cwd=os.environ["TEMP"])
print("launched pid", process.pid)

desktop = Desktop(backend="uia")
deadline = time.monotonic() + 10
found = None
while time.monotonic() < deadline:
    windows = [w for w in desktop.windows() if w.process_id == process.pid]
    if windows:
        found = windows[0]
        break
    time.sleep(0.2)
if found is None:
    print("NO WINDOW FOUND for pid")
    sys.exit(1)

info = found.element_info
print("WINDOW:", info.name, repr(info.class_name), getattr(info, "automation_id", None))
for child in found.descendants():
    cinfo = child.element_info
    print(
        "  control:",
        getattr(cinfo, "control_type", None),
        repr(getattr(cinfo, "automation_id", None)),
        repr(getattr(cinfo, "class_name", None)),
        "name=",
        repr((getattr(cinfo, "name", None) or "")[:40]),
    )
# value pattern on the first Edit-like control
for child in found.descendants():
    if getattr(child.element_info, "control_type", None) in ("Edit", "Document"):
        pattern = child.iface_value
        print("TEXT CONTROL:", child.control_type() if hasattr(child, "control_type") else "?", "value_pattern:", pattern)
        if pattern is not None:
            pattern.SetValue("probe text from Once")
            print("SET OK, read back:", pattern.Value)
        break
