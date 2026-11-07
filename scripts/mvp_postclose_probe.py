"""Follow-up truth probe: after a provider close (windows_closed=1), what state?"""

from __future__ import annotations

import subprocess
import sys

PID = 13980  # charmap closed by mvp_close_probe (windows_closed=1)

check = subprocess.run(
    ["tasklist", "/FI", f"PID eq {PID}", "/FO", "CSV", "/NH"],
    capture_output=True,
    text=True,
)
print("process 13980 alive?", "no" if "INFO:" in check.stdout else check.stdout.strip())

sys.path.insert(0, r"C:\Users\DELL\once")
from pywinauto import Desktop  # noqa: E402

windows = [w.element_info.process_id for w in Desktop(backend="uia").windows()]
print("13980 windows remaining on desktop:", windows.count(13980))
print("all charmap pids with windows on desktop:", sorted(set(windows)))
