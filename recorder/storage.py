"""Local JSON recording storage with explicit deletion."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from engine.errors import WorkflowValidationError

from .models import RecordedEvent, RecordedEventKind, Recording, UIElementInfo
from .redaction import redact_events


class RecordingStore:
    """Persist redacted recording event logs below an explicit local directory."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)

    def save(self, recording: Recording) -> Path:
        """Redact and save one recording as UTF-8 JSON."""
        safe = Recording(
            recording.recording_id, recording.started_at_ns, redact_events(recording.events)
        )
        path = self._directory / f"{safe.recording_id}.json"
        payload = {
            "recording_id": safe.recording_id,
            "started_at_ns": safe.started_at_ns,
            "events": [asdict(event) for event in safe.events],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def load(self, recording_id: str) -> Recording:
        """Load one recording and reject malformed or unknown JSON."""
        path = self._directory / f"{recording_id}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            events = tuple(
                RecordedEvent(
                    sequence=item["sequence"],
                    timestamp_ns=item["timestamp_ns"],
                    kind=RecordedEventKind(item["kind"]),
                    window_title=item["window_title"],
                    element=(
                        UIElementInfo(**item["element"]) if item["element"] is not None else None
                    ),
                    x=item["x"],
                    y=item["y"],
                    key=item["key"],
                    text=item["text"],
                    screenshot_name=item["screenshot_name"],
                )
                for item in data["events"]
            )
            recording = Recording(data["recording_id"], data["started_at_ns"], events)
        except (
            KeyError,
            TypeError,
            ValueError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as error:
            raise WorkflowValidationError(f"Could not read recording: {path}.") from error
        if recording.recording_id != recording_id:
            raise WorkflowValidationError("Recording ID does not match its file name.")
        return recording

    def delete(self, recording_id: str) -> None:
        """Delete one explicitly selected local recording."""
        try:
            (self._directory / f"{recording_id}.json").unlink()
        except FileNotFoundError as error:
            raise WorkflowValidationError(f"Recording was not found: {recording_id}.") from error
