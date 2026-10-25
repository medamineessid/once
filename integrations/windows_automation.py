"""Read-only, identity-based Windows UI Automation actions."""

from __future__ import annotations

import json
from collections.abc import Callable

from engine.errors import ExecutionError
from integrations.uia_targeting import element_matches, window_matches


class PywinautoWindowInspector:
    """Resolve exactly one UI Automation window without focusing it."""

    def __init__(self, desktop_factory: Callable[[], object] | None = None) -> None:
        self._desktop_factory = desktop_factory or self._default_desktop

    @staticmethod
    def _default_desktop() -> object:
        from pywinauto import Desktop

        return Desktop(backend="uia")

    def inspect(self, target_json: str) -> tuple[str, ...]:
        """Return stable metadata or fail closed for missing/ambiguous targets."""
        try:
            target = json.loads(target_json)
        except json.JSONDecodeError as error:
            raise ExecutionError("The UI Automation target is not valid JSON.") from error
        matches = [
            wrapper for wrapper in self._desktop_factory().windows() if window_matches(wrapper, target)
        ]
        if not matches:
            raise ExecutionError("The identified window was not found.")
        if len(matches) > 1:
            raise ExecutionError("The identified window is ambiguous.")
        wrapper = matches[0]
        info = wrapper.element_info
        return (
            f"title={info.name}",
            f"process_id={getattr(info, 'process_id', None)}",
            f"class_name={getattr(info, 'class_name', None) or 'unknown'}",
            f"control_type={getattr(info, 'control_type', None) or 'unknown'}",
        )

    def inspect_element(self, target_json: str) -> tuple[str, ...]:
        """Inspect exactly one descendant of exactly one identified window."""
        try:
            target = json.loads(target_json)
        except json.JSONDecodeError as error:
            raise ExecutionError("The UI element target is not valid JSON.") from error
        if not isinstance(target, dict) or set(target) != {"window", "element"}:
            raise ExecutionError("The UI element target must identify a window and element.")
        windows = self._desktop_factory().windows()
        matches = [wrapper for wrapper in windows if window_matches(wrapper, target["window"])]
        if not matches:
            raise ExecutionError("The identified parent window was not found.")
        if len(matches) > 1:
            raise ExecutionError("The identified parent window is ambiguous.")
        parent = matches[0]
        element_matches_list = [
            wrapper
            for wrapper in parent.descendants()
            if element_matches(wrapper, target["element"])
        ]
        if not element_matches_list:
            raise ExecutionError("The identified UI element was not found.")
        if len(element_matches_list) > 1:
            raise ExecutionError("The identified UI element is ambiguous.")
        element = element_matches_list[0]
        info = element.element_info
        return (
            f"automation_id={getattr(info, 'automation_id', None) or 'unknown'}",
            f"control_type={getattr(info, 'control_type', None) or 'unknown'}",
            f"class_name={getattr(info, 'class_name', None) or 'unknown'}",
            f"enabled={self._enabled(element)}",
        )

    @staticmethod
    def _enabled(wrapper: object) -> bool:
        try:
            return bool(wrapper.is_enabled())
        except (AttributeError, OSError, RuntimeError) as error:
            raise ExecutionError("The UI element state could not be inspected.") from error
