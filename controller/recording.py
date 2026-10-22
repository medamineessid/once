"""Controller service for explicit local recording sessions."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from threading import RLock

from integrations.recorder import EventSink, PynputRecorder
from recorder.models import RecordedEvent, Recording
from recorder.storage import RecordingStore


class RecordingService(EventSink):
    """Own recording lifecycle and persistence outside the Qt UI."""

    def __init__(
        self,
        directory: Path,
        *,
        recorder_factory: Callable[[EventSink], PynputRecorder] | None = None,
    ) -> None:
        self._store = RecordingStore(directory)
        self._recorder_factory = recorder_factory or PynputRecorder
        self._lock = RLock()
        self._events: list[RecordedEvent] = []
        self._recording_id: str | None = None
        self._started_at_ns: int | None = None
        self._recorder: PynputRecorder | None = None

    @property
    def recording(self) -> bool:
        """Return whether an explicit recording session is active."""
        return self._recorder is not None

    def start(self, recording_id: str) -> None:
        """Start a new local recording and reject concurrent sessions."""
        with self._lock:
            if self._recorder is not None:
                raise RuntimeError("A recording is already active.")
            self._events = []
            self._recording_id = recording_id
            self._started_at_ns = time.time_ns()
            self._recorder = self._recorder_factory(self)
            self._recorder.start()

    def stop(self) -> Recording:
        """Stop capture, redact, and persist the completed recording."""
        with self._lock:
            if self._recorder is None or self._recording_id is None:
                raise RuntimeError("No recording is active.")
            recorder = self._recorder
            recorder.stop()
            recording = Recording(
                self._recording_id,
                self._started_at_ns or time.time_ns(),
                tuple(self._events),
            )
            self._store.save(recording)
            self._recorder = None
            self._recording_id = None
            self._started_at_ns = None
            self._events = []
            return recording

    def append(self, event: RecordedEvent) -> None:
        """Receive one adapter event while a session is active."""
        with self._lock:
            if self._recorder is not None:
                self._events.append(event)

    def list_recordings(self) -> tuple[str, ...]:
        """List locally saved recordings without loading their contents."""
        return self._store.list_ids()

    def load(self, recording_id: str) -> Recording:
        """Load and validate one selected local recording."""
        return self._store.load(recording_id)

    def delete(self, recording_id: str) -> None:
        """Delete one explicitly selected local recording."""
        self._store.delete(recording_id)
