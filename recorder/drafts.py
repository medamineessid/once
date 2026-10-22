"""Raw, non-runnable drafts derived from recorded observations."""

from __future__ import annotations

from dataclasses import dataclass

from .models import RecordedEvent, RecordedEventKind, Recording


@dataclass(frozen=True)
class RawDraftAction:
    """An observed action that still requires analysis and user approval."""

    sequence: int
    description: str
    source_event: RecordedEventKind


@dataclass(frozen=True)
class RawDraft:
    """A deterministic observation summary, not an executable workflow."""

    recording_id: str
    actions: tuple[RawDraftAction, ...]


def build_raw_draft(recording: Recording) -> RawDraft:
    """Convert a redacted event log into a stable, reviewable raw draft."""
    actions = tuple(
        RawDraftAction(
            sequence=event.sequence,
            description=_describe(event),
            source_event=event.kind,
        )
        for event in recording.events
    )
    return RawDraft(recording.recording_id, actions)


def _describe(event: RecordedEvent) -> str:
    if event.kind is RecordedEventKind.MOUSE_CLICK:
        return f"Click at ({event.x}, {event.y})."
    if event.kind is RecordedEventKind.KEY_PRESS:
        return "Key press observed."
    if event.kind is RecordedEventKind.TEXT_INPUT:
        return "Text input observed." if event.text is None else "Non-password text input observed."
    return f"Window focus observed: {event.window_title or 'unknown window'}."
