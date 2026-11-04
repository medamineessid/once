"""Tests for injected recorder integration boundaries."""

from __future__ import annotations

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
        isinstance(process_name, str) and isinstance(title, str) and title
        for process_name, title in windows
    )
