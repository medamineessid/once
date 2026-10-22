"""Tests for injected recorder integration boundaries."""

from __future__ import annotations

from integrations.recorder import PynputRecorder
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
