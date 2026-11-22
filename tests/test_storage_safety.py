"""Local persistence safety: confined recording paths and atomic saves."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowStep
from recorder.models import Recording
from recorder.storage import RecordingStore
from storage.workflows import save_workflow


def test_recording_ids_cannot_escape_the_recordings_folder(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("keep me", encoding="utf-8")
    store = RecordingStore(tmp_path / "recordings")

    with pytest.raises(WorkflowValidationError):
        store.save(Recording("../outside", 1, ()))
    with pytest.raises(WorkflowValidationError):
        store.load("../outside")
    with pytest.raises(WorkflowValidationError):
        store.delete("../outside")

    assert outside.read_text(encoding="utf-8") == "keep me"


def test_interrupted_workflow_save_keeps_the_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "workflow.json"
    path.write_text("previous workflow", encoding="utf-8")
    original_write = Path.write_text

    def partial_write(self: Path, data: str, *args, **kwargs) -> int:
        original_write(self, data[:10], *args, **kwargs)
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", partial_write)
    workflow = Workflow(
        "atomic-workflow",
        "Atomic workflow",
        (WorkflowStep("step-1", "Report", StepKind.REPORT, "Recorded"),),
    )

    with pytest.raises(WorkflowValidationError):
        save_workflow(workflow, path)

    assert path.read_text(encoding="utf-8") == "previous workflow"


def test_interrupted_recording_save_keeps_the_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RecordingStore(tmp_path)
    store.save(Recording("recording-1", 1, ()))
    path = tmp_path / "recording-1.json"
    previous = path.read_text(encoding="utf-8")
    original_write = Path.write_text

    def partial_write(self: Path, data: str, *args, **kwargs) -> int:
        original_write(self, data[:10], *args, **kwargs)
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", partial_write)

    with pytest.raises(WorkflowValidationError):
        store.save(Recording("recording-1", 2, ()))

    assert path.read_text(encoding="utf-8") == previous
