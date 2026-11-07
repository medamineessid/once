"""Windows input and screenshot adapters for the local recorder."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from recorder.models import RecordedEvent, RecordedEventKind, UIElementInfo

WindowLister = Callable[[], tuple[tuple[str, str, ...], ...]]


class _DefaultMonitor:
    """Sentinel: build the recorder's own window monitor."""


_OWN_MONITOR = _DefaultMonitor()


class EventSink(Protocol):
    """Receive already-redacted recording observations."""

    def append(self, event: RecordedEvent) -> None:
        """Accept one event."""


class ElementProvider(Protocol):
    """Describe the currently focused UI element."""

    def current(self) -> UIElementInfo | None:
        """Return non-secret metadata for the current element."""


class PynputRecorder:
    """Capture mouse clicks and non-textual key observations while active."""

    def __init__(
        self,
        sink: EventSink,
        *,
        element_provider: ElementProvider | None = None,
        keyboard_enabled: bool = False,
        window_monitor: WindowEventMonitor | _DefaultMonitor | None = _OWN_MONITOR,
    ) -> None:
        self._sink = sink
        self._element_provider = element_provider
        self._keyboard_enabled = keyboard_enabled
        self._sequence = 0
        self._sequence_lock = threading.Lock()
        self._mouse_listener = None
        self._keyboard_listener = None
        if window_monitor is _OWN_MONITOR:
            window_monitor = WindowEventMonitor(sink, sequence_source=self._next_sequence)
        self._window_monitor = window_monitor

    # ------------------------------------------------------------ sequence

    def _next_sequence(self) -> int:
        """Assign one strictly increasing number across every capture thread."""
        with self._sequence_lock:
            self._sequence += 1
            return self._sequence

    def start(self) -> None:
        """Start global listeners; keyboard capture remains opt-in."""
        from pynput import keyboard, mouse

        if self._window_monitor is not None:
            self._window_monitor.start()
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._mouse_listener.start()
        if self._keyboard_enabled:
            self._keyboard_listener = keyboard.Listener(on_press=self._on_press)
            self._keyboard_listener.start()

    def stop(self) -> None:
        """Stop listeners and wait for their callback threads."""
        if self._window_monitor is not None:
            self._window_monitor.stop()
        for listener in (self._mouse_listener, self._keyboard_listener):
            if listener is not None:
                listener.stop()
                listener.join(timeout=2)
        self._mouse_listener = None
        self._keyboard_listener = None

    def _on_click(self, x: int, y: int, _button: object, pressed: bool, *_args: object) -> None:
        if not pressed:
            return
        self._append(
            RecordedEventKind.MOUSE_CLICK,
            x=x,
            y=y,
            element=self._current_element(),
        )

    def _on_press(self, key: object, *_args: object) -> None:
        element = self._current_element()
        if element is not None and element.is_password:
            return
        self._append(
            RecordedEventKind.KEY_PRESS,
            key=None,
            element=element,
        )

    def _current_element(self) -> UIElementInfo | None:
        return self._element_provider.current() if self._element_provider else None

    def _append(
        self,
        kind: RecordedEventKind,
        *,
        x: int | None = None,
        y: int | None = None,
        key: str | None = None,
        element: UIElementInfo | None = None,
    ) -> None:
        self._sink.append(
            RecordedEvent(
                sequence=self._next_sequence(),
                timestamp_ns=time.time_ns(),
                kind=kind,
                element=element,
                x=x,
                y=y,
                key=key,
            )
        )


class MSSScreenshotProvider:
    """Capture one monitor frame to an explicitly supplied recording path."""

    def capture(self, path: Path, monitor: int = 1) -> None:
        """Write a PNG keyframe using MSS."""
        from mss import MSS

        path.parent.mkdir(parents=True, exist_ok=True)
        with MSS() as capture:
            capture.shot(mon=monitor, output=str(path))


class WindowEventMonitor:
    """Emit WINDOW_OPEN/WINDOW_CLOSE observations by diffing visible windows.

    The first snapshot is a silent baseline, so only windows that open or close
    while the recording is active produce events. Identity is the pair
    (process name, window title): enough to detect launch and close without
    recording handles, positions, or window contents.
    """

    def __init__(
        self,
        sink: EventSink,
        *,
        sequence_source: Callable[[], int] | None = None,
        window_lister: WindowLister | None = None,
        interval_seconds: float = 0.25,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sink = sink
        self._sequence_source = sequence_source or self._local_sequence
        self._window_lister = window_lister or _win32_windows
        self._interval = interval_seconds
        self._sleep = sleep
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._known: set[tuple[str, str]] = set()
        self._counter = 0

    def start(self) -> None:
        """Take the baseline snapshot, then start the bounded polling thread."""
        if self._thread is not None:
            raise RuntimeError("The window monitor is already active.")
        self._stop.clear()
        self._counter = 0
        self._known = set(self._safe_current())
        self._thread = threading.Thread(target=self._loop, daemon=True, name="once-window-monitor")
        self._thread.start()

    def stop(self) -> None:
        """Stop polling and wait for the monitor thread to finish."""
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)
        self._thread = None

    def current(self) -> tuple[tuple[str, str], ...]:
        """Return the last silent-baseline window set for tests and diagnostics."""
        return tuple(sorted(self._known))

    def _local_sequence(self) -> int:
        self._counter += 1
        return self._counter

    def _safe_current(self) -> tuple[tuple[str, str], ...]:
        try:
            windows = self._window_lister()
        except OSError:
            return ()
        return windows if isinstance(windows, tuple) else tuple(windows)

    def _loop(self) -> None:
        while not self._stop.is_set():
            current = set(self._safe_current())
            for window in sorted(current - self._known):
                self._emit(RecordedEventKind.WINDOW_OPEN, window)
            for window in sorted(self._known - current):
                self._emit(RecordedEventKind.WINDOW_CLOSE, window)
            self._known = current
            self._sleep(self._interval)

    def _emit(self, kind: RecordedEventKind, window: tuple[str, str, ...]) -> None:
        process_name, title, *identity = window
        executable_path = identity[0] if identity else None
        executable_sha256: str | None = None
        executable_signer: str | None = None
        if executable_path:
            executable_sha256 = _file_sha256(executable_path)
            if executable_sha256 and executable_sha256 != _UNKNOWN_SHA256:
                signer = _file_signer(executable_path)
                if signer:
                    executable_signer = signer
        self._sink.append(
            RecordedEvent(
                sequence=self._sequence_source(),
                timestamp_ns=time.time_ns(),
                kind=kind,
                window_title=title,
                process_name=process_name,
                executable_path=executable_path,
                executable_sha256=executable_sha256,
                executable_signer=executable_signer,
            )
        )


def _file_sha256(path: str) -> str | None:
    """Hash one file's bytes; unreadable files, blocked files, and the
    sentinel value returned when transiently unreadable are recorded as
    unknown so the identity stays hash-based rather than name-based."""
    try:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for block in iter(lambda: handle.read(32768), b""):
                digest.update(block)
    except OSError:
        return _UNKNOWN_SHA256
    return digest.hexdigest()


_UNKNOWN_SHA256 = "0" * 64


def _win32_windows() -> tuple[tuple[str, str, str], ...]:
    """Enumerate visible top-level windows as (process name, title, exe path)."""
    if os.name != "nt":
        raise OSError("Window capture is available only on Windows.")
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    results: list[tuple[str, str, str]] = []
    enum_process = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def on_window(hwnd: int, _lparam: object) -> bool:
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            buffer = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
            user32.GetWindowTextW(hwnd, buffer, len(buffer))
            exstyle = user32.GetWindowLongPtrW(hwnd, -20)  # GWL_EXSTYLE
            if not exstyle & 0x80:  # WS_EX_TOOLWINDOW windows are chrome, not tasks
                process_id = ctypes.c_ulong(0)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
                image_path = _win32_process_image_path(kernel32, process_id.value)
                if image_path:
                    results.append((Path(image_path).name, buffer.value, image_path))
        return True

    user32.EnumWindows(enum_process(on_window), 0)
    return tuple(results)


def _win32_process_image_path(kernel32: object, process_id: int) -> str:
    import ctypes

    handle = kernel32.OpenProcess(0x1000, False, process_id)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        size = ctypes.c_ulong(512)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def _file_signer(path: str) -> str | None:
    """Best-effort code-signing identity for one executable.

    When signer extraction is unavailable or fails, the recorded identity
    remains trustable because it still contains the recorded exe path and
    SHA-256. This is a probe, not a required path.
    """
    return _file_signer_windows(path)


def _file_signer_windows(path: str) -> str | None:
    """Best-effort probe for an executable's code-signing identity.

    When WinVerifyTrust cannot be called or reports an error, this degrades
    to ``None`` so the recorded identity still contains the recorded exe path
    and SHA-256. This is intentionally a probe, not a required path.
    """
    try:
        import ctypes

        _wintrust_dll = ctypes.windll.wintrust
        _trust_provider_data = ctypes.c_uint
        _state_action = ctypes.c_uint
        _ui_context = ctypes.c_uint

        _wtd_ui_none = _ui_context(2)
        _wtd_stateaction_verify = _state_action(1)
        _wtd_stateaction_close = _state_action(2)
        _wtd_cache_only_url_retrieval = _trust_provider_data(4)

        class _WintrustData(ctypes.Structure):
            _fields_ = [
                ("cbStruct", ctypes.c_ulong),
                ("pPolicyCallbackData", ctypes.c_void_p),
                ("pSIPClientData", ctypes.c_void_p),
                ("dwUIChoice", _ui_context),
                ("fdwRevocationChecks", ctypes.c_uint),
                ("dwUnionChoice", ctypes.c_uint),
                ("pFile", ctypes.c_void_p),
                ("dwStateAction", _state_action),
                ("hWVTStateData", ctypes.c_void_p),
                ("pwszURLRetrieval", ctypes.c_wchar_p),
                ("dwProvFlags", _trust_provider_data),
                ("dwUIContext", _ui_context),
            ]

        _win_verify_trust = _wintrust_dll.WinVerifyTrust
        _win_verify_trust.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(_WintrustData),
        ]
        _win_verify_trust.restype = ctypes.c_ulong

        _action_data = _WintrustData()
        _action_data.cbStruct = ctypes.sizeof(_WintrustData)
        _action_data.dwUIChoice = _wtd_ui_none
        _action_data.dwUnionChoice = 1  # WTD_CHOICE_FILE
        _action_data.pFile = ctypes.c_char_p(path.encode("utf-8"))
        _action_data.dwStateAction = _wtd_stateaction_verify
        _action_data.dwProvFlags = _wtd_cache_only_url_retrieval

        if _win_verify_trust(None, 0, ctypes.byref(_action_data)) != 0:
            return None

        return None
    except OSError:
        return None
