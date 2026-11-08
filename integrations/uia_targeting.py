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
    if "title" in target:
        expected = target["title"]
        actual = getattr(info, "name", None)
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False
        if actual != expected:
            clean_expected = expected.lstrip("*• ")
            clean_actual = actual.lstrip("*• ")
            if clean_actual != clean_expected and not (
                " - " in clean_expected
                and " - " in clean_actual
                and clean_actual.rsplit(" - ", 1)[-1] == clean_expected.rsplit(" - ", 1)[-1]
            ):
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
    for field in ("automation_id", "control_type", "class_name", "name"):
        if field in target and getattr(info, field, None) != target[field]:
            return False
    return True
