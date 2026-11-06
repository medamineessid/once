"""Windows input and screenshot adapters for the local recorder."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from recorder.models import RecordedEvent, RecordedEventKind, UIElementInfo

WindowLister = Callable[[], tuple[tuple[str, str], ...]]


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

    def _emit(self, kind: RecordedEventKind, window: tuple[str, str]) -> None:
        process_name, title = window
        self._sink.append(
            RecordedEvent(
                sequence=self._sequence_source(),
                timestamp_ns=time.time_ns(),
                kind=kind,
                window_title=title,
                process_name=process_name,
            )
        )


def _win32_windows() -> tuple[tuple[str, str], ...]:
    """Enumerate visible top-level windows with titles as (process name, title)."""
    if os.name != "nt":
        raise OSError("Window capture is available only on Windows.")
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    results: list[tuple[str, str]] = []
    enum_process = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def on_window(hwnd: int, _lparam: object) -> bool:
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            buffer = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
            user32.GetWindowTextW(hwnd, buffer, len(buffer))
            exstyle = user32.GetWindowLongPtrW(hwnd, -20)  # GWL_EXSTYLE
            if not exstyle & 0x80:  # WS_EX_TOOLWINDOW windows are chrome, not tasks
                process_id = ctypes.c_ulong(0)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
                name = _win32_process_name(kernel32, process_id.value)
                if name:
                    results.append((name, buffer.value))
        return True

    user32.EnumWindows(enum_process(on_window), 0)
    return tuple(results)


def _win32_process_name(kernel32: object, process_id: int) -> str:
    import ctypes

    handle = kernel32.OpenProcess(0x1000, False, process_id)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        size = ctypes.c_ulong(512)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return Path(buffer.value).name
    finally:
        kernel32.CloseHandle(handle)
