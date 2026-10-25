"""One-off live probe: minimal stdlib WebSocket client against Chrome CDP."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class MiniWS:
    def __init__(self, url: str, timeout: float = 10.0) -> None:
        host, port, path = self._parse(url)
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        response = self._read_http_response()
        expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        if expected not in response:
            raise RuntimeError("WebSocket handshake failed")
        self._buf = b""

    @staticmethod
    def _parse(url):
        without = url[len("ws://") :]
        hostport, path = (without.split("/", 1) + [""])[:2]
        if ":" not in hostport:
            port = 443 if "wss" in url else 80
        else:
            port = int(hostport.split(":")[1])
        return hostport.split(":")[0], port, "/" + path

    def _read_http_response(self):
        data = b""
        while b"\r\n\r\n" not in data:
            data += self.sock.recv(4096)
        return data.decode("latin-1")

    def _recv_exact(self, n):
        while len(self._buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("socket closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _read_frame(self):
        header = self._recv_exact(2)
        fin_opcode, mask_len = header
        opcode = fin_opcode & 0x0F
        length = mask_len & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._recv_exact(8))[0]
        payload = self._recv_exact(length) if length else b""
        return opcode, payload

    def send_json(self, obj: dict) -> None:
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        header = bytearray([0x81])
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + mask + masked)

    def recv_message(self):
        """Return one complete text message, skipping ping and continuing frames."""
        payload = bytearray()
        opcode = None
        while True:
            code, chunk = self._read_frame()
            if code == 9 or code == 10:
                continue
            if code == 8:
                raise RuntimeError("websocket closed by peer")
            if code in (1, 2) and opcode is None:
                opcode = code
            payload += chunk
            finished = True  # frames already read to their declared length
            if not finished:
                continue
            # FIN bit check
            return json.loads(bytes(payload).decode())

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
profile = Path(tempfile.mkdtemp(prefix="once-chrome-probe2-"))
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


def reader():
    global ws_url
    for line in process.stderr:
        text = line.decode("utf-8", errors="replace")
        if "DevTools listening" in text:
            ws_url = text.split("DevTools listening on ")[1].split()[0]


threading.Thread(target=reader, daemon=True).start()
deadline = time.monotonic() + 15
while ws_url is None and time.monotonic() < deadline:
    time.sleep(0.2)
port = int(ws_url.split("/")[2].split(":")[1])
time.sleep(0.5)

import http.client

conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
conn.request("PUT", "/json/new?http://example.com/")
page = json.loads(conn.getresponse().read())
conn.close()
time.sleep(1.0)

conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
conn.request("GET", "/json/list")
page = [t for t in json.loads(conn.getresponse().read()) if t["type"] == "page" and "example" in t["url"]][0]
page_ws = page["webSocketDebuggerUrl"]
conn.close()
print("page ws:", page_ws)

ws = MiniWS(page_ws)
msgid = 0


def command(method, params=None):
    global msgid
    msgid += 1
    ws.send_json({"id": msgid, "method": method, "params": params or {}})
    while True:
        message = ws.recv_message()
        if message.get("id") == msgid:
            return message


r = command("Runtime.evaluate", {"expression": "document.title", "returnByValue": True})
print("title result:", r["result"]["result"])
r = command(
    "Runtime.evaluate",
    {"expression": "document.body.innerText.length", "returnByValue": True},
)
print("text length:", r["result"]["result"])
r = command("Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
print("href:", r["result"]["result"]["value"])
r = command("Runtime.evaluate", {"expression": "document.querySelector('h1') ? document.querySelector('h1').textContent : null", "returnByValue": True})
print("h1:", r["result"]["result"]["value"])
r = command("Page.navigate", {"url": "http://127.0.0.1/"})
print("navigate result keys:", r.get("result", {}).keys(), r.get("error"))
ws.close()
process.kill()
print("probe2 done")
