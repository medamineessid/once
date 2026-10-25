"""Enumerate all top-level UIA windows while looking for Notepad."""

import os
import subprocess
import time
from pathlib import Path

from pywinauto import Desktop

exe = Path(os.environ["SystemRoot"]) / "System32" / "notepad.exe"
process = subprocess.Popen([str(exe)], shell=False)
print("launched pid", process.pid)
time.sleep(3)

desktop = Desktop(backend="uia")
for wrapper in desktop.windows():
    info = wrapper.element_info
    name = getattr(info, "name", None)
    print(
        "pid=",
        getattr(info, "process_id", None),
        "class=",
        repr(getattr(info, "class_name", None)),
        "name=",
        repr((name or "")[:50]),
        "ctl=",
        getattr(info, "control_type", None),
    )
