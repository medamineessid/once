"""Tests for local recording redaction, drafts, and storage."""

from __future__ import annotations

import json

import pytest

from engine.errors import WorkflowValidationError
from recorder.drafts import build_raw_draft
from recorder.models import RecordedEvent, RecordedEventKind, Recording, UIElementInfo
from recorder.storage import RecordingStore


def sample_recording() -> Recording:
    return Recording(
        "recording-1",
        100,
        (
            RecordedEvent(
                1,
                101,
                RecordedEventKind.TEXT_INPUT,
                element=UIElementInfo(control_type="Edit", is_password=True),
                text="secret",
                key="s",
            ),
            RecordedEvent(2, 102, RecordedEventKind.MOUSE_CLICK, x=10, y=20),
        ),
    )


def test_recording_store_redacts_password_data(tmp_path) -> None:
    path = RecordingStore(tmp_path).save(sample_recording())

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["events"][0]["text"] is None
    assert payload["events"][0]["key"] is None


def test_recording_round_trips_and_raw_draft_is_deterministic(tmp_path) -> None:
    store = RecordingStore(tmp_path)
    recording = sample_recording()
    store.save(recording)

    loaded = store.load("recording-1")
    draft = build_raw_draft(loaded)

    assert len(draft.actions) == 2
    assert draft.actions[0].description == "Text input observed."
    assert draft.actions[1].description == "Click at (10, 20)."


def test_recording_store_delete_is_explicit(tmp_path) -> None:
    store = RecordingStore(tmp_path)
    store.save(sample_recording())
    store.delete("recording-1")

    with pytest.raises(WorkflowValidationError):
        store.load("recording-1")
