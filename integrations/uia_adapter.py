"""UI Automation adapter for smart replay (recorder capture + replay).

Two halves, both testable on any machine that has no interactive desktop:

- **capture**: :func:`descriptor_from_element` turns the metadata a recorder saw
  into independent clues. A password field never produces a descriptor, and a
  descriptor with no identity clue (only a point or an ordinal) is refused
  rather than stored, because it could not be re-resolved safely later.
- **replay**: :class:`UiaTargetAdapter` implements the engine's
  ``StepTargetAdapter`` over an injected :class:`UiaSurface`. It re-resolves the
  element before *every* attempt, tries the UI Automation pattern first, then
  the keyboard, then the centre of the element, and refuses rather than sending
  keys to whatever happens to be focused.

Only :class:`PywinautoSurface` touches pywinauto; every rule above is exercised
against a fake surface in ``tests/test_uia_adapter.py``. Real desktop behaviour
is therefore **not** verified by the automated suite.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from engine.errors import ExecutionError
from engine.resolve import Candidate, Clue, ClueKind, Surface
from engine.workflow import (
    StepDescriptor,
    StepKind,
    StepResult,
    StepStatus,
    WorkflowStep,
)
from integrations.uia_targeting import element_matches
from integrations.windows_desktop import SHORTCUT_CODES

#: Step kinds this adapter can resolve and perform.
UIA_STEP_KINDS: frozenset[StepKind] = frozenset(
    {StepKind.CLICK_UI_ELEMENT, StepKind.TYPE_TEXT, StepKind.PRESS_SHORTCUT}
)
#: Clue kinds that identify an element by what it is, not where it sits.
IDENTITY_CLUE_KINDS: frozenset[ClueKind] = frozenset(
    {
        ClueKind.AUTOMATION_ID,
        ClueKind.ROLE,
        ClueKind.NAME,
        ClueKind.CONTAINER_TEXT,
        ClueKind.PROCESS,
    }
)
#: Bounded wait after a pattern is invoked, before the value is read back.
READBACK_TIMEOUT_SECONDS = 2.0


# ---------------------------------------------------------------- capture


def element_clues(
    info: object,
    *,
    ordinal: int = 0,
    process: str | None = None,
    container: str | None = None,
    group_prefix: str = "element",
) -> tuple[Clue, ...]:
    """Return independent clues for one observed UI Automation element.

    Each clue carries its own group, so copying id, role and name out of one
    node cannot inflate a score: the resolver counts one piece of evidence per
    group.
    """
    clues: list[Clue] = []

    def add(kind: ClueKind, value: object, group: str) -> None:
        text = value.strip() if isinstance(value, str) else ""
        if text:
            clues.append(Clue(kind, text, group))

    add(ClueKind.AUTOMATION_ID, getattr(info, "automation_id", None), f"{group_prefix}.id")
    add(ClueKind.ROLE, getattr(info, "control_type", None), f"{group_prefix}.role")
    add(ClueKind.NAME, getattr(info, "name", None), f"{group_prefix}.name")
    add(ClueKind.CONTAINER_TEXT, container, f"{group_prefix}.container")
    add(ClueKind.PROCESS, process, f"{group_prefix}.process")
    if ordinal:
        clues.append(Clue(ClueKind.ORDINAL, str(ordinal), f"{group_prefix}.ordinal"))
    return tuple(clues)


def descriptor_from_element(
    info: object,
    *,
    ordinal: int = 0,
    position: tuple[int, int] | None = None,
    process: str | None = None,
    container: str | None = None,
) -> StepDescriptor | None:
    """Turn one observed element into a re-resolvable descriptor, or refuse.

    Returns ``None`` for a password field (never recorded) and for an element
    whose only evidence is a position or an ordinal, because neither survives a
    layout change and neither may become a coordinate click.
    """
    if bool(getattr(info, "is_password", False)):
        return None
    clues = element_clues(info, ordinal=ordinal, process=process, container=container)
    if not any(clue.kind in IDENTITY_CLUE_KINDS for clue in clues):
        return None
    return StepDescriptor(surface=Surface.DESKTOP, clues=clues, position_hint=position)


def descriptor_from_event(event: Any) -> StepDescriptor | None:
    """Capture one recorded input event as a re-resolvable descriptor.

    A keystroke with no element metadata (an application-level shortcut) and a
    password field both produce ``None``: neither may become a step whose
    target is guessed from where the mouse happened to be.
    """
    element = getattr(event, "element", None)
    if element is None:
        return None
    x = getattr(event, "x", None)
    y = getattr(event, "y", None)
    position = (x, y) if isinstance(x, int) and isinstance(y, int) else None
    return descriptor_from_element(
        element,
        process=getattr(event, "process_name", None),
        position=position,
    )


# ----------------------------------------------------------------- replaysurface


class UiaSurface(Protocol):
    """The small part of the desktop this adapter is allowed to use.

    Implemented for real by :class:`PywinautoSurface` and for tests by a fake.
    Every method may raise :class:`ExecutionError`; the adapter turns that into
    a readable refusal, never a traceback.
    """

    def window(self) -> Any:
        """Return the single window the step targets."""

    def window_title(self) -> str:
        """Return the visible title of that window."""

    def descendants(self, window: Any) -> Sequence[Any]:
        """Return the window's descendants in a stable order."""

    def info(self, element: Any) -> Any:
        """Return the element metadata (``element_info``)."""

    def enabled(self, element: Any) -> bool:
        """True when the element can be interacted with."""

    def rectangle(self, element: Any) -> tuple[int, int, int, int]:
        """Return ``(left, top, right, bottom)``."""

    def supports_invoke(self, element: Any) -> bool:
        """True when the element exposes Invoke/Select/Toggle."""

    def invoke(self, element: Any) -> None:
        """Perform the element's pattern action."""

    def set_text(self, element: Any, text: str) -> None:
        """Set the element's value through ValuePattern."""

    def read_text(self, element: Any) -> str | None:
        """Read the element's current value, or None when it has none."""

    def focus(self, target: Any) -> None:
        """Move keyboard focus to the target."""

    def send_keys(self, target: Any, keys: str) -> None:
        """Send allow-listed keys to the target."""

    def click_point(self, x: int, y: int) -> None:
        """Click the physical screen point ``(x, y)``."""

    def foreground_handle(self) -> int:
        """Return the handle of the window that currently has focus."""

    def window_handle(self) -> int:
        """Return the handle of the targeted window."""

    def physical_point(self, x: int, y: int) -> tuple[int, int]:
        """Convert a DPI-scaled point to physical pixels before clicking."""


def _rect_centre(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = rect
    return ((left + right) // 2, (top + bottom) // 2)


@dataclass(frozen=True)
class _Attempt:
    """One way to perform the action, in the order the adapter tries them."""

    name: str
    run: Callable[[Any, WorkflowStep], tuple[str, ...]]


class UiaTargetAdapter:
    """Resolve, re-resolve and perform one recorded step on the desktop."""

    def __init__(
        self,
        surface: UiaSurface,
        target_json: str,
        *,
        kinds: frozenset[StepKind] = UIA_STEP_KINDS,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._surface = surface
        self._target_json = target_json
        self._kinds = kinds
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._last_readback: str = ""

    # ------------------------------------------------------------ adapter API

    def handles(self, step: WorkflowStep) -> bool:
        return step.kind in self._kinds

    def candidates(self, step: WorkflowStep) -> tuple[Candidate, ...]:
        """List what the live window currently offers, or nothing when absent."""
        try:
            window = self._surface.window()
            elements = list(self._surface.descendants(window))
        except ExecutionError:
            return ()
        process = self._process_name()
        found: list[Candidate] = []
        for index, element in enumerate(elements):
            info = self._surface.info(element)
            position = self._centre_or_none(element)
            found.append(
                Candidate(
                    candidate_id=f"uia-{index}",
                    clues=element_clues(info, ordinal=index, process=process),
                    ordinal=index,
                    enabled=self._enabled(element),
                    position=position,
                )
            )
        return tuple(found)

    def observe(self, step: WorkflowStep) -> str:
        """The window's visible text, or the last value read back from a control."""
        if self._last_readback:
            return self._last_readback
        try:
            return self._surface.window_title()
        except ExecutionError:
            return ""

    def perform(self, step: WorkflowStep, candidate: Candidate) -> StepResult:
        """Perform the action, trying each method in a fixed, safe order."""
        tried: list[str] = []
        reasons: list[str] = []
        for attempt in self._attempts_for(step):
            try:
                element = self._find(candidate)
            except ExecutionError as error:
                return StepResult(
                    step.step_id,
                    StepStatus.FAILED,
                    f"{error} Nothing was sent.",
                    evidence=tuple(tried),
                )
            try:
                evidence = attempt.run(element, step)
            except ExecutionError as error:
                tried.append(f"{attempt.name}_refused")
                reasons.append(str(error))
                continue
            tried.append(
                f"click_method={attempt.name}" if attempt.name != "text" else "input_method=text"
            )
            return StepResult(
                step.step_id,
                StepStatus.SUCCEEDED,
                self._success_message(attempt.name, step),
                evidence=tuple([*tried, *evidence]),
            )
        last = reasons[-1] if reasons else "no method applies to this element."
        return StepResult(
            step.step_id,
            StepStatus.FAILED,
            f"Once could not carry out {step.name} by any safe method: "
            f"{last} Nothing else was done.",
            evidence=tuple(tried),
        )

    # -------------------------------------------------------------- attempts

    def _attempts_for(self, step: WorkflowStep) -> tuple[_Attempt, ...]:
        if step.kind is StepKind.CLICK_UI_ELEMENT:
            return (
                _Attempt("pattern", self._click_with_pattern),
                _Attempt("keyboard", self._click_with_keyboard),
                _Attempt("mouse_centre", self._click_at_centre),
            )
        if step.kind is StepKind.TYPE_TEXT:
            return (
                _Attempt("text", self._type_with_pattern),
                _Attempt("text", self._type_with_keyboard),
            )
        return (_Attempt("shortcut", self._send_shortcut),)

    def _click_with_pattern(self, element: Any, step: WorkflowStep) -> tuple[str, ...]:
        if not self._surface.supports_invoke(element):
            raise ExecutionError("The control does not support a pattern click.")
        self._surface.invoke(element)
        return ("target_verified=true",)

    def _click_with_keyboard(self, element: Any, step: WorkflowStep) -> tuple[str, ...]:
        self._focus_and_verify(element)
        self._surface.send_keys(element, "{ENTER}")
        return ("target_verified=true", "foreground_verified=true")

    def _click_at_centre(self, element: Any, step: WorkflowStep) -> tuple[str, ...]:
        centre = self._centre_or_none(element)
        if centre is None:
            raise ExecutionError("The element has no usable size, so no point was clicked.")
        x, y = self._surface.physical_point(*centre)
        self._surface.click_point(x, y)
        return ("target_verified=true", f"coords={x},{y}")

    def _type_with_pattern(self, element: Any, step: WorkflowStep) -> tuple[str, ...]:
        text = self._text_for(step)
        self._surface.set_text(element, text)
        readback = self._wait_for_readback(element, text)
        if not readback:
            raise ExecutionError("The control did not keep the text it was given.")
        self._last_readback = text
        return ("chars=" + str(len(text)), "readback_confirmed=true")

    def _type_with_keyboard(self, element: Any, step: WorkflowStep) -> tuple[str, ...]:
        text = self._text_for(step)
        self._focus_and_verify(element)
        self._surface.send_keys(element, "^a{BACKSPACE}")
        self._surface.send_keys(element, text)
        if not self._wait_for_readback(element, text):
            raise ExecutionError("The control did not keep the typed text.")
        self._last_readback = text
        return ("chars=" + str(len(text)), "readback_confirmed=true", "foreground_verified=true")

    def _send_shortcut(self, element: Any, step: WorkflowStep) -> tuple[str, ...]:
        keys = self._shortcut_keys(step)
        window = self._surface.window()
        self._focus_and_verify(window)
        self._surface.send_keys(window, keys)
        return ("keys=" + keys, "untargeted_injection=false")

    # --------------------------------------------------------------- helpers

    def _find(self, candidate: Candidate) -> Any:
        """Re-resolve the chosen candidate against the live window.

        Called before every attempt, so a retry can never act on a stale
        element: if the surface changed enough that the element is gone or no
        longer unique, the attempt is refused instead.
        """
        target = self._identity_of(candidate)
        try:
            window = self._surface.window()
            matches = [
                element
                for element in self._surface.descendants(window)
                if element_matches(element, target)
            ]
        except ExecutionError:
            raise
        if not matches:
            raise ExecutionError("The element is no longer on screen, so nothing was done.")
        if len(matches) > 1:
            raise ExecutionError(
                "More than one element now matches, so Once refused rather than guessing."
            )
        element = matches[0]
        if not self._surface.enabled(element):
            raise ExecutionError("The element is disabled, so the action was refused.")
        return element

    @staticmethod
    def _identity_of(candidate: Candidate) -> dict[str, str]:
        """The element fields the candidate was observed with, for re-resolution."""
        fields = {
            ClueKind.AUTOMATION_ID: "automation_id",
            ClueKind.ROLE: "control_type",
            ClueKind.NAME: "name",
        }
        target: dict[str, str] = {}
        for clue in candidate.clues:
            field = fields.get(clue.kind)
            if field is not None and clue.group.startswith("element.") and field not in target:
                target[field] = clue.value
        if "automation_id" not in target and "name" not in target:
            raise ExecutionError(
                "Once cannot identify that element again by anything but its place."
            )
        return target

    def _focus_and_verify(self, target: Any) -> None:
        """Focus the target and confirm it really is in front before sending keys."""
        self._surface.focus(target)
        if self._surface.foreground_handle() != self._surface.window_handle():
            raise ExecutionError(
                "Once could not bring the window to the front, so it sent no keys."
            )

    def _centre_or_none(self, element: Any) -> tuple[int, int] | None:
        try:
            rect = self._surface.rectangle(element)
        except ExecutionError:
            return None
        left, top, right, bottom = rect
        if right <= left or bottom <= top:
            return None
        return _rect_centre(rect)

    def _enabled(self, element: Any) -> bool:
        try:
            return self._surface.enabled(element)
        except ExecutionError:
            return False

    def _process_name(self) -> str | None:
        title = None
        try:
            title = self._surface.window_title()
        except ExecutionError:
            return None
        return title or None

    def _wait_for_readback(self, element: Any, text: str) -> bool:
        deadline = self._clock() + READBACK_TIMEOUT_SECONDS
        while True:
            try:
                current = self._surface.read_text(element)
            except ExecutionError:
                return False
            if current == text or (isinstance(current, str) and current.rstrip("\r\n") == text):
                return True
            if self._clock() >= deadline:
                return False
            self._sleep(0.05)

    @staticmethod
    def _text_for(step: WorkflowStep) -> str:
        try:
            target = json.loads(step.target)
        except (TypeError, ValueError) as error:
            raise ExecutionError("The step's text target is not valid JSON.") from error
        if not isinstance(target, dict) or not isinstance(target.get("text"), str):
            raise ExecutionError("The step does not carry the text to enter.")
        return target["text"]

    @staticmethod
    def _shortcut_keys(step: WorkflowStep) -> str:
        try:
            target = json.loads(step.target)
        except (TypeError, ValueError) as error:
            raise ExecutionError("The step's shortcut target is not valid JSON.") from error
        keys = str(target.get("keys", "")).strip().lower() if isinstance(target, dict) else ""
        code = SHORTCUT_CODES.get(keys)
        if code is None:
            raise ExecutionError(
                f"The shortcut {keys or '(empty)'} is not on the allowlist, so no keys were sent."
            )
        return code

    @staticmethod
    def _success_message(method: str, step: WorkflowStep) -> str:
        if step.kind is StepKind.CLICK_UI_ELEMENT:
            how = {
                "pattern": "through the control itself",
                "keyboard": "with the keyboard, after bringing the window to the front",
                "mouse_centre": "at the middle of the control",
            }[method]
            return f"{step.name} was done {how}."
        if step.kind is StepKind.TYPE_TEXT:
            return f"The text for {step.name} was entered and read back."
        return f"{step.name} was sent to the window only."


# -------------------------------------------------------------- real surface


class PywinautoSurface:
    """The real desktop, behind one narrow object (pywinauto imported lazily).

    Anything this class cannot do raises :class:`ExecutionError`; it never
    swallows an OS error and never invents a postcondition.
    """

    def __init__(
        self, target_json: str, *, desktop_factory: Callable[[], Any] | None = None
    ) -> None:
        self._target_json = target_json
        self._desktop_factory = desktop_factory or self._default_desktop
        self._window: Any | None = None

    @staticmethod
    def _default_desktop() -> Any:
        from pywinauto import Desktop

        return Desktop(backend="uia")

    def _identified(self) -> dict[str, Any]:
        from integrations.uia_targeting import window_matches  # local: same package

        try:
            target = json.loads(self._target_json)
        except (TypeError, ValueError) as error:
            raise ExecutionError("The step's window target is not valid JSON.") from error
        windows = [w for w in self._desktop_factory().windows() if window_matches(w, target)]
        if not windows:
            raise ExecutionError("The identified window was not found.")
        if len(windows) > 1:
            raise ExecutionError("The identified window is ambiguous.")
        self._window = windows[0]
        return target

    def window(self) -> Any:
        self._identified()
        return self._window

    def window_title(self) -> str:
        info = self.window().element_info
        return str(getattr(info, "name", "") or "")

    def descendants(self, window: Any) -> Sequence[Any]:
        return list(window.descendants())

    def info(self, element: Any) -> Any:
        return element.element_info

    def enabled(self, element: Any) -> bool:
        try:
            return bool(element.is_enabled())
        except (AttributeError, OSError, RuntimeError) as error:
            raise ExecutionError("The element state could not be read.") from error

    def rectangle(self, element: Any) -> tuple[int, int, int, int]:
        try:
            rect = element.rectangle()
        except (AttributeError, OSError, RuntimeError, ValueError) as error:
            raise ExecutionError("The element's position could not be read.") from error
        return (rect.left, rect.top, rect.right, rect.bottom)

    def supports_invoke(self, element: Any) -> bool:
        try:
            return getattr(element, "iface_invoke", None) is not None
        except (AttributeError, OSError, RuntimeError):
            return False

    def invoke(self, element: Any) -> None:
        try:
            element.iface_invoke.Invoke()
        except (AttributeError, OSError, RuntimeError) as error:
            raise ExecutionError("The control refused the pattern action.") from error

    def set_text(self, element: Any, text: str) -> None:
        try:
            element.iface_value.SetValue(text)
        except (AttributeError, OSError, RuntimeError) as error:
            raise ExecutionError(
                "The control does not accept text directly, so the keyboard was needed."
            ) from error

    def read_text(self, element: Any) -> str | None:
        try:
            return str(element.iface_value.CurrentValue)
        except (AttributeError, OSError, RuntimeError):
            return None

    def focus(self, target: Any) -> None:
        try:
            target.set_focus()
        except (AttributeError, OSError, RuntimeError) as error:
            raise ExecutionError("The window could not be brought to the front.") from error

    def send_keys(self, target: Any, keys: str) -> None:
        try:
            target.type_keys(keys, with_spaces=True)
        except (AttributeError, OSError, RuntimeError) as error:
            raise ExecutionError("The keys could not be delivered.") from error

    def click_point(self, x: int, y: int) -> None:
        try:
            import win32api
            import win32con

            win32api.SetCursorPos((x, y))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
        except (ImportError, OSError, AttributeError) as error:
            raise ExecutionError("The mouse click could not be sent.") from error

    def foreground_handle(self) -> int:
        try:
            import win32gui

            return int(win32gui.GetForegroundWindow() or 0)
        except (ImportError, OSError) as error:
            raise ExecutionError("The focused window could not be read.") from error

    def window_handle(self) -> int:
        try:
            return int(self.window().handle)
        except (AttributeError, OSError, RuntimeError) as error:
            raise ExecutionError("The window handle could not be read.") from error

    def physical_point(self, x: int, y: int) -> tuple[int, int]:
        """Convert a DPI-scaled point to physical pixels.

        UI Automation rectangles are already physical; a point that came from a
        screenshot or a scaled window is not. Scaling by the window's DPI keeps
        a click on the element at any display scale.
        """
        try:
            import win32gui

            dpi = 96
            try:
                dpi = int(win32gui.GetDpiForWindow(self.window_handle())) or 96
            except (AttributeError, OSError):
                dpi = 96
            if dpi == 96:
                return (x, y)
            scale = dpi / 96.0
            return (round(x * scale), round(y * scale))
        except (ImportError, OSError) as error:
            raise ExecutionError("The display scale could not be read.") from error
