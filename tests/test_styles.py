"""Qt must not report unknown properties in the Once stylesheet.

Qt's style-sheet parser ignores properties it does not understand and prints
"Unknown property <name>" through its message handler, so a shadow written in
CSS terms simply never draws. These tests capture that output while the real
theme is applied and fail on any unknown property; one test proves the capture
itself can fail.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from PySide6 import QtCore
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.styles import apply_theme

# Every widget class the theme styles, so each rule is actually parsed.
_SELECTOR_CLASSES = {
    "QWidget": QWidget,
    "QMainWindow": QMainWindow,
    "QToolBar": QToolBar,
    "QToolButton": QToolButton,
    "QLabel": QLabel,
    "QFrame": QFrame,
    "QGroupBox": QGroupBox,
    "QScrollArea": QScrollArea,
    "QPushButton": QPushButton,
    "QLineEdit": QLineEdit,
    "QTextEdit": QTextEdit,
    "QListWidget": QListWidget,
}

_SELECTOR_PAIR = re.compile(r"([A-Za-z]+)#([A-Za-z0-9_]+)")


@pytest.fixture
def qt_messages() -> Iterator[list[str]]:
    """Collect every Qt message emitted while the fixture is active."""
    captured: list[str] = []

    def _handler(_msg_type, _context, message: str) -> None:
        captured.append(str(message))

    previous = QtCore.qInstallMessageHandler(_handler)
    try:
        yield captured
    finally:
        QtCore.qInstallMessageHandler(previous)


def test_qt_reports_no_unknown_property_for_the_Once_theme(qtbot, qt_messages):
    """Apply the whole theme to a widget for every selector it declares."""
    app = QApplication.instance() or QApplication([])
    apply_theme(app)

    selectors = sorted(_SELECTOR_PAIR.findall(app.styleSheet()))
    assert selectors, "the theme stylesheet is empty; the test would prove nothing"

    host = QWidget()
    host.setObjectName("themeHost")
    layout = QVBoxLayout(host)
    made = 0
    for class_name, object_name in selectors:
        widget_class = _SELECTOR_CLASSES.get(class_name)
        if widget_class is None:
            raise AssertionError(f"unknown selector class in theme: {class_name}")
        child = widget_class(host)
        child.setObjectName(object_name)
        layout.addWidget(child)
        made += 1
    assert made == len(selectors)

    host.show()
    app.processEvents()
    qtbot.addWidget(host)

    unknown = [message for message in qt_messages if "Unknown property" in message]
    assert unknown == [], f"Qt ignored stylesheet properties: {unknown}"


def test_the_capture_detects_an_unknown_property(qtbot, qt_messages):
    """Prove the detector can fail: a CSS-only property must be reported."""
    app = QApplication.instance() or QApplication([])

    widget = QWidget()
    widget.setObjectName("brokenCard")
    widget.setStyleSheet("QWidget#brokenCard { box-shadow: 0 1px 3px rgba(0, 0, 0, 0.5); }")
    widget.show()
    app.processEvents()
    qtbot.addWidget(widget)

    unknown = [message for message in qt_messages if "Unknown property" in message]
    assert unknown, "Qt accepted box-shadow, so the capture proves nothing"
