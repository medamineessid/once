"""Immutable models for local recordings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RecordedEventKind(StrEnum):
    """Kinds of input observations retained by the recorder."""

    MOUSE_CLICK = "MOUSE_CLICK"
    KEY_PRESS = "KEY_PRESS"
    TEXT_INPUT = "TEXT_INPUT"
    WINDOW_FOCUS = "WINDOW_FOCUS"


@dataclass(frozen=True)
class UIElementInfo:
    """Non-secret metadata describing the observed UI element."""

    automation_id: str | None = None
    control_type: str | None = None
    name: str | None = None
    class_name: str | None = None
    is_password: bool = False


@dataclass(frozen=True)
class RecordedEvent:
    """One ordered observation from a recording session."""

    sequence: int
    timestamp_ns: int
    kind: RecordedEventKind
    window_title: str | None = None
    element: UIElementInfo | None = None
    x: int | None = None
    y: int | None = None
    key: str | None = None
    text: str | None = None
    screenshot_name: str | None = None


@dataclass(frozen=True)
class Recording:
    """A complete immutable recording event log."""

    recording_id: str
    started_at_ns: int
    events: tuple[RecordedEvent, ...]
