"""Global kill switch that stops a running desktop replay from the keyboard.

While an approved desktop replay runs, Once may be clicking and typing in other
applications, so its own window is often hidden. The kill switch listens for one
global hotkey and, when pressed, marks the run cancelled; the engine checks the
flag before every step, so no further step starts. The hotkey is deliberately
absent from the replay shortcut allowlist, so a replayed step can never press it.

The listener only exists for the duration of one run and observes only whether
the hotkey combination was pressed; it never records or stores keystrokes.

The combination is matched here, key by key, instead of through pynput's
``GlobalHotKeys`` string parser. That parser only recognises keys it can name as
characters, so on a layout where the key produces no character (and for keys
injected by automation) it silently never fired; a matcher that also accepts the
virtual key is deterministic and testable without a physical keyboard.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Protocol

#: pynput notation for the stop combination, kept for display and diagnostics.
KILL_SWITCH_HOTKEY = "<ctrl>+<alt>+q"
#: How the combination is shown to people.
KILL_SWITCH_LABEL = "Ctrl+Alt+Q"
#: The non-modifier key of the combination.
STOP_KEY = "q"
#: Virtual-key code of the Q key, used when no character is reported.
STOP_KEY_VK = 0x51

_CTRL_KEY_NAMES = frozenset({"ctrl", "ctrl_l", "ctrl_r"})
_ALT_KEY_NAMES = frozenset({"alt", "alt_l", "alt_r"})


class KillSwitch(Protocol):
    """Run-scoped stop signal; the controller starts and stops it per run."""

    @property
    def triggered(self) -> bool: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...


def canonical_key(key: object) -> str | None:
    """Map one key event to ``ctrl``, ``alt``, ``q``, or None when irrelevant."""
    name = getattr(key, "name", None)
    if isinstance(name, str):
        if name in _CTRL_KEY_NAMES:
            return "ctrl"
        if name in _ALT_KEY_NAMES:
            return "alt"
        return None
    char = getattr(key, "char", None)
    if isinstance(char, str) and char:
        lowered = char.lower()
        return STOP_KEY if lowered == STOP_KEY else None
    if getattr(key, "vk", None) == STOP_KEY_VK:
        return STOP_KEY
    return None


def is_stop_combo(pressed: set[str] | frozenset[str]) -> bool:
    """True when Ctrl, Alt and Q are all held at once."""
    return {"ctrl", "alt", STOP_KEY}.issubset(pressed)


def _default_listener_factory(
    on_press: Callable[[object], None],
    on_release: Callable[[object], None],
) -> Any:
    from pynput import keyboard

    return keyboard.Listener(on_press=on_press, on_release=on_release)


class HotkeyKillSwitch:
    """Kill switch backed by a pynput keyboard listener (injectable)."""

    def __init__(
        self,
        listener_factory: Callable[[Callable[[object], None], Callable[[object], None]], Any]
        | None = None,
    ) -> None:
        self._listener_factory = listener_factory or _default_listener_factory
        self._triggered = threading.Event()
        self._listener: Any = None
        self._pressed: set[str] = set()
        self._lock = threading.Lock()

    @property
    def triggered(self) -> bool:
        """True once the hotkey was pressed during the current run."""
        return self._triggered.is_set()

    def trigger(self) -> None:
        """Mark the current run as stopped (called by the hotkey listener)."""
        self._triggered.set()

    def _press(self, key: object) -> None:
        token = canonical_key(key)
        if token is None:
            return
        with self._lock:
            self._pressed.add(token)
            if is_stop_combo(self._pressed):
                self._triggered.set()

    def _release(self, key: object) -> None:
        token = canonical_key(key)
        if token is None:
            return
        with self._lock:
            self._pressed.discard(token)

    def start(self) -> None:
        """Reset the flag and begin listening for the hotkey."""
        self.stop()
        self._triggered.clear()
        with self._lock:
            self._pressed.clear()
        listener = self._listener_factory(self._press, self._release)
        listener.start()
        self._listener = listener

    def stop(self) -> None:
        """Stop listening; the triggered flag stays readable until next start."""
        listener, self._listener = self._listener, None
        with self._lock:
            self._pressed.clear()
        if listener is not None:
            listener.stop()
