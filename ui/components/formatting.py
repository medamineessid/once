"""Presentation formatting shared by the activity, home, and editor pages.

These helpers are pure functions: no widget access, no time or locale
guesswork beyond an optional injected ``now`` so tests stay deterministic.
"""

from __future__ import annotations

from datetime import date, datetime

#: Human labels and chip kinds for workflow run statuses.
_STATUS_DISPLAY: dict[str, tuple[str, str]] = {
    "SUCCEEDED": ("Succeeded", "ok"),
    "FAILED": ("Failed", "fail"),
    "CANCELLED": ("Cancelled", "neutral"),
    "RUNNING": ("Running…", "warn"),
    "INTERRUPTED": ("Interrupted", "warn"),
    "COMPLETED": ("Completed", "ok"),
}


def status_display(raw: str) -> tuple[str, str]:
    """Return ``(human label, chip kind)`` for a raw run status string."""
    return _STATUS_DISPLAY.get(raw, (raw or "Unknown", "neutral"))


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
