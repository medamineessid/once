"""Read-only, identity-based Windows UI Automation actions."""

from __future__ import annotations

import json
from collections.abc import Callable

from engine.errors import ExecutionError


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
        windows = self._desktop_factory().windows()
        matches = [wrapper for wrapper in windows if self._matches(wrapper, target)]
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

    @staticmethod
    def _matches(wrapper: object, target: object) -> bool:
        if not isinstance(target, dict):
            return False
        info = wrapper.element_info
        if info.name != target.get("title"):
            return False
        for field, attribute in (
            ("process_id", "process_id"),
            ("class_name", "class_name"),
            ("automation_id", "automation_id"),
        ):
            if field in target and getattr(info, attribute, None) != target[field]:
                return False
        return True
