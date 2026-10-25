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


def element_matches(wrapper: Any, target: object) -> bool:
    """True when a descendant wrapper satisfies every requested element field."""
    if not isinstance(target, dict):
        return False
    info = wrapper.element_info
    if getattr(info, "automation_id", None) != target.get("automation_id"):
        return False
    if getattr(info, "control_type", None) != target.get("control_type"):
        return False
    return (
        "class_name" not in target
        or getattr(info, "class_name", None) == target["class_name"]
    )
