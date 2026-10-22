"""Privacy filtering for recording events."""

from __future__ import annotations

from dataclasses import replace

from .models import RecordedEvent


def redact_event(event: RecordedEvent) -> RecordedEvent:
    """Remove secrets from an event before it can be persisted or analyzed."""
    element = event.element
    is_password = element is not None and element.is_password
    if is_password:
        return replace(event, text=None, key=None)
    return event


def redact_events(events: tuple[RecordedEvent, ...]) -> tuple[RecordedEvent, ...]:
    """Redact all events deterministically while preserving their order."""
    return tuple(redact_event(event) for event in events)
