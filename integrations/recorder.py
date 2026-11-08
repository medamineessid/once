"""Windows input, UI Automation, and screenshot adapters for the local recorder."""

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

_CTRL_KEY_NAMES = frozenset({"Key.ctrl", "Key.ctrl_l", "Key.ctrl_r"})
_SPECIAL_SHORTCUTS: dict[str, str] = {
    "Key.enter": "enter",
    "Key.esc": "escape",
    "Key.tab": "tab",
}
_CTRL_LETTERS = frozenset({"s", "a", "c", "v", "x", "z", "y"})


class EventSink(Protocol):
    """Receive already-redacted recording observations."""

    def append(self, event: RecordedEvent) -> None:
        """Accept one event."""


class ElementProvider(Protocol):
    """Describe the currently focused UI element."""

    def current(self) -> UIElementInfo | None:
        """Return non-secret metadata for the current element."""


class UIAElementProvider:
    """Inspect Windows UI Automation elements and top-level windows without coordinates."""

    def __init__(self, own_pid: int | None = None) -> None:
        self._own_pid = os.getpid() if own_pid is None else own_pid

    def current(self) -> UIElementInfo | None:
        element, _title, _proc, _exe, is_self = self.inspect_focused()
        return None if is_self else element

    def inspect_point(
        self, x: int, y: int
    ) -> tuple[UIElementInfo | None, str | None, str | None, str | None, bool]:
        """Return (element, window_title, process_name, executable_path, is_self_process)."""
        if os.name != "nt":
            return None, None, None, None, False
        try:
            import ctypes

            from pywinauto import Desktop

            wrapper = Desktop(backend="uia").from_point(x, y)
            if wrapper is None:
                return None, None, None, None, False
            info = wrapper.element_info
            pid = getattr(info, "process_id", None)
            if isinstance(pid, int) and pid == self._own_pid:
                return None, None, None, None, True
            top = wrapper.top_level_parent()
            top_info = getattr(top, "element_info", info)
            top_pid = getattr(top_info, "process_id", pid)
            if isinstance(top_pid, int) and top_pid == self._own_pid:
                return None, None, None, None, True
            window_title = (getattr(top_info, "name", None) or "").strip() or None
            exe_path: str | None = None
            proc_name: str | None = None
            if isinstance(top_pid, int) and top_pid > 0:
                raw_exe = _win32_process_image_path(ctypes.windll.kernel32, top_pid)
                if raw_exe:
                    exe_path = raw_exe
                    proc_name = Path(raw_exe).name
            element = _to_element_info(info)
            return element, window_title, proc_name, exe_path, False
        except Exception:
            return None, None, None, None, False

    def inspect_focused(
        self,
    ) -> tuple[UIElementInfo | None, str | None, str | None, str | None, bool]:
        """Inspect the foreground window and focused UI element."""
        if os.name != "nt":
            return None, None, None, None, False
        try:
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None, None, None, None, False
            pid_c = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
            pid = int(pid_c.value)
            if pid == self._own_pid:
                return None, None, None, None, True
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, len(buf))
            window_title = buf.value.strip() or None
            raw_exe = _win32_process_image_path(kernel32, pid) if pid > 0 else ""
            exe_path = raw_exe or None
            proc_name = Path(raw_exe).name if raw_exe else None
            element: UIElementInfo | None = None
            try:
                from pywinauto.uia_element_info import UIAElementInfo

                focused_info = UIAElementInfo()
                if getattr(focused_info, "process_id", None) == pid:
                    element = _to_element_info(focused_info)
            except Exception:
                element = None
            return element, window_title, proc_name, exe_path, False
        except Exception:
            return None, None, None, None, False


def _to_element_info(info: object) -> UIElementInfo:
    auto_id = (getattr(info, "automation_id", None) or "").strip() or None
    ctrl_type = (getattr(info, "control_type", None) or "").strip() or None
    name = (getattr(info, "name", None) or "").strip() or None
    cls_name = (getattr(info, "class_name", None) or "").strip() or None
    is_pwd = bool(getattr(info, "is_password", False)) or (
        isinstance(name, str) and "password" in name.casefold()
    )
    return UIElementInfo(
        automation_id=auto_id,
        control_type=ctrl_type,
        name=name[:120] if name else None,
        class_name=cls_name,
        is_password=is_pwd,
    )


class PynputRecorder:
    """Capture mouse clicks, semantic UIA targets, text input, and shortcuts while active."""

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
        self._seen_executables: set[str] = set()
        self._ctrl_down = False
        self._text_buffer: list[str] = []
        self._text_context: (
            tuple[UIElementInfo | None, str | None, str | None, str | None] | None
        ) = None
        self._mouse_listener = None
        self._keyboard_listener = None
        if window_monitor is _OWN_MONITOR:
            window_monitor = WindowEventMonitor(
                sink,
                sequence_source=self._next_sequence,
                seen_executables=self._seen_executables,
            )
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

        self._seen_executables.clear()
        self._text_buffer.clear()
        self._text_context = None
        self._ctrl_down = False
        if self._window_monitor is not None:
            self._window_monitor.start()
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._mouse_listener.start()
        if self._keyboard_enabled:
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._keyboard_listener.start()

    def stop(self) -> None:
        """Stop listeners and wait for their callback threads."""
        self._flush_text_buffer()
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
        self._flush_text_buffer()
        inspector = getattr(self._element_provider, "inspect_point", None)
        if callable(inspector):
            element, win_title, proc_name, exe_path, is_self = inspector(x, y)
            if is_self:
                return
            self._ensure_window_opened(win_title, proc_name, exe_path)
            self._append(
                RecordedEventKind.MOUSE_CLICK,
                x=x,
                y=y,
                element=element,
                window_title=win_title,
                process_name=proc_name,
                executable_path=exe_path,
            )
            return
        self._append(
            RecordedEventKind.MOUSE_CLICK,
            x=x,
            y=y,
            element=self._current_element(),
        )

    def _on_release(self, key: object, *_args: object) -> None:
        if str(key) in _CTRL_KEY_NAMES:
            self._ctrl_down = False

    def _on_press(self, key: object, *_args: object) -> None:
        key_str = str(key)
        if key_str in _CTRL_KEY_NAMES:
            self._ctrl_down = True
            return
        focused_inspector = getattr(self._element_provider, "inspect_focused", None)
        if callable(focused_inspector):
            element, win_title, proc_name, exe_path, is_self = focused_inspector()
            if is_self:
                return
        else:
            element = self._current_element()
            win_title, proc_name, exe_path = None, None, None
        if element is not None and element.is_password:
            self._text_buffer.clear()
            self._text_context = None
            return
        if not callable(focused_inspector):
            self._append(
                RecordedEventKind.KEY_PRESS,
                key=None,
                element=element,
            )
            return
        shortcut = self._extract_shortcut(key, key_str)
        if shortcut is not None:
            self._flush_text_buffer()
            self._ensure_window_opened(win_title, proc_name, exe_path)
            self._append(
                RecordedEventKind.KEY_PRESS,
                key=shortcut,
                element=element,
                window_title=win_title,
                process_name=proc_name,
                executable_path=exe_path,
            )
            return
        char = self._extract_printable_char(key, key_str)
        if char is not None:
            if not self._text_buffer:
                self._text_context = (element, win_title, proc_name, exe_path)
            self._text_buffer.append(char)

    def _extract_shortcut(self, key: object, key_str: str) -> str | None:
        if key_str in _SPECIAL_SHORTCUTS:
            return _SPECIAL_SHORTCUTS[key_str]
        char = getattr(key, "char", None)
        if self._ctrl_down and isinstance(char, str) and len(char) == 1:
            # Ctrl+letter in pynput can arrive as control code \x01..\x1a or letter
            code = ord(char)
            letter = chr(code + 96) if 1 <= code <= 26 else char.lower()
            if letter in _CTRL_LETTERS:
                return f"ctrl+{letter}"
        return None

    def _extract_printable_char(self, key: object, key_str: str) -> str | None:
        if self._ctrl_down:
            return None
        if key_str == "Key.space":
            return " "
        if key_str == "Key.backspace":
            if self._text_buffer:
                self._text_buffer.pop()
            return None
        char = getattr(key, "char", None)
        if isinstance(char, str) and len(char) == 1 and ord(char) >= 32:
            return char
        return None

    def _flush_text_buffer(self) -> None:
        if not self._text_buffer:
            return
        text = "".join(self._text_buffer)
        context = self._text_context
        self._text_buffer.clear()
        self._text_context = None
        if not text:
            return
        element, win_title, proc_name, exe_path = context or (None, None, None, None)
        if element is not None and element.is_password:
            return
        self._ensure_window_opened(win_title, proc_name, exe_path)
        self._append(
            RecordedEventKind.TEXT_INPUT,
            element=element,
            text=text[:500],
            window_title=win_title,
            process_name=proc_name,
            executable_path=exe_path,
        )

    def _ensure_window_opened(
        self,
        window_title: str | None,
        process_name: str | None,
        executable_path: str | None,
    ) -> None:
        """Emit WINDOW_OPEN once when the user acts inside an already-open app window."""
        if not executable_path or not window_title:
            return
        norm = os.path.normcase(executable_path)
        if Path(norm).stem.lower() == "explorer":
            return
        with self._sequence_lock:
            if norm in self._seen_executables:
                return
            self._seen_executables.add(norm)
            seq = self._sequence + 1
            self._sequence = seq
        sha256 = _file_sha256(executable_path)
        self._sink.append(
            RecordedEvent(
                sequence=seq,
                timestamp_ns=time.time_ns(),
                kind=RecordedEventKind.WINDOW_OPEN,
                window_title=window_title,
                process_name=process_name or Path(executable_path).name,
                executable_path=executable_path,
                executable_sha256=sha256,
            )
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
        text: str | None = None,
        element: UIElementInfo | None = None,
        window_title: str | None = None,
        process_name: str | None = None,
        executable_path: str | None = None,
    ) -> None:
        self._sink.append(
            RecordedEvent(
                sequence=self._next_sequence(),
                timestamp_ns=time.time_ns(),
                kind=kind,
                window_title=window_title,
                process_name=process_name,
                executable_path=executable_path,
                element=element,
                x=x,
                y=y,
                key=key,
                text=text,
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
        seen_executables: set[str] | None = None,
    ) -> None:
        self._sink = sink
        self._sequence_source = sequence_source or self._local_sequence
        self._window_lister = window_lister or _win32_windows
        self._interval = interval_seconds
        self._sleep = sleep
        self._seen_executables = seen_executables if seen_executables is not None else set()
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
            if kind is RecordedEventKind.WINDOW_OPEN:
                self._seen_executables.add(os.path.normcase(executable_path))
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
    _ = path
    return None
