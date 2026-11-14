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
