"""One-off live probe: isolated Chrome + DevTools endpoints (not a test)."""

from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
profile = Path(tempfile.mkdtemp(prefix="once-chrome-probe-"))

process = subprocess.Popen(
    [
        str(CHROME),
        "--remote-debugging-port=0",
        "--user-data-dir=" + str(profile / "profile"),
        "--no-first-run",
        "--no-default-browser-check",
        "--headless=new",
        "about:blank",
    ],
    shell=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

ws_url = None
deadline = time.monotonic() + 15
import threading


def reader():
    global ws_url
    for line in process.stderr:
        text = line.decode("utf-8", errors="replace").strip()
        if "DevTools listening" in text:
            ws_url = text.split("DevTools listening on ")[1].split()[0]


t = threading.Thread(target=reader, daemon=True)
t.start()
while ws_url is None and time.monotonic() < deadline:
    time.sleep(0.2)

print("ws_url:", ws_url)
port = int(ws_url.split("/")[2].split(":")[1])
print("port:", port)

conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
conn.request("GET", "/json/list")
targets = json.loads(conn.getresponse().read())
print("targets:")
for tg in targets:
    print("  type=", tg["type"], "title=", tg["title"][:40], "url=", tg["url"][:40])
    print("    ws:", tg.get("webSocketDebuggerUrl", "none")[:60])

# Open a new tab with PUT /json/new (Chrome 111+ requires PUT)
conn.request("PUT", "/json/new?http://example.com/")
resp = json.loads(conn.getresponse().read())
print("new tab:", resp.get("id"), resp.get("url"), resp.get("title"))
time.sleep(1.5)
conn.request("GET", "/json/list")
for tg in json.loads(conn.getresponse().read()):
    if tg["type"] == "page":
        print("  after: title=", tg["title"][:50], "url=", tg["url"][:50])

process.kill()
print("probe done; profile:", profile)
