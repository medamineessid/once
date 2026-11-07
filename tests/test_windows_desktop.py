"""Tests for the real Windows desktop provider using a fake pywinauto surface."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from pathlib import Path

import pytest

from engine.workflow import StepStatus
from integrations.windows_desktop import (
    PywinautoDesktopActions,
)

APP_TARGET = json.dumps({"executable": str(sys.executable)})


class FakePointers:
    """Emulates the pattern pointers pywinauto exposes."""

    def __init__(self, value: str | None = "before") -> None:
        self._value = value

    def SetValue(self, text: str) -> None:
        self._value = text

    @property
    def Value(self) -> str:
        return self._value

    def Invoke(self) -> None:
        self.invoked = True

    def Toggle(self) -> None:
        self.toggled = True


class FakeElementInfo:
    def __init__(
        self,
        name="",
        class_name="",
        automation_id="",
        control_type="",
        process_id=1,
        is_password=False,
    ) -> None:
        self.name = name
        self.class_name = class_name
        self.automation_id = automation_id
        self.control_type = control_type
        self.process_id = process_id
        self.is_password = is_password


class FakeWrapper:
    def __init__(
        self,
        info: FakeElementInfo,
        *,
        enabled=True,
        value: str | None = "before",
        has_invoke=True,
        has_toggle=False,
    ) -> None:
        self.element_info = info
        self._enabled = enabled
        self.iface_value = FakePointers(value) if (value is not None) else None
        self.iface_invoke = FakePointers() if has_invoke else None
        self.iface_toggle = FakePointers() if has_toggle else None
        self.focused_keys: list[str] = []
        self.selected = False

    def is_enabled(self) -> bool:
        return self._enabled

    def is_visible(self) -> bool:
        return True

    def set_focus(self) -> None:
        self.focused_keys.append("focus")

    def type_keys(self, code: str) -> None:
        self.focused_keys.append(code)

    def is_selected(self) -> bool:
        return self.selected

    def select(self) -> None:
        self.selected = True

    def descendants(self) -> tuple[FakeWrapper, ...]:
        return ()


class FakeWindow(FakeWrapper):
    def __init__(self, info: FakeElementInfo, children: list[FakeWrapper], **kw) -> None:
        super().__init__(info, **kw)
        self._children = children
        self.closed = False

    def close(self) -> None:
        """Mirror pywinauto's close: marks the window closed for the fake surface."""
        self.closed = True

    def descendants(self) -> tuple[FakeWrapper, ...]:
        return tuple(self._children)


class FakeDesktop:
    def __init__(self, windows: list[FakeWrapper]) -> None:
        self._windows = windows

    def windows(self) -> list[FakeWrapper]:
        return [wrapper for wrapper in self._windows if not getattr(wrapper, "closed", False)]


def shortcut_payload(**overrides) -> str:
    full = {"window": {**WINDOW_IDENTITY, **overrides}, "keys": "ctrl+s"}
    return json.dumps(full)


WINDOW_IDENTITY = {"title": "once-demo.txt - Editor", "class_name": "DemoEditor"}
TEXT_ELEMENT = {"class_name": "DemoEditClass", "control_type": "Document"}
BUTTON_ELEMENT = {"automation_id": "okButton", "control_type": "Button"}


def provider_with(children, *, windows=None, sleep=lambda _s: None, clock=lambda: 0.0):
    """Build a provider bound to one fake desktop with fixed time."""
    if windows is None:
        windows = [
            FakeWindow(
                FakeElementInfo(
                    name=WINDOW_IDENTITY["title"],
                    class_name="DemoEditor",
                    control_type="Window",
                    process_id=99,
                ),
                children,
            )
        ]
    desktop = FakeDesktop(windows)
    provider = approved_provider(
        desktop_factory=lambda: desktop,
        popen=lambda argv: FakeProcess(),
        sleep=sleep,
        clock=clock,
    )
    return provider


class FakeProcess:
    pid = 4242


def window_step(**overrides) -> str:
    identity = {**WINDOW_IDENTITY, **overrides}
    return json.dumps(identity)


def element_step(**overrides) -> str:
    payload = {"window": {**WINDOW_IDENTITY, **overrides}, "element": {**TEXT_ELEMENT}}
    return json.dumps(payload)


def test_type_text_sets_value_and_confirms_readback() -> None:
    editor = FakeWrapper(
        FakeElementInfo(class_name="DemoEditClass", control_type="Document"), enabled=True
    )
    provider = provider_with([editor])
    result = provider.type_text(
        json.dumps({**{"window": WINDOW_IDENTITY, "element": TEXT_ELEMENT}, "text": "hello once"})
    )
    assert result.status is StepStatus.SUCCEEDED
    assert "readback_confirmed=true" in result.evidence


def test_type_text_refuses_disabled_elements() -> None:
    editor = FakeWrapper(
        FakeElementInfo(class_name="DemoEditClass", control_type="Document"), enabled=False
    )
    provider = provider_with([editor])
    with pytest.raises(Exception, match="disabled"):
        provider.type_text(
            json.dumps({**{"window": WINDOW_IDENTITY, "element": TEXT_ELEMENT}, "text": "hi"})
        )


def test_type_text_refuses_non_text_controls() -> None:
    button = FakeWrapper(FakeElementInfo(control_type="Button", automation_id="ok"))
    provider = provider_with([button])
    with pytest.raises(Exception, match="not a text input"):
        provider.type_text(
            json.dumps(
                {
                    "window": WINDOW_IDENTITY,
                    "element": {"automation_id": "ok", "control_type": "Button"},
                    "text": "hi",
                }
            )
        )


def test_type_text_refuses_password_controls_without_logging_text() -> None:
    secret = FakeWrapper(
        FakeElementInfo(class_name="DemoEditClass", control_type="Edit", is_password=True)
    )
    provider = provider_with([secret])
    with pytest.raises(Exception, match="password"):
        provider.type_text(
            json.dumps(
                {
                    "window": WINDOW_IDENTITY,
                    "element": {"class_name": "DemoEditClass", "control_type": "Edit"},
                    "text": "secret-password",
                }
            )
        )


def test_ambiguous_elements_are_refused_without_guessing() -> None:
    first = FakeWrapper(FakeElementInfo(class_name="DemoEditClass", control_type="Document"))
    second = FakeWrapper(FakeElementInfo(class_name="DemoEditClass", control_type="Document"))
    provider = provider_with([first, second])
    with pytest.raises(Exception, match="ambiguous"):
        provider.type_text(
            json.dumps(
                {
                    "window": WINDOW_IDENTITY,
                    "element": TEXT_ELEMENT,
                    "text": "hi",
                }
            )
        )


def test_missing_element_fails_closed() -> None:
    provider = provider_with([])
    with pytest.raises(Exception, match="was not found"):
        provider.type_text(
            json.dumps(
                {
                    "window": WINDOW_IDENTITY,
                    "element": TEXT_ELEMENT,
                    "text": "hi",
                }
            )
        )


def test_ambiguous_windows_are_refused(tmp_path: Path) -> None:
    window_one = FakeWindow(
        FakeElementInfo(name=WINDOW_IDENTITY["title"], class_name="DemoEditor"), []
    )
    window_two = FakeWindow(
        FakeElementInfo(name=WINDOW_IDENTITY["title"], class_name="DemoEditor"), []
    )
    provider = provider_with([], windows=[window_one, window_two])
    with pytest.raises(Exception, match="ambiguous"):
        provider.press_shortcut(shortcut_payload())


def test_click_invoke_performs_and_records_pattern() -> None:
    button = FakeWrapper(FakeElementInfo(control_type="Button", automation_id="okButton"))
    provider = provider_with([button])
    result = provider.click_element(
        json.dumps(
            {
                "window": WINDOW_IDENTITY,
                "element": BUTTON_ELEMENT,
            }
        )
    )
    assert result.status is StepStatus.SUCCEEDED
    assert "interaction=invoke" in result.evidence
    assert button.iface_invoke.invoked is True


def test_click_refuses_controls_without_pattern_support() -> None:
    text = FakeWrapper(
        FakeElementInfo(class_name="DemoEditClass", control_type="Document"),
        has_invoke=False,
    )
    provider = provider_with([text])
    with pytest.raises(Exception, match="does not support invoke"):
        provider.click_element(
            json.dumps(
                {
                    "window": WINDOW_IDENTITY,
                    "element": TEXT_ELEMENT,
                }
            )
        )


def test_click_toggle_refused_on_a_button() -> None:
    button = FakeWrapper(FakeElementInfo(control_type="Button", automation_id="okButton"))
    provider = provider_with([button])
    with pytest.raises(Exception, match="cannot be toggled"):
        provider.click_element(
            json.dumps(
                {
                    "window": WINDOW_IDENTITY,
                    "element": BUTTON_ELEMENT,
                    "interaction": "toggle",
                }
            )
        )


def test_click_toggle_supported_on_checkbox() -> None:
    checkbox = FakeWrapper(
        FakeElementInfo(control_type="CheckBox", automation_id="agree"),
        has_toggle=True,
    )
    provider = provider_with([checkbox])
    result = provider.click_element(
        json.dumps(
            {
                "window": WINDOW_IDENTITY,
                "element": {"automation_id": "agree", "control_type": "CheckBox"},
                "interaction": "toggle",
            }
        )
    )
    assert result.status is StepStatus.SUCCEEDED
    assert checkbox.iface_toggle.toggled is True


def test_shortcut_is_delivered_to_the_identified_window_only() -> None:
    window = FakeWindow(FakeElementInfo(name=WINDOW_IDENTITY["title"], class_name="DemoEditor"), [])
    provider = provider_with([], windows=[window])
    result = provider.press_shortcut(shortcut_payload())
    assert result.status is StepStatus.SUCCEEDED
    assert "untargeted_injection=false" in result.evidence
    assert window.focused_keys == ["focus", "^s"]


def test_shortcut_rejects_unlisted_combinations() -> None:
    provider = provider_with([])
    with pytest.raises(Exception, match="not allow-listed"):
        provider.press_shortcut(json.dumps({**WINDOW_IDENTITY, "keys": "ctrl+q"}))


def test_wait_window_succeeds_when_one_matches() -> None:
    window = FakeWindow(FakeElementInfo(name=WINDOW_IDENTITY["title"], class_name="DemoEditor"), [])
    provider = provider_with([], windows=[window])
    result = provider.wait_window(window_step(), 2.0)
    assert result.status is StepStatus.SUCCEEDED


def test_wait_window_times_out_with_bounded_polling() -> None:
    sleeps: list[float] = []

    class Clock:
        value = 0.0

        def __call__(self) -> float:
            return self.value

    clock = Clock()

    def sleep(duration: float) -> None:
        sleeps.append(duration)
        clock.value += duration

    provider = provider_with([], windows=[], sleep=sleep, clock=clock)
    result = provider.wait_window(window_step(), 1.0)
    assert result.status is StepStatus.FAILED
    assert "did not appear within 1.0 seconds" in result.message
    assert sleeps  # busy-wait refusal: it backed off between polls


def test_launch_records_the_resolved_command_and_process(tmp_path: Path) -> None:
    """The launch path validates existence, passes an argv list, and records evidence."""
    launched: list[list[str]] = []

    def fake_popen(argv: list[str]):
        launched.append(argv)
        return FakeProcess()

    provider = approved_provider(
        desktop_factory=lambda: FakeDesktop([]),
        popen=fake_popen,
    )
    result = provider.launch_application(
        json.dumps({"executable": str(sys.executable), "arguments": ["--version"]})
    )
    assert result.status is StepStatus.SUCCEEDED
    assert "process_id=4242" in result.evidence
    assert launched == [[sys.executable, "--version"]]


def test_launch_fails_closed_for_a_missing_executable(tmp_path: Path) -> None:
    """An executable path that does not exist produces a structured failure."""
    launched: list[list[str]] = []

    def must_not_launch(argv: list[str]):
        launched.append(argv)
        raise AssertionError("Popen must not be called for a missing executable")

    provider = approved_provider(
        desktop_factory=lambda: FakeDesktop([]),
        popen=must_not_launch,
    )
    result = provider.launch_application(json.dumps({"executable": str(tmp_path / "gone.exe")}))
    assert result.status is StepStatus.FAILED
    assert "missing" in result.message
    assert launched == []


def test_default_launch_never_uses_a_shell(monkeypatch) -> None:
    """The built-in launcher passes shell=False with an exact argv list."""
    import subprocess

    real_popen = subprocess.Popen
    observed: dict[str, object] = {}

    def recording_popen(argv, **kwargs):
        observed["argv"] = argv
        observed["shell"] = kwargs.get("shell")
        return real_popen(argv, shell=False, stdout=subprocess.DEVNULL)

    monkeypatch.setattr("integrations.windows_desktop.subprocess.Popen", recording_popen)
    argv = [sys.executable, "--version"]
    process = PywinautoDesktopActions._default_popen(argv)
    assert observed["shell"] is False
    assert observed["argv"] == argv
    process.wait(timeout=10)


def close_provider(windows, *, clock=lambda: 0.0, alive=True) -> PywinautoDesktopActions:
    """Provider bound to one fake desktop surface with launch and close access."""
    desktop = FakeDesktop(windows)
    return approved_provider(
        desktop_factory=lambda: desktop,
        popen=lambda argv: FakeProcess(),
        sleep=lambda _s: None,
        clock=clock,
        is_visible=lambda wrapper: getattr(wrapper.element_info, "visible", True),
        has_owner=lambda wrapper: getattr(wrapper.element_info, "owner", False),
        process_alive=lambda _pid: alive,
    )


def test_close_refuses_when_this_run_launched_nothing() -> None:
    provider = close_provider([])
    result = provider.close_application(APP_TARGET)
    assert result.status is StepStatus.FAILED
    assert "did not launch" in result.message
    assert "registered=false" in result.evidence


def test_close_only_touches_windows_of_the_launched_process() -> None:
    own = FakeWindow(FakeElementInfo(name="Visual Studio Code", process_id=FakeProcess.pid), [])
    foreign = FakeWindow(FakeElementInfo(name="Unrelated windows", process_id=99), [])
    provider = close_provider([own, foreign])
    launched = provider.launch_application(APP_TARGET)
    assert launched.status is StepStatus.SUCCEEDED

    result = provider.close_application(APP_TARGET)
    assert result.status is StepStatus.SUCCEEDED
    assert own.closed is True
    assert foreign.closed is False
    assert "process_id=4242" in result.evidence
    assert "windows_closed=1" in result.evidence


def test_close_fails_when_a_window_refuses_to_disappear() -> None:
    class StickyWindow(FakeWindow):
        def close(self) -> None:
            return None

    sticky = StickyWindow(FakeElementInfo(name="Stuck", process_id=FakeProcess.pid), [])
    ticks = iter(range(1, 100))

    def clock() -> float:
        return float(next(ticks))

    provider = close_provider([sticky], clock=clock)
    provider.launch_application(APP_TARGET)

    result = provider.close_application(APP_TARGET)
    assert result.status is StepStatus.FAILED
    assert "did not close" in result.message


def test_close_fails_closed_when_the_window_close_errors() -> None:
    class BrokenWindow(FakeWindow):
        def close(self) -> None:
            raise RuntimeError("the surface refused")

    broken = BrokenWindow(FakeElementInfo(name="Broken", process_id=FakeProcess.pid), [])
    provider = close_provider([broken])
    provider.launch_application(APP_TARGET)

    result = provider.close_application(APP_TARGET)
    assert result.status is StepStatus.FAILED
    assert "the surface refused" in result.message


def test_close_summary_reports_only_what_was_measured() -> None:
    """The adapter holds no application names or install locations at all."""
    import integrations.windows_desktop as adapter

    source = pathlib.Path(adapter.__file__).read_text(encoding="utf-8").lower()
    for name in ("chrome.exe", "notepad.exe", "code.exe", "charmap"):
        assert name not in source


class FakeApprovals:
    """One approved-application record, standing in for the storage registry."""

    def __init__(
        self,
        *,
        approved: bool = True,
        close_supported: bool = True,
        sha256: str | None = None,
        display_name: str = "Harmless app",
    ) -> None:
        self.approved = approved
        self.close_supported = close_supported
        self.sha256 = sha256
        self.display_name = display_name

    def find(self, executable):
        from engine.workflow import ApprovedApplication

        return ApprovedApplication(
            executable=executable,
            sha256=self.sha256 or hashlib.sha256(executable.read_bytes()).hexdigest(),
            display_name=self.display_name,
            approved=self.approved,
            close_supported=self.close_supported,
        )


def approved_provider(**kwargs):
    """A desktop provider whose approval source is the fake registry above."""
    kwargs.setdefault("approvals", FakeApprovals())
    return PywinautoDesktopActions(**kwargs)
