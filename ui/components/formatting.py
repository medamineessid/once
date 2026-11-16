"""Presentation formatting shared by the activity, home, and editor pages.

These helpers are pure functions: no widget access, no time or locale
guesswork beyond an optional injected ``now`` so tests stay deterministic.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

#: Human labels and chip kinds for workflow run statuses.
_STATUS_DISPLAY: dict[str, tuple[str, str]] = {
    "SUCCEEDED": ("Succeeded", "ok"),
    "PARTIALLY_PERFORMED": ("Partly performed", "warn"),
    # A run that only looked and reported: finished, not an error (see
    # docs/contracts/run-outcomes.md).
    "OBSERVATION_ONLY": ("Observation only — nothing was performed", "neutral"),
    "FAILED": ("Failed", "fail"),
    "CANCELLED": ("Cancelled", "neutral"),
    "RUNNING": ("Running…", "warn"),
    "INTERRUPTED": ("Interrupted", "warn"),
    "COMPLETED": ("Completed", "ok"),
}


def status_display(raw: str, results: Iterable[object] | None = None) -> tuple[str, str]:
    """Return ``(human label, chip kind)`` for a raw run status string."""
    if raw == "PARTIALLY_PERFORMED" and results is not None:
        items = tuple(results)
        done = sum(
            1
            for r in items
            if getattr(getattr(r, "status", None), "value", "") in ("SUCCEEDED", "VERIFIED")
        )
        return (f"{done} of {len(items)} steps ran", "warn")
    return _STATUS_DISPLAY.get(raw, (raw or "Unknown", "neutral"))


def failure_reason(results: Iterable[object] | None) -> str:
    """Return a concise single-line failure reason from the first failed step."""
    if results is None:
        return ""
    for item in results:
        status_val = getattr(getattr(item, "status", None), "value", "")
        if status_val == "FAILED":
            msg = " ".join(str(getattr(item, "message", "") or "").split())
            if msg:
                return msg if len(msg) <= 120 else msg[:117] + "..."
    return ""


def friendly_run_name(service: object | None, workflow_id: str) -> str:
    """Return a human-readable automation name for a run, never a raw ID if avoidable."""
    if service is not None:
        saved_name = getattr(service, "workflow_name", lambda _wid: None)(workflow_id)
        if isinstance(saved_name, str) and saved_name.strip():
            return saved_name.strip()
    if workflow_id.startswith("recording-"):
        return "Recorded automation"
    return workflow_id


_ACTION_LABELS: dict[str, str] = {
    "LAUNCH_APPLICATION": "Open app",
    "CLOSE_APPLICATION": "Close app",
    "CLICK_UI_ELEMENT": "Click element",
    "TYPE_TEXT": "Type text",
    "PRESS_SHORTCUT": "Press shortcut",
    "WAIT_WINDOW": "Wait for window",
    "INSPECT_WINDOW": "Check window",
    "INSPECT_UI_ELEMENT": "Check element",
    "INSPECT_PATH": "Check file or folder",
    "VERIFY_PATH_EXISTS": "Verify file exists",
    "VERIFY_FILE_TEXT": "Verify file text",
    "LAUNCH_BROWSER": "Open browser",
    "NAVIGATE_BROWSER": "Go to page",
    "INSPECT_PAGE": "Check page",
    "FIND_PAGE_ELEMENT": "Find page element",
    "INTERACT_PAGE_ELEMENT": "Click page element",
    "WAIT_PAGE": "Wait for page",
    "REPORT": "Note",
    "FAIL": "Stop on error",
}

_DEBUG_SUFFIXES = (
    " (OS shell process ignored for application lifecycle)",
    " (Window title change observation; not an application close)",
    " (executable path not recorded)",
)


def friendly_action_label(kind_value: str) -> str:
    """Map an internal StepKind string to a plain-English action label."""
    return _ACTION_LABELS.get(kind_value, kind_value.replace("_", " ").capitalize())


def strip_observation_prefix(text: str) -> str:
    """Remove internal 'Observation N' / 'Observation N:' prefixes from copy."""
    import re

    cleaned = re.sub(r"^Observation\s+\d+\s*:?\s*", "", text.strip())
    return cleaned


def clean_step_message(message: str) -> str:
    """Remove internal debug suffixes and normalize single quotes to double quotes."""
    cleaned = message.strip()
    for suffix in _DEBUG_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].rstrip()
    # Show captured UI text in double quotes so it reads as data, not UI copy.
    import re

    cleaned = re.sub(r"'([^']+)'", r'"\1"', cleaned)
    return cleaned


def friendly_step_display(step: object) -> tuple[str, str, str]:
    """Return ``(friendly_title, action_label, clean_description)`` for a WorkflowStep."""
    import json
    from pathlib import Path

    kind_val = getattr(getattr(step, "kind", None), "value", str(getattr(step, "kind", "")))
    action_label = friendly_action_label(kind_val)
    raw_name = strip_observation_prefix(str(getattr(step, "name", "") or ""))
    raw_msg = clean_step_message(str(getattr(step, "message", "") or ""))
    target_raw = getattr(step, "target", None)

    title = raw_name
    if not title:
        if target_raw:
            try:
                target = json.loads(target_raw)
                if kind_val in ("LAUNCH_APPLICATION", "CLOSE_APPLICATION") and target.get(
                    "executable"
                ):
                    verb = "Open" if kind_val == "LAUNCH_APPLICATION" else "Close"
                    title = f'{verb} "{Path(target["executable"]).stem}"'
                elif kind_val == "CLICK_UI_ELEMENT" and isinstance(target.get("element"), dict):
                    elem = target["element"]
                    label = elem.get("name") or elem.get("automation_id") or "button"
                    title = f'Click "{label}"'
                elif kind_val == "TYPE_TEXT":
                    title = "Type text"
                elif kind_val == "PRESS_SHORTCUT" and target.get("keys"):
                    title = f'Press "{target["keys"]}"'
            except (TypeError, ValueError):
                pass
        if not title:
            title = raw_msg or action_label

    # Format Click/Close names so captured UI labels sit in quotes
    if title.startswith("Click ") and not title.startswith('Click "'):
        title = f'Click "{title[6:]}"'
    elif title.startswith("Close ") and not title.startswith('Close "'):
        title = f'Close "{title[6:]}"'

    return title, action_label, raw_msg


def run_status_display(run: object) -> tuple[str, str]:
    """Return ``(human label, chip kind)`` for a WorkflowRun object."""
    status_value = getattr(getattr(run, "status", None), "value", "Unknown")
    return status_display(status_value, getattr(run, "results", None))


def human_timestamp(value: datetime | None, now: datetime | None = None) -> str:
    """Render a timestamp for humans: "today at 10:04" or "01 Jan 2025, 09:30"."""
    if value is None:
        return ""
    local = value.astimezone()
    reference = (now or datetime.now()).astimezone().date()
    if local.date() == reference:
        return local.strftime("today at %H:%M")
    return local.strftime("%d %b %Y, %H:%M")


def friendly_or_id(name: str | None, workflow_id: str, today: date | None = None) -> str:
    """Prefer a workflow's saved name; fall back to its raw identifier."""
    cleaned = (name or "").strip()
    return cleaned if cleaned else workflow_id
