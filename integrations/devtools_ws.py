"""Minimal RFC 6455 WebSocket client (stdlib only) for Chrome DevTools.

Implemented for one narrow use: exchanging JSON messages with Chrome's local
DevTools endpoint on 127.0.0.1. It supports exactly what the CDP flow needs -
client-to-server masked text frames, unmasked server-to-client text frames,
message continuation, ping/pong kept-alive traffic, and close detection. No
compression, no server-initiated requests, no browser URLs (wss is refused).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_TEXT = 0x1
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

RECV_CHUNK = 65_536
MAX_FRAME_BYTES = 10_485_760


class WebSocketClosedError(Exception):
    """The peer closed the socket or the connection was lost."""


WebSocketClosed = WebSocketClosedError  # legacy alias used by provider code


class WebSocketClient:
    """A blocking RFC 6455 client bound to one ws://127.0.0.1 endpoint."""

    def __init__(self, url: str, timeout_seconds: float = 10.0) -> None:
        self._url = url
        if not url.startswith("ws://127.0.0.1:"):
            raise ValueError("DevTools connections must use ws://127.0.0.1:.")
        host, port, path = self._target_of(url)
        self.sock = socket.create_connection((host, port), timeout=timeout_seconds)
        self.sock.settimeout(timeout_seconds)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self._read_handshake_response()
        if f"Sec-WebSocket-Accept: {self._accept_of(key)}" not in response:
            self.close()
            raise ValueError("The DevTools endpoint refused the WebSocket handshake.")
        self._buffer = b""

    @property
    def url(self) -> str:
        return self._url

    @staticmethod
    def _target_of(url: str) -> tuple[str, int, str]:
        without_scheme = url[len("ws://") :]
        host_port, _, tail = without_scheme.partition("/")
        path = "/" + tail
        host, sep, port_text = host_port.partition(":")
        if not host or not sep or not port_text.isdigit():
            raise ValueError("The DevTools URL must contain an explicit localhost port.")
        return host, int(port_text), path

    @staticmethod
    def _accept_of(key: str) -> str:
        # The WebSocket opening-handshake accept value is SHA-1 by RFC 6455;
        # it is not used for any security property.
        return base64.b64encode(
            hashlib.sha1(  # noqa: S324
                (key + GUID).encode()
            ).digest()
        ).decode()

    def _read_handshake_response(self) -> str:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(RECV_CHUNK)
            if not chunk:
                raise WebSocketClosed("The socket closed during the handshake.")
            data += chunk
        return data.decode("latin-1")

    def _recv_exact(self, count: int) -> bytes:
        while len(self._buffer) < count:
            chunk = self.sock.recv(RECV_CHUNK)
            if not chunk:
                raise WebSocketClosed("The DevTools socket closed mid-frame.")
            self._buffer += chunk
        payload, self._buffer = self._buffer[:count], self._buffer[count:]
        return payload

    def _read_one_frame(self) -> tuple[int, bool, bytes]:
        first, second = self._recv_exact(2)
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        if second & 0x80:
            raise ValueError("DevTools frames must not be masked by the server.")
        length = second & 0x7F
        if length == 126:
            (length,) = struct.unpack(">H", self._recv_exact(2))
        elif length == 127:
            (length,) = struct.unpack(">Q", self._recv_exact(8))
        if length > MAX_FRAME_BYTES:
            raise ValueError("A DevTools frame exceeded the safety size bound.")
        return opcode, fin, self._recv_exact(length) if length else b""

    def send_json(self, message: dict) -> None:
        """Send one JSON object as a masked client text frame."""
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        mask = os.urandom(4)
        first = 0x80 | OP_TEXT
        length = len(data)
        if length < 126:
            header = struct.pack("!BB", first, 0x80 | length)
        elif length < 65_536:
            header = struct.pack("!BBH", first, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", first, 0x80 | 127, length)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(header + mask + masked)

    def receive_json(self) -> dict:
        """Return the next complete JSON message, absorbing pings and fragments."""
        fragments = bytearray()
        while True:
            opcode, fin, payload = self._read_one_frame()
            if opcode in (OP_PING, OP_PONG):
                continue
            if opcode == OP_CLOSE:
                self.close()
                raise WebSocketClosed("The DevTools endpoint closed the connection.")
            if opcode != OP_TEXT:
                raise ValueError(
                    f"Unexpected DevTools frame opcode {opcode}; only text is supported."
                )
            fragments += payload
            if fin:
                return json.loads(bytes(fragments).decode("utf-8"))

    def close(self) -> None:
        import contextlib

        with contextlib.suppress(OSError):
            self.sock.close()
