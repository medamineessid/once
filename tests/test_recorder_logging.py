"""Recorder inspection failures must be visible in the log, never silent."""

from __future__ import annotations

import logging
import sys
from types import ModuleType

import pytest

from integrations.recorder import UIAElementProvider


class BrokenDesktop:
    def __init__(self, *args, **kwargs) -> None:
        raise RuntimeError("UI Automation is unavailable")


def test_point_inspection_failure_is_logged_and_recording_continues(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake_pywinauto = ModuleType("pywinauto")
    fake_pywinauto.Desktop = BrokenDesktop  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pywinauto", fake_pywinauto)
    provider = UIAElementProvider()

    with caplog.at_level(logging.WARNING, logger="integrations.recorder"):
        result = provider.inspect_point(10, 20)

    assert result == (None, None, None, None, False)
    assert "point inspection failed" in caplog.text.lower()
    assert "UI Automation is unavailable" in caplog.text
