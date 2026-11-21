"""Tests for the global replay kill switch."""

from __future__ import annotations

from integrations.kill_switch import (
    KILL_SWITCH_HOTKEY,
    KILL_SWITCH_LABEL,
    HotkeyKillSwitch,
    canonical_key,
    is_stop_combo,
)


class FakeListener:
    """Stands in for a pynput listener: keeps the callbacks it was given."""

    def __init__(self, on_press, on_release) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class FakeKey:
    """One key event, shaped like a pynput Key or KeyCode."""

    def __init__(self, name: str | None = None, char: str | None = None, vk=None) -> None:
        if name is not None:
            self.name = name
        self.char = char
        self.vk = vk


def test_kill_switch_labels_and_constants() -> None:
    assert KILL_SWITCH_LABEL == "Ctrl+Alt+Q"
    assert KILL_SWITCH_HOTKEY == "<ctrl>+<alt>+q"


def test_canonical_key_maps_modifiers_and_the_stop_key() -> None:
    assert canonical_key(FakeKey(name="ctrl_l")) == "ctrl"
    assert canonical_key(FakeKey(name="alt_r")) == "alt"
    assert canonical_key(FakeKey(char="q")) == "q"
    # Layouts where the key produces no character still report its virtual key.
    assert canonical_key(FakeKey(char=None, vk=0x51)) == "q"
    assert canonical_key(FakeKey(char="a")) is None
    assert canonical_key(FakeKey(name="shift")) is None


def test_stop_combo_needs_ctrl_alt_and_q() -> None:
    assert is_stop_combo({"ctrl", "alt", "q"}) is True
    assert is_stop_combo({"ctrl", "alt", "q", "shift"}) is True
    assert is_stop_combo({"ctrl", "q"}) is False
    assert is_stop_combo({"alt", "q"}) is False
    assert is_stop_combo({"ctrl", "alt", "a"}) is False
    assert is_stop_combo(set()) is False


def test_kill_switch_lifecycle_and_trigger() -> None:
    fake_listener: FakeListener | None = None

    def factory(on_press, on_release):
        nonlocal fake_listener
        fake_listener = FakeListener(on_press, on_release)
        return fake_listener

    kill_switch = HotkeyKillSwitch(listener_factory=factory)
    assert not kill_switch.triggered

    kill_switch.start()
    assert fake_listener is not None
    assert fake_listener.started

    # A partial combination must not stop the run.
    fake_listener.on_press(FakeKey(name="ctrl_l"))
    fake_listener.on_press(FakeKey(char="q"))
    assert not kill_switch.triggered

    fake_listener.on_press(FakeKey(name="alt_l"))
    fake_listener.on_press(FakeKey(char="q"))
    assert kill_switch.triggered

    kill_switch.stop()
    assert fake_listener.stopped

    # Re-starting clears triggered state and the held keys.
    kill_switch.start()
    assert not kill_switch.triggered
    kill_switch.stop()


def test_released_keys_stop_counting_towards_the_combo() -> None:
    holder: dict[str, FakeListener] = {}

    def factory(on_press, on_release):
        holder["listener"] = FakeListener(on_press, on_release)
        return holder["listener"]

    kill_switch = HotkeyKillSwitch(listener_factory=factory)
    kill_switch.start()
    listener = holder["listener"]

    listener.on_press(FakeKey(name="ctrl_l"))
    listener.on_release(FakeKey(name="ctrl_l"))
    listener.on_press(FakeKey(name="alt_l"))
    listener.on_press(FakeKey(char="q"))
    assert not kill_switch.triggered

    # Pressing the modifier again with alt and q down fires once.
    listener.on_press(FakeKey(name="ctrl_r"))
    assert kill_switch.triggered
    kill_switch.stop()


def test_a_failing_listener_does_not_leave_the_switch_armed() -> None:
    class BrokenListener(FakeListener):
        def start(self) -> None:
            raise OSError("could not install the keyboard hook")

    kill_switch = HotkeyKillSwitch(
        listener_factory=lambda on_press, on_release: BrokenListener(on_press, on_release)
    )
    try:
        kill_switch.start()
    except OSError:
        pass
    else:  # pragma: no cover - the switch must surface the real failure
        raise AssertionError("a listener that cannot start must raise")
    assert kill_switch.triggered is False
    assert kill_switch._listener is None
