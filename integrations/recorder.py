"""Windows input and screenshot adapters for the local recorder."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

from recorder.models import RecordedEvent, RecordedEventKind, UIElementInfo


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
    ) -> None:
        self._sink = sink
        self._element_provider = element_provider
        self._keyboard_enabled = keyboard_enabled
        self._sequence = 0
        self._mouse_listener = None
        self._keyboard_listener = None

    def start(self) -> None:
        """Start global listeners; keyboard capture remains opt-in."""
        from pynput import keyboard, mouse

        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._mouse_listener.start()
        if self._keyboard_enabled:
            self._keyboard_listener = keyboard.Listener(on_press=self._on_press)
            self._keyboard_listener.start()

    def stop(self) -> None:
        """Stop listeners and wait for their callback threads."""
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
        self._sequence += 1
        self._sink.append(
            RecordedEvent(
                sequence=self._sequence,
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
