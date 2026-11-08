"""Diagnose: which pid does each pywinauto backend report for calc windows?"""

from __future__ import annotations

import subprocess
import sys
import time

sys.path.insert(0, r"C:\Users\DELL\once")
from pywinauto import Desktop

proc = subprocess.Popen([r"C:\Windows\System32\calc.exe"])
time.sleep(2.5)
print("launched pid:", proc.pid)

for backend in ("uia", "win32"):
    try:
        windows = Desktop(backend=backend).windows()
    except Exception as error:
        print(f"{backend}: <{error}>")
        continue
    print(f"--- backend {backend}: {len(windows)} top-level windows")
    for wrapper in windows:
        info = wrapper.element_info
        name = (info.name or "")[:36]
        cls = str(getattr(info, "class_name", ""))[:22]
        if "calculator" in name.lower() or "calc" in cls.lower() or info.process_id == proc.pid:
            print(f"   pid={info.process_id} class={cls} title={name}")

# Also: who owns the window per Win32 native API?
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32


@ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
def _enum(hwnd, _lparam):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    length = user32.GetWindowTextLengthW(hwnd)
    title = ctypes.create_unicode_window_text_buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title, length + 1)
    if "caract" in title.value or pid.value == proc.pid:
        print(f"   native: hwnd={hwnd} pid={pid.value} title={title.value[:36]}")
    return True


user32.EnumWindows(_enum, 0)
subprocess.run(["taskkill", "/PID", str(proc.pid)], capture_output=True)
proc.wait(timeout=5)
print("closed")
