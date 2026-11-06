"""The Windows desktop interaction provider behind the approved workflow engine.

Every action is identity-based, bounded, and fail-closed: a target that cannot
be uniquely resolved, a control that cannot support the requested interaction,
or a launch that cannot be validated produces a structured failure result. The
provider never shells out, never injects keyboard input into untargeted
windows, and never waits or retries without the step's timeout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

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
#: Bound on how long one close step may wait for a window to appear or go.
CLOSE_TIMEOUT_SECONDS = 10.0
MAX_ARGUMENTS = 16

GW_OWNER = 4
STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

#: Applications Once may launch but not close. Measured live on 2026-11-06:
#: Chrome swaps its startup window for the real browser window, and close
#: requests left that window and the process running until the deadline, so a
#: close step could only report a success it cannot prove. Closed only when the
#: measurement proves a browser window actually goes away.
LAUNCH_ONLY_APPLICATIONS = frozenset({"chrome"})

CHROME_EXECUTABLE_NAME = "chrome.exe"
#: Relative location of chrome.exe inside each Windows install root.
CHROME_RELATIVE_EXECUTABLE = Path("Google", "Chrome", "Application", CHROME_EXECUTABLE_NAME)
#: (environment variable, documented default) for Chrome's install roots.
CHROME_INSTALL_ROOTS: tuple[tuple[str, str | None], ...] = (
    ("ProgramFiles", r"C:\Program Files"),
    ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ("LOCALAPPDATA", None),
)
#: Chrome switches Once refuses to take from a step: it always picks its own
#: disposable profile so the launched process is separate and its PID is ours.
CHROME_PROFILE_SWITCHES = frozenset({"--user-data-dir", "--profile-directory"})
CHROME_PROFILE_PREFIX = "once-chrome-profile-"


def chrome_install_candidates() -> tuple[Path, ...]:
    """Standard absolute chrome.exe locations, in resolution order."""
    candidates: list[Path] = []
    for variable, fallback in CHROME_INSTALL_ROOTS:
        root = os.environ.get(variable) or fallback
        if root:
            candidates.append(Path(root) / CHROME_RELATIVE_EXECUTABLE)
    return tuple(candidates)


def _is_chrome(executable: Path) -> bool:
    return executable.name.lower() == CHROME_EXECUTABLE_NAME


def _chrome_profile_argument() -> tuple[str, Path]:
    """A throwaway --user-data-dir, so this launch is a separate Chrome process."""
    profile = Path(tempfile.gettempdir()) / f"{CHROME_PROFILE_PREFIX}{uuid4().hex}"
    return f"--user-data-dir={profile}", profile


def _handle_of(wrapper: Any) -> int:
    """The Win32 handle of a top-level wrapper, or 0 when it has none."""
    handle = getattr(getattr(wrapper, "element_info", None), "handle", None)
    return handle if isinstance(handle, int) else 0


def _windows_api() -> Any:
    if sys.platform != "win32":
        raise ExecutionError("Reading Windows window state is only supported on Windows.")
    import ctypes

    return ctypes.windll.user32


def _default_is_visible(wrapper: Any) -> bool:
    """IsWindowVisible: hidden helper windows never count as the application."""
    handle = _handle_of(wrapper)
    return bool(handle) and bool(_windows_api().IsWindowVisible(handle))


def _default_has_owner(wrapper: Any) -> bool:
    """Owned windows are popups of another window, not top-level application windows."""
    handle = _handle_of(wrapper)
    return bool(handle) and bool(_windows_api().GetWindow(handle, GW_OWNER))


def _default_process_alive(pid: int) -> bool:
    """True while the process exists; a handle-less pid counts as gone."""
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _vscode_candidates() -> tuple[Path, ...]:
    """Known install locations of VS Code, user-scope install first."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    local_root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    return (
        local_root / "Programs" / "Microsoft VS Code" / "Code.exe",
        Path(program_files) / "Microsoft VS Code" / "Code.exe",
    )


class WindowsApplicationRegistry:
    """Controlled expansion of allow-listed application names to executables."""

    def __init__(self, chrome_candidates: tuple[Path, ...] | None = None) -> None:
        self._chrome_candidates = (
            chrome_install_candidates() if chrome_candidates is None else tuple(chrome_candidates)
        )

    def chrome_candidates(self) -> tuple[Path, ...]:
        """The chrome.exe locations this registry will consider, in order."""
        return self._chrome_candidates

    def resolve(self, name: str) -> Path:
        """Return the executable path for one registered application name."""
        lowered = name.strip().lower()
        if lowered == "notepad":
            root = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
            return root / "System32" / "notepad.exe"
        if lowered == "vscode":
            candidates = _vscode_candidates()
            for candidate in candidates:
                if candidate.is_file():
                    return candidate
            return candidates[0]
        if lowered == "chrome":
            for candidate in self._chrome_candidates:
                if candidate.is_file():
                    return candidate
            raise ExecutionError(
                "Chrome was not found in its standard install locations on this "
                "computer, so Once cannot launch it by name. Install Chrome, or "
                "point the step at an absolute chrome.exe path you approve."
            )
        if lowered == "charmap":
            root = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
            return root / "System32" / "charmap.exe"
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
        is_visible: Callable[[Any], bool] | None = None,
        has_owner: Callable[[Any], bool] | None = None,
        process_alive: Callable[[int], bool] | None = None,
    ) -> None:
        self._desktop_factory = desktop_factory or self._default_desktop
        self._registry = registry or WindowsApplicationRegistry()
        self._popen = popen or self._default_popen
        self._sleep = sleep
        self._clock = clock
        self._poll_interval = poll_interval
        self._is_visible = is_visible or _default_is_visible
        self._has_owner = has_owner or _default_has_owner
        self._process_alive = process_alive or _default_process_alive
        #: application name -> pid of exactly the process this run launched.
        self._launched_processes: dict[str, int] = {}

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
        arguments = [str(item) for item in target.get("arguments", [])]
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
        extra_evidence: tuple[str, ...] = ()
        if _is_chrome(executable):
            refused = sorted(
                {
                    switch
                    for switch in CHROME_PROFILE_SWITCHES
                    for argument in arguments
                    if argument.split("=", 1)[0].strip().lower() == switch
                }
            )
            if refused:
                return StepResult(
                    step_id="",
                    status=StepStatus.FAILED,
                    message=(
                        "Once launches Chrome with its own temporary profile, so this "
                        f"step cannot choose one ({', '.join(refused)}). Remove that "
                        "argument and run the step again."
                    ),
                    evidence=(f"refused_argument={refused[0]}", f"executable={executable}"),
                )
            profile_argument, profile = _chrome_profile_argument()
            arguments = [*arguments, profile_argument]
            extra_evidence = ("isolated_profile=true", f"chrome_profile={profile}")
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
        application_name = target.get("application")
        if isinstance(application_name, str) and application_name.strip():
            self._launched_processes[application_name.strip().lower()] = process.pid
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message="The application was launched.",
            evidence=(
                f"executable={executable}",
                f"process_id={process.pid}",
                f"argument_count={len(argv) - 1}",
                *extra_evidence,
            ),
        )

    # ---------------------------------------------------------------- close

    def close_application(self, target_json: str) -> StepResult:
        """Close the application this run launched, by its exact process id.

        Bounded and truthful: the step waits for a visible top-level window of
        the recorded pid to appear before asking anything to close, ignores
        hidden and owned windows, and reports success only when that pid has
        exited or has no visible top-level window left. A window that never
        appears, or ignores the close request, is a failure, never a silent
        success. Without a launch recorded in this run nothing is closed.
        """
        target = _load_parsed(target_json, "close")
        application = target.get("application")
        if not isinstance(application, str) or not application.strip():
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message="The close target needs an allow-listed application name.",
            )
        pid = self._launched_processes.get(application.strip().lower())
        if pid is None:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=(
                    f"This run did not launch {application.strip()}, so it is not "
                    "allowed to close anything on its behalf."
                ),
                evidence=("registered=false",),
            )
        if application.strip().lower() in LAUNCH_ONLY_APPLICATIONS:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=(
                    "Close is not supported for Chrome yet, so Once left it open. "
                    "Quit Chrome yourself when you are finished."
                ),
                evidence=(f"process_id={pid}", "close_supported=false"),
            )
        deadline = self._clock() + CLOSE_TIMEOUT_SECONDS
        closed = 0
        requested: set[int] = set()
        while True:
            if not self._process_alive(pid):
                if closed == 0:
                    return StepResult(
                        step_id="",
                        status=StepStatus.SUCCEEDED,
                        message="The application had already exited.",
                        evidence=(f"process_id={pid}", "exited=true"),
                    )
                return StepResult(
                    step_id="",
                    status=StepStatus.SUCCEEDED,
                    message="The application windows were closed.",
                    evidence=(f"process_id={pid}", f"windows_closed={closed}", "exited=true"),
                )
            visible = self._visible_windows(pid)
            if not visible:
                if closed:
                    return StepResult(
                        step_id="",
                        status=StepStatus.SUCCEEDED,
                        message="The application windows were closed.",
                        evidence=(f"process_id={pid}", f"windows_closed={closed}", "exited=false"),
                    )
                if self._clock() >= deadline:
                    return StepResult(
                        step_id="",
                        status=StepStatus.FAILED,
                        message=(
                            "The application window never appeared within "
                            f"{CLOSE_TIMEOUT_SECONDS:.0f} seconds."
                        ),
                        evidence=(
                            f"process_id={pid}",
                            "windows_closed=0",
                            "window_appeared=false",
                        ),
                    )
                self._sleep(self._poll_interval)
                continue
            if self._clock() >= deadline:
                return StepResult(
                    step_id="",
                    status=StepStatus.FAILED,
                    message=(
                        f"The application did not close within {CLOSE_TIMEOUT_SECONDS:.0f} seconds."
                    ),
                    evidence=(
                        f"process_id={pid}",
                        f"windows_closed={closed}",
                        f"visible_windows_remaining={len(visible)}",
                    ),
                )
            pending = [wrapper for wrapper in visible if _handle_of(wrapper) not in requested]
            if pending:
                wrapper = pending[0]
                requested.add(_handle_of(wrapper))
                try:
                    wrapper.close()
                except (AttributeError, OSError, RuntimeError, ValueError) as error:
                    return StepResult(
                        step_id="",
                        status=StepStatus.FAILED,
                        message=f"The application window did not close: {error}",
                        evidence=(f"process_id={pid}", f"windows_closed={closed}"),
                    )
                closed += 1
            self._sleep(self._poll_interval)

    def _visible_windows(self, pid: int) -> list[Any]:
        """Visible, unowned top-level windows of exactly one process id."""
        found = [
            wrapper
            for wrapper in self._desktop_factory().windows()
            if window_matches(wrapper, {"process_id": pid})
            and self._is_visible(wrapper)
            and not self._has_owner(wrapper)
        ]
        return sorted(found, key=_handle_of)

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

    _CLICKABLE_CONTROL_TYPES = frozenset({"Button", "MenuItem", "CheckBox", "RadioButton"})

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
