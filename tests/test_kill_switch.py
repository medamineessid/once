"""Tests for the global replay kill switch."""

from __future__ import annotations

from integrations.kill_switch import (
    KILL_SWITCH_HOTKEY,
    KILL_SWITCH_LABEL,
    HotkeyKillSwitch,
)


class FakeListener:
    def __init__(self, hotkeys: dict) -> None:
        self.hotkeys = hotkeys
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_kill_switch_labels_and_constants() -> None:
    assert KILL_SWITCH_LABEL == "Ctrl+Alt+Q"
    assert KILL_SWITCH_HOTKEY == "<ctrl>+<alt>+q"


def test_kill_switch_lifecycle_and_trigger() -> None:
    fake_listener: FakeListener | None = None

    def factory(hotkeys):
        nonlocal fake_listener
        fake_listener = FakeListener(hotkeys)
        return fake_listener

    kill_switch = HotkeyKillSwitch(listener_factory=factory)
    assert not kill_switch.triggered

    kill_switch.start()
    assert fake_listener is not None
    assert fake_listener.started
    assert KILL_SWITCH_HOTKEY in fake_listener.hotkeys

    # Trigger via hotkey callback:
    fake_listener.hotkeys[KILL_SWITCH_HOTKEY]()
    assert kill_switch.triggered

    kill_switch.stop()
    assert fake_listener.stopped

    # Re-starting clears triggered state:
    kill_switch.start()
    assert not kill_switch.triggered
    kill_switch.stop()
