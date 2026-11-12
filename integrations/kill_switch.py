"""Global kill switch that stops a running desktop replay from the keyboard.

While an approved desktop replay runs, Once may be clicking and typing in other
applications, so its own window is often hidden. The kill switch listens for one
global hotkey and, when pressed, marks the run cancelled; the engine checks the
flag before every step, so no further step starts. The hotkey is deliberately
absent from the replay shortcut allowlist, so a replayed step can never press it.

The listener only exists for the duration of one run and observes only whether
the hotkey combination was pressed; it never records or stores keystrokes.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Protocol

#: pynput GlobalHotKeys notation for the stop combination.
KILL_SWITCH_HOTKEY = "<ctrl>+<alt>+q"
#: How the combination is shown to people.
KILL_SWITCH_LABEL = "Ctrl+Alt+Q"


class KillSwitch(Protocol):
    """Run-scoped stop signal; the controller starts and stops it per run."""

    @property
    def triggered(self) -> bool: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...


def _default_listener_factory(hotkeys: dict[str, Callable[[], None]]) -> Any:
    from pynput import keyboard

    return keyboard.GlobalHotKeys(hotkeys)


class HotkeyKillSwitch:
    """Kill switch backed by a pynput global hotkey listener (injectable)."""

    def __init__(
        self,
        listener_factory: Callable[[dict[str, Callable[[], None]]], Any] | None = None,
    ) -> None:
        self._listener_factory = listener_factory or _default_listener_factory
        self._triggered = threading.Event()
        self._listener: Any = None

    @property
    def triggered(self) -> bool:
        """True once the hotkey was pressed during the current run."""
        return self._triggered.is_set()

    def trigger(self) -> None:
        """Mark the current run as stopped (called by the hotkey listener)."""
        self._triggered.set()

    def start(self) -> None:
        """Reset the flag and begin listening for the hotkey."""
        self.stop()
        self._triggered.clear()
        listener = self._listener_factory({KILL_SWITCH_HOTKEY: self.trigger})
        listener.start()
        self._listener = listener

    def stop(self) -> None:
        """Stop listening; the triggered flag stays readable until next start."""
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.stop()
