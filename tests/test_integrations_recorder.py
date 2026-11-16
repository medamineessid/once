"""Tests for injected recorder integration boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

from integrations.recorder import PynputRecorder, WindowEventMonitor
from recorder.models import RecordedEvent, RecordedEventKind, UIElementInfo


class EventCollector:
    def __init__(self) -> None:
        self.events: list[RecordedEvent] = []

    def append(self, event: RecordedEvent) -> None:
        self.events.append(event)


class PasswordElement:
    def current(self) -> UIElementInfo:
        return UIElementInfo(control_type="Edit", is_password=True)


def test_recorder_omits_key_events_in_password_fields() -> None:
    collector = EventCollector()
    recorder = PynputRecorder(
        collector,
        element_provider=PasswordElement(),
        keyboard_enabled=True,
    )

    recorder._on_press("secret")

    assert collector.events == []


def test_recorder_records_mouse_press_only() -> None:
    collector = EventCollector()
    recorder = PynputRecorder(collector)

    recorder._on_click(10, 20, object(), False)
    recorder._on_click(10, 20, object(), True)

    assert [event.kind for event in collector.events] == [RecordedEventKind.MOUSE_CLICK]
    assert collector.events[0].x == 10


def test_window_monitor_emits_open_and_close_observations() -> None:
    collector = EventCollector()
    pending: list[tuple[tuple[str, str], ...]] = [
        (),
        (("Code.exe", "Visual Studio Code"),),
        (("Code.exe", "Visual Studio Code"), ("notepad.exe", "demo.txt - Notepad")),
        (("notepad.exe", "demo.txt - Notepad"),),
    ]
    last: tuple[tuple[str, str], ...] = ()

    def snapshots() -> tuple[tuple[str, str], ...]:
        nonlocal last
        if pending:
            last = pending.pop(0)
        return last

    monitor = WindowEventMonitor(
        collector,
        window_lister=snapshots,
        interval_seconds=0.0,
        sleep=lambda _seconds: None,
    )
    monitor.start()
    for _ in range(10_000):
        if len(collector.events) >= 3:
            break
    monitor.stop()

    kinds = [event.kind for event in collector.events]
    assert kinds == [
        RecordedEventKind.WINDOW_OPEN,
        RecordedEventKind.WINDOW_OPEN,
        RecordedEventKind.WINDOW_CLOSE,
    ]
    opened = [event for event in collector.events if event.kind is RecordedEventKind.WINDOW_OPEN]
    assert [(event.process_name, event.window_title) for event in opened] == [
        ("Code.exe", "Visual Studio Code"),
        ("notepad.exe", "demo.txt - Notepad"),
    ]
    closed = [event for event in collector.events if event.kind is RecordedEventKind.WINDOW_CLOSE]
    assert closed[0].process_name == "Code.exe"
    assert closed[0].window_title == "Visual Studio Code"


def test_window_monitor_never_repeats_or_floods_the_baseline() -> None:
    collector = EventCollector()
    windows = (("Code.exe", "Visual Studio Code"), ("explorer.exe", "Program Manager"))

    monitor = WindowEventMonitor(
        collector,
        window_lister=lambda: windows,
        interval_seconds=0.0,
        sleep=lambda _seconds: None,
    )
    monitor.start()
    monitor.stop()

    assert collector.events == []


def test_window_monitor_survives_a_failing_window_lister() -> None:
    collector = EventCollector()
    pending: list[tuple[tuple[str, str], ...]] = [(), (("Code.exe", "Visual Studio Code"),)]
    last: tuple[tuple[str, str], ...] = ()
    failures = {"count": 0}

    def snapshots() -> tuple[tuple[str, str], ...]:
        nonlocal last
        if failures["count"] == 0:
            failures["count"] = 1
            raise OSError("The desktop changed")
        if pending:
            last = pending.pop(0)
        return last

    monitor = WindowEventMonitor(
        collector,
        window_lister=snapshots,
        interval_seconds=0.0,
        sleep=lambda _seconds: None,
    )
    monitor.start()
    for _ in range(10_000):
        if len(collector.events) >= 1:
            break
    monitor.stop()

    first = collector.events[0]
    assert (first.kind, first.process_name, first.window_title) == (
        RecordedEventKind.WINDOW_OPEN,
        "Code.exe",
        "Visual Studio Code",
    )


def test_window_monitor_open_events_share_one_sequence_space() -> None:
    collector = EventCollector()
    pending: list[tuple[tuple[str, str], ...]] = [
        (),
        (("Code.exe", "z second"), ("Code.exe", "a first")),
        (("Code.exe", "z second"),),
    ]
    last: tuple[tuple[str, str], ...] = ()

    def snapshots() -> tuple[tuple[str, str], ...]:
        nonlocal last
        if pending:
            last = pending.pop(0)
        return last

    monitor = WindowEventMonitor(
        collector,
        window_lister=snapshots,
        interval_seconds=0.0,
        sleep=lambda _seconds: None,
    )
    monitor.start()
    for _ in range(10_000):
        if len(collector.events) >= 3:
            break
    monitor.stop()

    sequences = [event.sequence for event in collector.events]
    assert sequences == [1, 2, 3]
    opened = [
        event.window_title
        for event in collector.events
        if event.kind is RecordedEventKind.WINDOW_OPEN
    ]
    assert opened == ["a first", "z second"]


def test_recorder_owns_and_guards_its_window_monitor() -> None:
    collector = EventCollector()
    default_recorder = PynputRecorder(collector)
    assert default_recorder._window_monitor is not None

    disabled_recorder = PynputRecorder(collector, window_monitor=None)
    assert disabled_recorder._window_monitor is None

    monitor = WindowEventMonitor(collector, window_lister=lambda: ())
    monitor.start()
    with pytest.raises(RuntimeError, match="already active"):
        monitor.start()
    monitor.stop()


def test_win32_window_list_requires_windows() -> None:
    import os

    from integrations.recorder import _win32_windows

    if os.name != "nt":
        with pytest.raises(OSError, match="only on Windows"):
            _win32_windows()
        pytest.skip("Window capture needs Windows")
    windows = _win32_windows()
    assert all(
        isinstance(process_name, str)
        and isinstance(title, str)
        and isinstance(image_path, str)
        and isinstance(hwnd, int)
        and title
        for process_name, title, image_path, hwnd in windows
    )


def test_window_monitor_emits_open_and_close_with_executable_path(tmp_path) -> None:
    exe_file = tmp_path / "app.exe"
    exe_file.write_bytes(b"MZ-test-binary")
    collector = EventCollector()
    pending: list[tuple[tuple[str, str, str], ...]] = [
        (),
        (("app.exe", "Sample App", str(exe_file)),),
        (),
    ]
    last: tuple[tuple[str, str, str], ...] = ()

    def snapshots() -> tuple[tuple[str, str, str], ...]:
        nonlocal last
        if pending:
            last = pending.pop(0)
        return last

    monitor = WindowEventMonitor(
        collector,
        window_lister=snapshots,
        interval_seconds=0.0,
        sleep=lambda _seconds: None,
    )
    import time

    monitor.start()
    for _ in range(500):
        if len(collector.events) >= 2:
            break
        time.sleep(0.002)
    monitor.stop()

    assert [event.kind for event in collector.events] == [
        RecordedEventKind.WINDOW_OPEN,
        RecordedEventKind.WINDOW_CLOSE,
    ]
    assert collector.events[0].executable_path == str(exe_file)
    assert collector.events[0].executable_sha256 is not None
    assert len(collector.events[0].executable_sha256) == 64


def test_window_monitor_tracks_hwnd_and_title_change_produces_no_close_open_flapping(
    tmp_path: Path,
) -> None:
    """Regression test using recording-1794212626041060300.json:

    When Windows Terminal changes title ('Windows PowerShell' -> '626346453/70264'
    -> 'Windows PowerShell'), tracking by HWND identity emits WINDOW_TITLE_CHANGED,
    never spurious WINDOW_CLOSE + WINDOW_OPEN pairs.
    """
    import json

    recording_path = Path(__file__).parent / "fixtures" / "recording-1794212626041060300.json"
    data = json.loads(recording_path.read_text(encoding="utf-8"))

    # Extract the distinct terminal titles from the real recording
    terminal_events = [e for e in data["events"] if e.get("process_name") == "WindowsTerminal.exe"]
    titles = [e["window_title"] for e in terminal_events]
    assert "626346453/70264" in titles
    assert "Windows PowerShell" in titles

    collector = EventCollector()
    wt_exe = "C:\\Program Files\\WindowsApps\\wt\\WindowsTerminal.exe"
    hwnd_wt = 0x1234
    hwnd_settings = 0x5678
    settings_exe = "C:\\Windows\\System32\\ApplicationFrameHost.exe"

    # Sequence of states where the same HWND undergoes title renames:
    snapshots_sequence: list[tuple[tuple[str, str, str, int], ...]] = [
        # Baseline: Terminal already open
        (("WindowsTerminal.exe", "Windows PowerShell", wt_exe, hwnd_wt),),
        # Step 1: Terminal title changes to transient PID title
        (("WindowsTerminal.exe", "626346453/70264", wt_exe, hwnd_wt),),
        # Step 2: Terminal title changes back
        (("WindowsTerminal.exe", "Windows PowerShell", wt_exe, hwnd_wt),),
        # Step 3: Settings window opens
        (
            ("WindowsTerminal.exe", "Windows PowerShell", wt_exe, hwnd_wt),
            ("ApplicationFrameHost.exe", "Paramètres", settings_exe, hwnd_settings),
        ),
        # Step 4: Settings window changes title internally on same HWND
        (
            ("WindowsTerminal.exe", "Windows PowerShell", wt_exe, hwnd_wt),
            ("ApplicationFrameHost.exe", "Paramètres - Système", settings_exe, hwnd_settings),
        ),
    ]

    current_idx = 0

    def next_snapshot() -> tuple[tuple[str, str, str, int], ...]:
        nonlocal current_idx
        idx = min(current_idx, len(snapshots_sequence) - 1)
        current_idx += 1
        return snapshots_sequence[idx]

    monitor = WindowEventMonitor(
        collector,
        window_lister=next_snapshot,
        interval_seconds=0.0,
        sleep=lambda _s: None,
    )
    monitor.start()
    for _ in range(500):
        if len(collector.events) >= 3:
            break
        import time

        time.sleep(0.002)
    monitor.stop()

    # Verify: NO close events occurred for the terminal or settings renames
    terminal_closes = [
        e
        for e in collector.events
        if e.kind is RecordedEventKind.WINDOW_CLOSE and e.process_name == "WindowsTerminal.exe"
    ]
    terminal_opens = [
        e
        for e in collector.events
        if e.kind is RecordedEventKind.WINDOW_OPEN and e.process_name == "WindowsTerminal.exe"
    ]
    title_changes = [
        e for e in collector.events if e.kind is RecordedEventKind.WINDOW_TITLE_CHANGED
    ]

    assert terminal_closes == []
    assert terminal_opens == []
    assert len(title_changes) >= 2
    assert title_changes[0].window_title == "626346453/70264"
    assert title_changes[1].window_title == "Windows PowerShell"
