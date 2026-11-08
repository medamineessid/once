"""Raw, non-runnable drafts derived from recorded observations."""

from __future__ import annotations

from dataclasses import dataclass

from .models import RecordedEvent, RecordedEventKind, Recording, UIElementInfo


@dataclass(frozen=True)
class RawDraftAction:
    """An observed action that still requires analysis and user approval."""

    sequence: int
    description: str
    source_event: RecordedEventKind
    process_name: str | None = None
    window_title: str | None = None
    executable_path: str | None = None
    executable_sha256: str | None = None
    element: UIElementInfo | None = None
    key: str | None = None
    text: str | None = None


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
            process_name=event.process_name,
            window_title=event.window_title,
            executable_path=event.executable_path,
            executable_sha256=event.executable_sha256,
            element=event.element,
            key=event.key,
            text=event.text,
        )
        for event in recording.events
    )
    return RawDraft(recording.recording_id, actions)


def _describe(event: RecordedEvent) -> str:
    if event.kind is RecordedEventKind.MOUSE_CLICK:
        if event.element is not None and event.window_title:
            label = (
                event.element.name
                or event.element.automation_id
                or event.element.class_name
                or "element"
            )
            ctrl = event.element.control_type or "UI element"
            return f"Click {ctrl} '{label}' in {event.window_title}."
        return f"Click at ({event.x}, {event.y})."
    if event.kind is RecordedEventKind.KEY_PRESS:
        if event.key and event.window_title:
            return f"Shortcut '{event.key}' pressed in {event.window_title}."
        return "Key press observed."
    if event.kind is RecordedEventKind.TEXT_INPUT:
        if event.text is None:
            return "Text input observed."
        if event.window_title:
            return f"Text input in {event.window_title}: '{event.text[:60]}'."
        return "Non-password text input observed."
    if event.kind is RecordedEventKind.WINDOW_OPEN:
        title = event.window_title or "untitled window"
        who = event.process_name or "an application"
        return f"A {who} window opened: {title}."
    if event.kind is RecordedEventKind.WINDOW_CLOSE:
        title = event.window_title or "untitled window"
        who = event.process_name or "an application"
        return f"The {who} window closed: {title}."
    return f"Window focus observed: {event.window_title or 'unknown window'}."
