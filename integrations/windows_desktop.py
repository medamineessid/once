"""The Windows desktop interaction provider behind the approved workflow engine.

Every action is identity-based, bounded, and fail-closed: a target that cannot
be uniquely resolved, a control that cannot support the requested interaction,
or a launch that cannot be validated produces a structured failure result. The
provider never shells out, never injects keyboard input into untargeted
windows, and never waits or retries without the step's timeout.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from engine.errors import ExecutionError
from engine.workflow import StepResult, StepStatus
from integrations.uia_targeting import element_matches, window_matches

SHORTCUT_CODES: dict[str, str] = {
    "ctrl+s": "^s",
    "ctrl+a": "^a",
    "ctrl+c": "^c",
    "ctrl+v": "^v",
    "ctrl+x": "^x",
    "ctrl+z": "^z",
    "ctrl+y": "^y",
    "enter": "{ENTER}",
    "escape": "{ESC}",
    "tab": "{TAB}",
}

POLL_INTERVAL_SECONDS = 0.25
MAX_ARGUMENTS = 16


class WindowsApplicationRegistry:
    """Controlled expansion of allow-listed application names to executables."""

    def resolve(self, name: str) -> Path:
        """Return the executable path for one registered application name."""
        lowered = name.strip().lower()
        if lowered == "notepad":
            root = Path(__import__("os").environ.get("SystemRoot", r"C:\Windows"))
            return root / "System32" / "notepad.exe"
        raise ExecutionError(
            f"The application registry does not contain {name}. Use an "
            "allow-listed application name or an explicitly approved absolute "
            "executable path."
        )


def _load_parsed(target_json: str, what: str) -> dict:
    try:
        parsed = json.loads(target_json)
    except json.JSONDecodeError as error:
        raise ExecutionError(f"The {what} target is not valid JSON.") from error
    if not isinstance(parsed, dict):
        raise ExecutionError(f"The {what} target must be a JSON object.")
    return parsed


class PywinautoDesktopActions:
    """Real Windows actions via pywinauto UI Automation (pattern based)."""

    def __init__(
        self,
        desktop_factory: Callable[[], Any] | None = None,
        registry: WindowsApplicationRegistry | None = None,
        popen: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        poll_interval: float = POLL_INTERVAL_SECONDS,
    ) -> None:
        self._desktop_factory = desktop_factory or self._default_desktop
        self._registry = registry or WindowsApplicationRegistry()
        self._popen = popen or self._default_popen
        self._sleep = sleep
        self._clock = clock
        self._poll_interval = poll_interval

    # ------------------------------------------------------------ dispatch

    @staticmethod
    def _default_desktop() -> Any:
        from pywinauto import Desktop

        return Desktop(backend="uia")

    @staticmethod
    def _default_popen(argv: list[str]) -> subprocess.Popen:
        return subprocess.Popen(  # noqa: S603 - exact argv list, shell disabled
            argv,
            shell=False,
            cwd=None,
        )

    # -------------------------------------------------------------- launch

    def launch_application(self, target_json: str) -> StepResult:
        """Start one approved application; never uses a shell."""
        target = _load_parsed(target_json, "launch")
        arguments = target.get("arguments", [])
        if isinstance(target.get("application"), str):
            executable = self._registry.resolve(target["application"])
        else:
            executable = Path(str(target["executable"]))
        if not executable.is_file():
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=(
                    f"The application could not be launched because its executable "
                    f"is missing at {executable}."
                ),
                evidence=("missing=true", f"executable={executable}"),
            )
        argv = [str(executable), *arguments]
        try:
            process = self._popen(argv)
        except OSError as error:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The application could not be launched: {error}",
                evidence=(f"executable={executable}",),
            )
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message="The application was launched.",
            evidence=(
                f"executable={executable}",
                f"process_id={process.pid}",
                f"argument_count={len(argv) - 1}",
            ),
        )

    # ---------------------------------------------------------------- wait

    def wait_window(self, target_json: str, timeout_seconds: float) -> StepResult:
        """Poll for exactly one matching top-level window within the step timeout."""
        identity = _load_parsed(target_json, "window")
        deadline = self._clock() + timeout_seconds
        last_count = 0
        while True:
            matches = [
                wrapper
                for wrapper in self._desktop_factory().windows()
                if window_matches(wrapper, identity)
            ]
            last_count = len(matches)
            if last_count == 1:
                wrapper = matches[0]
                info = wrapper.element_info
                return StepResult(
                    step_id="",
                    status=StepStatus.SUCCEEDED,
                    message="The identified window appeared.",
                    evidence=(
                        f"title={getattr(info, 'name', None)}",
                        f"process_id={getattr(info, 'process_id', None)}",
                        f"class_name={getattr(info, 'class_name', None) or 'unknown'}",
                    ),
                )
            if last_count > 1:
                return StepResult(
                    step_id="",
                    status=StepStatus.FAILED,
                    message=(
                        "More than one window matches the identity, so the wait "
                        "was refused instead of choosing one arbitrarily."
                    ),
                    evidence=(f"matches={last_count}",),
                )
            if self._clock() >= deadline:
                return StepResult(
                    step_id="",
                    status=StepStatus.FAILED,
                    message=(
                        f"The identified window did not appear within {timeout_seconds} seconds."
                    ),
                    evidence=("matches=0",),
                )
            self._sleep(self._poll_interval)

    # ------------------------------------------------- shared element lookup

    def _resolve_element(self, target_json: str, what: str) -> Any:
        """Return the unique element wrapper or raise a structured failure."""
        target = _load_parsed(target_json, what)
        windows = self._desktop_factory().windows()
        window_matches_list = [w for w in windows if window_matches(w, target.get("window"))]
        if not window_matches_list:
            raise ExecutionError("The identified window was not found, so nothing was done.")
        if len(window_matches_list) > 1:
            raise ExecutionError("The identified window is ambiguous, so nothing was done.")
        parent = window_matches_list[0]
        candidates = [w for w in parent.descendants() if element_matches(w, target.get("element"))]
        if not candidates:
            raise ExecutionError(
                f"The identified {what} element was not found, so nothing was done."
            )
        if len(candidates) > 1:
            raise ExecutionError(
                f"The identified {what} element is ambiguous, so nothing was done."
            )
        element = candidates[0]
        try:
            enabled = bool(element.is_enabled())
        except (OSError, RuntimeError) as error:
            raise ExecutionError(
                f"The {what} element state could not be inspected, so nothing was done."
            ) from error
        if not enabled:
            raise ExecutionError(f"The {what} element is disabled, so the action was refused.")
        return element

    @staticmethod
    def _pattern(wrapper: Any, name: str) -> Any:
        """Return the UI Automation pattern interface or fail closed."""
        from pywinauto.uia_defines import (
            NoPatternInterfaceError,
        )  # local: keeps import Windows-safe

        attribute = f"iface_{name}"
        try:
            pattern = getattr(wrapper, attribute)
        except NoPatternInterfaceError as error:
            raise ExecutionError(
                f"The element does not support the {name} pattern needed for "
                "this action, so the action was refused."
            ) from error
        if pattern is None:
            raise ExecutionError(
                f"The element does not support the {name} pattern needed for "
                "this action, so the action was refused."
            )
        return pattern

    # ---------------------------------------------------------------- click

    _CLICKABLE_CONTROL_TYPES = frozenset(
        {"Button", "MenuItem", "CheckBox", "RadioButton"}
    )

    def click_element(self, target_json: str) -> StepResult:
        """Invoke/toggle/select one unique, enabled element by its UIA pattern."""
        target = _load_parsed(target_json, "click")
        interaction = target.get("interaction", "invoke")
        element = self._resolve_element(target_json, "click")
        element_type = getattr(element.element_info, "control_type", None)
        self._guard_clickable(element, interaction, element_type)
        try:
            if interaction == "invoke":
                self._pattern(element, "invoke").Invoke()
            elif interaction == "toggle":
                self._pattern(element, "toggle").Toggle()
            else:
                element.select()
        except (AttributeError, OSError, RuntimeError, ValueError) as error:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The element interaction failed: {error}",
                evidence=(f"interaction={interaction}",),
            )
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message=f"The element interaction was performed ({interaction}).",
            evidence=(
                f"interaction={interaction}",
                f"control_type={element_type}",
                "target_verified=true",
            ),
        )

    def _guard_clickable(self, element: Any, interaction: str, control_type: Any) -> None:
        """Refuse interactions the identified control cannot support."""
        if interaction == "toggle" and control_type not in ("CheckBox", "RadioButton"):
            raise ExecutionError(
                f"A {control_type or 'window'} control cannot be toggled, so the "
                "action was refused rather than sending another input."
            )
        if interaction == "invoke" and control_type not in self._CLICKABLE_CONTROL_TYPES:
            raise ExecutionError(
                f"A {control_type or 'window'} control does not support invoke; the "
                "action was refused instead of clicking a different element."
            )
        if interaction == "select":
            selector = getattr(element, "is_selected", None)
            if not callable(selector):
                raise ExecutionError(
                    "The element does not support selection, so the action was refused."
                )

    @staticmethod
    def _readback(pattern: Any) -> Any:
        """Read a Value-pattern control back through either API attribute name."""
        if hasattr(pattern, "CurrentValue"):
            return pattern.CurrentValue
        return pattern.Value

    # ------------------------------------------------------------ type text

    def type_text(self, target_json: str) -> StepResult:
        """Set text on one unique, enabled, editable value-pattern control."""
        target = _load_parsed(target_json, "text entry")
        text = str(target.get("text", ""))
        element = self._resolve_element(target_json, "text entry")
        control_type = getattr(element.element_info, "control_type", None)
        if control_type not in ("Edit", "Document"):
            raise ExecutionError(
                f"A {control_type or 'window'} control is not a text input, so the "
                "text was not entered."
            )
        info = element.element_info
        if bool(getattr(info, "is_password", False)):
            raise ExecutionError(
                "The target control is a password field, so entering text was refused for secrecy."
            )
        value_pattern = self._pattern(element, "value")
        try:
            value_pattern.SetValue(text)
            read_back = self._readback(value_pattern)
        except (AttributeError, OSError, RuntimeError, ValueError) as error:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The text could not be entered: {error}",
                evidence=("chars=" + str(len(text)),),
            )
        if read_back != text:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=(
                    "The control did not retain the entered text, so the action "
                    "failed instead of trusting the setting."
                ),
                evidence=("chars=" + str(len(text)), "readback_confirmed=false"),
            )
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message="The text was entered and confirmed by reading the control.",
            evidence=("chars=" + str(len(text)), "readback_confirmed=true"),
        )

    # ------------------------------------------------------------- shortcut

    def press_shortcut(self, target_json: str) -> StepResult:
        """Send one allow-listed shortcut to exactly the identified window."""
        target = _load_parsed(target_json, "shortcut")
        keys = str(target.get("keys", "")).strip().lower()
        code = SHORTCUT_CODES.get(keys)
        if code is None:
            raise ExecutionError(f"The requested shortcut {keys or '(empty)'} is not allow-listed.")
        windows = self._desktop_factory().windows()
        matches = [w for w in windows if window_matches(w, target.get("window"))]
        if not matches:
            raise ExecutionError("The identified window was not found, so no keys were sent.")
        if len(matches) > 1:
            raise ExecutionError("The identified window is ambiguous, so no keys were sent.")
        window = matches[0]
        try:
            window.set_focus()
            window.type_keys(code)
        except (AttributeError, OSError, RuntimeError, ValueError) as error:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The shortcut could not be delivered: {error}",
                evidence=(f"keys={keys}",),
            )
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message="The shortcut was sent to the identified window only.",
            evidence=(f"keys={keys}", "untargeted_injection=false"),
        )
