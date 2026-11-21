"""Shared UI Automation targeting helpers (single implementation for all providers).

These helpers compare pywinauto wrappers against validated identity targets.
Both the read-only inspector and the desktop-action provider use them so that
targeting cannot behave differently depending on which integration is running.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _normalize_title(title: str) -> str:
    """Normalize Unicode characters, whitespace, and dirty prefixes from a title."""
    normalized = unicodedata.normalize("NFKC", title).replace("\ufffd", "")
    return normalized.lstrip("*• ").strip()


def _trailing_title_segment(title: str) -> str:
    """Extract the rightmost application or window role segment of a title.

    Windows applications use different title separators depending on context:
    - Standard document/app: 'Untitled - Notepad' -> 'Notepad'
    - Multi-level / search: 'query - Search Results in Home : File Explorer' -> 'File Explorer'
    - Em-dash or pipe: 'Document — App' or 'Page | Service'
    """
    clean = _normalize_title(title)
    parts = [p.strip() for p in re.split(r"\s+[-:—|]\s+", clean) if p.strip()]
    return parts[-1] if parts else clean


def titles_share_application_suffix(actual: str, expected: str) -> bool:
    """True when two titles end in the same application segment.

    This is deliberately weak evidence ('Doc1 - Word' and 'Doc2 - Word' agree),
    so callers may only use it together with a stronger identity such as a
    process this run launched; it is never sufficient on its own.
    """
    expected_suffix = _trailing_title_segment(expected)
    actual_suffix = _trailing_title_segment(actual)
    return (
        len(expected_suffix) >= 2
        and len(actual_suffix) >= 2
        and expected_suffix.casefold() == actual_suffix.casefold()
    )


def window_matches(wrapper: Any, target: object, *, relaxed_title: bool = False) -> bool:
    """True when a top-level wrapper satisfies every requested window field.

    By default the title must be equal after Unicode normalisation and removal
    of an unsaved-changes marker ('*Untitled - Notepad' equals
    'Untitled - Notepad'). With ``relaxed_title`` only the trailing application
    segment must agree; the caller is responsible for restricting candidates to
    processes it launched, because a relaxed title alone is ambiguous.
    """
    if not isinstance(target, dict):
        return False
    info = wrapper.element_info
    if "title" in target:
        expected = target["title"]
        actual = getattr(info, "name", None)
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False
        if actual != expected:
            clean_expected = _normalize_title(expected)
            clean_actual = _normalize_title(actual)
            if clean_actual != clean_expected and not (
                relaxed_title and titles_share_application_suffix(clean_actual, clean_expected)
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
