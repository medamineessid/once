"""Each audit check must catch a deliberately broken widget, or it is useless.

Every test builds a tiny widget tree rather than the real window, so a failure
names the check that stopped working. The last test keeps ``docs/UI_SPEC.md``
and ``scripts/ui_spec.py`` in step.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import ui_audit  # noqa: E402
import ui_spec  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    application = QApplication.instance() or QApplication([])
    yield application


def _window(qt_app, width: int = 400, height: int = 300) -> QWidget:
    window = QWidget()
    window.resize(width, height)
    window.show()
    qt_app.processEvents()
    return window


def test_contrast_ratio_spans_the_full_range() -> None:
    assert ui_audit.contrast_ratio(QColor("white"), QColor("black")) == pytest.approx(
        21.0, rel=0.01
    )
    assert ui_audit.contrast_ratio(QColor("white"), QColor("white")) == pytest.approx(1.0)


def test_check_a_flags_a_label_that_leaves_its_parent(qt_app) -> None:
    window = _window(qt_app)
    frame = QFrame(window)
    frame.setObjectName("brokenFrame")
    frame.setGeometry(0, 0, 200, 100)
    label = QLabel("outside", frame)
    label.setObjectName("brokenLabel")
    label.setGeometry(250, 10, 60, 20)
    findings: list = []
    ui_audit.check_containment(window, "page", "state", 100, "400x300", findings)
    assert [finding.check for finding in findings] == ["a-contains"]
    assert findings[0].widget == "brokenLabel"


def test_check_b_flags_two_overlapping_siblings(qt_app) -> None:
    window = _window(qt_app)
    holder = QWidget(window)
    holder.setGeometry(0, 0, 300, 100)
    first = QLabel("first", holder)
    first.setObjectName("firstLabel")
    first.setGeometry(0, 0, 100, 30)
    second = QLabel("second", holder)
    second.setObjectName("secondLabel")
    second.setGeometry(20, 10, 100, 30)
    findings: list = []
    ui_audit.check_overlap(window, "page", "state", 100, "400x300", findings)
    assert any(finding.check == "b-overlap" for finding in findings)


def test_check_b_accepts_a_parent_and_its_child(qt_app) -> None:
    window = _window(qt_app)
    card = QFrame(window)
    card.setObjectName("card")
    card.setGeometry(10, 10, 200, 100)
    inside = QLabel("inside", card)
    inside.setObjectName("insideLabel")
    inside.setGeometry(5, 5, 100, 20)
    findings: list = []
    ui_audit.check_overlap(window, "page", "state", 100, "400x300", findings)
    assert findings == []


def test_check_c_flags_clipped_text(qt_app) -> None:
    window = _window(qt_app)
    label = QLabel("a very long sentence that cannot fit", window)
    label.setObjectName("clippedLabel")
    label.setGeometry(0, 0, 40, 14)
    findings: list = []
    ui_audit.check_text_clipped(window, "page", "state", 100, "400x300", findings)
    assert [finding.check for finding in findings] == ["c-clipped"]


def test_check_d_flags_low_contrast_button_text(qt_app) -> None:
    window = _window(qt_app)
    button = QPushButton("Invisible", window)
    button.setObjectName("lowContrastButton")
    button.setGeometry(0, 0, 120, 32)
    button.setStyleSheet("background: #111111; color: #121212; border: none;")
    qt_app.processEvents()
    findings: list = []
    ui_audit.check_buttons(window, "page", "state", 100, "400x300", findings)
    assert any(finding.check == "d-contrast" for finding in findings)


def test_check_d_flags_an_outlined_button_without_a_border(qt_app) -> None:
    window = _window(qt_app)
    button = QPushButton("Borderless", window)
    button.setObjectName("borderlessButton")
    button.setProperty("variant", "secondary")
    button.setGeometry(0, 0, 140, 32)
    button.setStyleSheet("background: #ffffff; color: #111111; border: none;")
    qt_app.processEvents()
    findings: list = []
    ui_audit.check_buttons(window, "page", "state", 100, "400x300", findings)
    borders = [finding for finding in findings if finding.check == "d-border"]
    assert len(borders) == 4


def test_check_e_flags_a_missing_required_element(qt_app) -> None:
    window = _window(qt_app)
    findings: list = []
    ui_audit.check_required(window, "delete_dialog", "state", 100, "400x300", findings)
    missing = {finding.widget for finding in findings if finding.detail == "missing"}
    assert "deleteConfirmDialog" in missing


def test_check_f_flags_a_button_that_grows_on_hover(qt_app) -> None:
    class GrowingButton(QPushButton):
        def enterEvent(self, event) -> None:  # noqa: N802 - Qt name
            self.resize(self.width() + 40, self.height())
            super().enterEvent(event)

    window = _window(qt_app)
    holder = QWidget(window)
    holder.setGeometry(0, 0, 300, 120)
    button = GrowingButton("Grow", holder)
    button.setObjectName("growingButton")
    button.setGeometry(10, 10, 100, 32)
    qt_app.processEvents()
    findings: list = []
    ui_audit.check_animation(window, "page", "state", 100, "400x300", findings, qt_app)
    assert any(finding.check == "f-animation" for finding in findings)


def test_spec_names_appear_in_the_document() -> None:
    document = (Path(__file__).resolve().parents[1] / "docs" / "UI_SPEC.md").read_text(
        encoding="utf-8"
    )
    for names in ui_spec.REQUIRED.values():
        for name in names:
            assert f"`{name}`" in document, f"{name} is not documented in docs/UI_SPEC.md"
