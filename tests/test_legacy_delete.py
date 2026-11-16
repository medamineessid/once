"""Legacy-window destructive actions must confirm before deleting."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from controller.recording import RecordingService
from controller.service import WorkflowService
from recorder.models import Recording
from recorder.storage import RecordingStore
from ui.main_window import MainWindow


@pytest.fixture
def app(qtbot):
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_legacy_recording_delete_requires_confirmation(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings = tmp_path / "recordings"
    RecordingStore(recordings).save(Recording("legacy-recording", 1, ()))
    recording_path = recordings / "legacy-recording.json"
    service = WorkflowService()
    window = MainWindow(service, RecordingService(recordings))
    qtbot.addWidget(window)
    window._recording_list.clear()
    window._recording_list.addItem("legacy-recording")
    window._recording_list.setCurrentRow(0)
    prompts: list[object] = []

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(
            lambda *args, **kwargs: prompts.append(args) or QMessageBox.StandardButton.Cancel
        ),
    )
    window._delete_recording()

    assert prompts, "deleting a recording must ask first"
    assert recording_path.exists()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes),
    )
    window._delete_recording()

    assert not recording_path.exists()
    service.close()
