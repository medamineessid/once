"""Tests for controller-owned recording lifecycle."""

from __future__ import annotations

import pytest

from controller.recording import RecordingService
from recorder.models import RecordedEvent, RecordedEventKind


class FakeRecorder:
    def __init__(self, sink) -> None:
        self.sink = sink
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True
        self.sink.append(RecordedEvent(1, 1, RecordedEventKind.MOUSE_CLICK, x=1, y=2))

    def stop(self) -> None:
        self.stopped = True


def test_recording_service_starts_stops_and_persists(tmp_path) -> None:
    service = RecordingService(tmp_path, recorder_factory=FakeRecorder)

    service.start("session-1")
    recording = service.stop()

    assert recording.recording_id == "session-1"
    assert len(recording.events) == 1
    assert (tmp_path / "session-1.json").exists()


def test_recording_service_rejects_concurrent_or_missing_sessions(tmp_path) -> None:
    service = RecordingService(tmp_path, recorder_factory=FakeRecorder)

    with pytest.raises(RuntimeError, match="No recording"):
        service.stop()
    service.start("session-1")
    with pytest.raises(RuntimeError, match="already active"):
        service.start("session-2")
    service.stop()
