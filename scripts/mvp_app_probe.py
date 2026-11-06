"""Diagnose: which classic apps spawn a process that owns its own windows?"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\DELL\once")
from pywinauto import Desktop

WINDIR = Path(r"C:\Windows")


def probe(exe: str, target_pid_hint: str) -> None:
    full = WINDIR / "System32" / exe
    proc = subprocess.Popen([str(full)])
    time.sleep(2.5)
    windows = Desktop(backend="win32").windows()
    owned = []
    for wrapper in windows:
        info = wrapper.element_info
        if info.process_id == proc.pid:
            owned.append((info.class_name, (info.name or "")[:30]))
    print(f"{exe}: launched pid {proc.pid}; own windows: {owned if owned else 'NONE'}")
    subprocess.run(["taskkill", "/PID", str(proc.pid)], capture_output=True)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"], capture_output=True)
        proc.wait(timeout=5)
    time.sleep(0.6)


probe("calc.exe", target_pid_hint="calc")
