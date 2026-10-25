"""Transport-level tests for the DevTools WebSocket client.

Each test runs against a real localhost socket whose server side is a
scripted byte stream — no Chrome, no network. The server performs the
RFC 6455 handshake and then emits the scripted frames, so every behavior is
exercised at the exact byte level the provider-level fakes never cover.
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import struct
import threading
import time

import pytest

from integrations.devtools_ws import (
    MAX_FRAME_BYTES,
    WebSocketClient,
    WebSocketClosed,
)

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MASK_KEY = b"\x11\x22\x33\x44"
TEXT = 0x1
CONT = 0x0
CLOSE = 0x8
PING = 0x9


def encode_frame(
    opcode: int,
    payload: bytes = b"",
    *,
    fin: bool = True,
    mask: bool = False,
) -> bytes:
    """Build one server-to-client frame exactly as scripted."""
    first = (0x80 if fin else 0) | opcode
    length = len(payload)
    mask_bit = 0x80 if mask else 0
    if length < 126:
        header = struct.pack("!BB", first, mask_bit | length)
    elif length < 65_536:
        header = struct.pack("!BBH", first, mask_bit | 126, length)
    else:
        header = struct.pack("!BBQ", first, mask_bit | 127, length)
    if not mask:
        return header + payload
    masked = bytes(byte ^ MASK_KEY[index % 4] for index, byte in enumerate(payload))
    return header + MASK_KEY + masked


class ScriptedServer:
    """Accepts exactly one localhost WebSocket client and runs a script.

    Script steps: ("send", bytes), ("recv_exact", n -> appended to .reads),
    ("sleep", seconds). After the script the connection is closed.
    """

    def __init__(self, script: list[tuple]) -> None:
        self.reads: list[bytes] = []
        self._script = list(script)
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self.port = self._listener.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        connection, _ = self._listener.accept()
        try:
            connection.settimeout(10)
            self._handshake(connection)
            for name, value in self._script:
                if name == "send":
                    connection.sendall(value)
                elif name == "recv_exact":
                    self.reads.append(self._recv_exact(connection, value))
                elif name == "sleep":
                    time.sleep(value)
        finally:
            import contextlib

            with contextlib.suppress(OSError):
                connection.close()
            self._listener.close()

    @staticmethod
    def _recv_exact(connection: socket.socket, count: int) -> bytes:
        buffer = b""
        while len(buffer) < count:
            chunk = connection.recv(count - len(buffer))
            if not chunk:
                break
            buffer += chunk
        return buffer

    def _handshake(self, connection: socket.socket) -> None:
        request = b""
        while b"\r\n\r\n" not in request:
            request += connection.recv(4096)
        for line in request.decode("latin-1").split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
                break
        else:
            raise AssertionError("client sent no Sec-WebSocket-Key")
        # The RFC 6455 opening-handshake accept value is SHA-1 by definition
        # of the protocol; it carries no security property.
        accept = base64.b64encode(
            hashlib.sha1((key + GUID).encode()).digest()  # noqa: S324
        ).decode()
        connection.sendall(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("ascii")
        )


def unmask(masked: bytes, mask_key: bytes) -> bytes:
    return bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(masked))


def connect_to(server: ScriptedServer) -> WebSocketClient:
    return WebSocketClient(f"ws://127.0.0.1:{server.port}/devtools/page/x")


def test_client_reassembles_a_fragmented_message() -> None:
    server = ScriptedServer(
        [
            ("send", encode_frame(TEXT, b'{"a": ', fin=False)),
            ("send", encode_frame(CONT, b"123}")),
        ]
    )
    client = connect_to(server)
    try:
        assert client.receive_json() == {"a": 123}
    finally:
        client.close()
        server.thread.join(timeout=5)


def test_ping_is_answered_with_an_identical_pong_payload() -> None:
    pong_payload = b"probe-pong"
    server = ScriptedServer(
        [
            ("send", encode_frame(PING, pong_payload)),
            ("recv_exact", 2 + 4 + len(pong_payload)),
            ("send", encode_frame(TEXT, b'{"after": "ping"}')),
        ]
    )
    client = connect_to(server)
    try:
        assert client.receive_json() == {"after": "ping"}
        raw = server.reads[0]
        first, second = struct.unpack("!BB", raw[:2])
        assert first & 0x0F == 0xA, "the client must answer with a pong frame"
        assert first & 0x80, "the pong frame must have FIN set"
        assert (second & 0x7F) == len(pong_payload)
        received = unmask(raw[6:], raw[2:6])
        assert received == pong_payload, "the pong repeats the ping payload"
        assert second & 0x80, "the pong must be masked client-to-server"
    finally:
        client.close()
        server.thread.join(timeout=5)


def test_server_close_frame_ends_the_stream() -> None:
    server = ScriptedServer([("send", encode_frame(CLOSE, b""))])
    client = connect_to(server)
    try:
        with pytest.raises(WebSocketClosed, match="closed the connection"):
            client.receive_json()
    finally:
        client.close()
        server.thread.join(timeout=5)


def test_outgoing_frames_are_masked_text_frames() -> None:
    small = {"small": "payload"}
    large = {"padding": "x" * 400}  # exercises the 16-bit length path
    script: list[tuple] = [("send", encode_frame(TEXT, b'{"ack": true}'))]
    script[1:1] = [
        ("recv_exact", 2 + 4 + len(json.dumps(small).encode())),
        ("recv_exact", 2 + 4 + 2 + len(json.dumps(large).encode())),
    ]
    server = ScriptedServer(
        [
            ("recv_exact", 2 + 4 + len(json.dumps(small).encode())),
            ("recv_exact", 2 + 4 + 2 + len(json.dumps(large).encode())),
            ("send", encode_frame(TEXT, b'{"ack": true}')),
        ]
    )
    client = connect_to(server)
    try:
        client.send_json(small)
        client.send_json(large)
        assert client.receive_json() == {"ack": True}

        def parse_frame(raw: bytes) -> dict:
            first, second = struct.unpack("!BB", raw[:2])
            assert first & 0x0F == TEXT, "client frames must be text frames"
            assert first & 0x80, "client frames must have FIN set"
            assert second & 0x80, "client frames must be masked (RFC 6455)"
            length = second & 0x7F
            offset = 2
            if length == 126:
                (length,) = struct.unpack("!H", raw[2:4])
                offset = 4
            mask_key = raw[offset : offset + 4]
            return json.loads(unmask(raw[offset + 4 :], mask_key))

        small_sent = parse_frame(server.reads[0])
        large_sent = parse_frame(server.reads[1])
        assert small_sent == small
        assert large_sent == large
        assert len(large_sent["padding"]) == 400
    finally:
        client.close()
        server.thread.join(timeout=5)


def test_declared_frame_over_the_size_limit_is_refused() -> None:
    oversized_header = struct.pack("!BBQ", 0x81, 0x7F, MAX_FRAME_BYTES + 1)
    server = ScriptedServer([("send", oversized_header)])
    client = connect_to(server)
    try:
        with pytest.raises(ValueError, match="exceeded the safety size bound"):
            client.receive_json()
    finally:
        client.close()
        server.thread.join(timeout=5)


def test_masked_server_frame_is_refused() -> None:
    server = ScriptedServer([("send", encode_frame(TEXT, b'{"masked": true}', mask=True))])
    client = connect_to(server)
    try:
        with pytest.raises(ValueError, match="must not be masked"):
            client.receive_json()
    finally:
        client.close()
        server.thread.join(timeout=5)


def test_connection_drop_mid_frame_is_detected() -> None:
    declared = 600
    body = b"A" * 100  # only 100 of the 600 declared bytes arrive, then EOF
    server = ScriptedServer(
        [
            ("send", struct.pack("!BBH", 0x81, 126, declared) + body),
        ]
    )
    client = connect_to(server)
    try:
        with pytest.raises(WebSocketClosed, match="closed mid-frame"):
            client.receive_json()
    finally:
        client.close()
        server.thread.join(timeout=5)


def test_silent_server_hits_the_read_timeout() -> None:
    server = ScriptedServer([("sleep", 2.0)])
    client = connect_to_with_timeout(server, 0.3)
    try:
        with pytest.raises(TimeoutError):
            client.receive_json()
    finally:
        client.close()
        server.thread.join(timeout=5)


def connect_to_with_timeout(server: ScriptedServer, timeout_seconds: float):
    return WebSocketClient(
        f"ws://127.0.0.1:{server.port}/devtools/page/x", timeout_seconds=timeout_seconds
    )
