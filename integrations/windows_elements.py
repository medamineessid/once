"""Best-effort Windows UI Automation metadata provider."""

from __future__ import annotations

from recorder.models import UIElementInfo


class PywinautoElementProvider:
    """Read metadata from the UI Automation element under the cursor."""

    def current(self) -> UIElementInfo | None:
        """Return metadata, or None when the target cannot be inspected."""
        try:
            import win32api
            from pywinauto import Desktop

            x, y = win32api.GetCursorPos()
            wrapper = Desktop(backend="uia").from_point(x, y)
            return UIElementInfo(
                automation_id=wrapper.element_info.automation_id or None,
                control_type=wrapper.element_info.control_type or None,
                name=wrapper.element_info.name or None,
                class_name=wrapper.element_info.class_name or None,
                is_password=bool(getattr(wrapper.element_info, "is_password", False)),
            )
        except AttributeError, ImportError, OSError, RuntimeError:
            return None
