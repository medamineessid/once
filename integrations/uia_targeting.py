"""Shared UI Automation targeting helpers (single implementation for all providers).

These helpers compare pywinauto wrappers against validated identity targets.
Both the read-only inspector and the desktop-action provider use them so that
targeting cannot behave differently depending on which integration is running.
"""

from __future__ import annotations

from typing import Any


def window_matches(wrapper: Any, target: object) -> bool:
    """True when a top-level wrapper satisfies every requested window field."""
    if not isinstance(target, dict):
        return False
    info = wrapper.element_info
    if "title" in target and info.name != target["title"]:
        return False
    for field, attribute in (
        ("process_id", "process_id"),
        ("class_name", "class_name"),
        ("automation_id", "automation_id"),
    ):
        if field in target and getattr(info, attribute, None) != target[field]:
            return False
    return True


def element_matches(wrapper: Any, target: object) -> bool:
    """True when a descendant wrapper satisfies every requested element field."""
    if not isinstance(target, dict):
        return False
    info = wrapper.element_info
    for field in ("automation_id", "control_type", "class_name"):
        if field in target and getattr(info, field, None) != target[field]:
            return False
    return True
