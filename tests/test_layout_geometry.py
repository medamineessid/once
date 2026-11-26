"""Objective geometry checks, so a defect does not need a human eye to catch.

Everything here works on widget geometry and rendered pixels offscreen. The
checks are written in a widget's own coordinates, so a scrolling page cannot
produce a false "sticks out" report for content that is simply scrolled away.

Two groups so far:

- a button's outermost edge must still be painted in its rest, hover and pressed
  states (the removed painted scale used to cut the border);
- a page may not show a child outside its parent, a non-wrapping label too
  narrow for its text, or a button that hangs outside its parent.

The full battery from the defect list (overlap between visible siblings, the
approval panel, the delete dialog, and the hero at six widths) is added with the
change it protects.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QEnterEvent, QImage, QMouseEvent, qAlpha
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from ui.components.buttons import ActionButton

#: Labels that deliberately run past their parent so the band crops a glyph.
CROP_ALLOWED = frozenset({"pageTitle", "heroLine", "heroLineAccent", "heroMicro"})
SIZES = ((960, 600), (1280, 820), (1920, 1020))


def _enter_event(widget: QWidget) -> QEnterEvent:
    centre = widget.rect().center()
    return QEnterEvent(
        centre.toPointF(),
        centre.toPointF(),
        centre.toPointF(),
    )


def _press_event(widget: QWidget) -> QMouseEvent:
    position = widget.rect().center().toPointF()
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        position,
        widget.mapToGlobal(position.toPoint()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _edge_midpoints(image: QImage) -> tuple[QPoint, ...]:
    width, height = image.width(), image.height()
    return (
        QPoint(width // 2, 0),
        QPoint(width // 2, height - 1),
        QPoint(0, height // 2),
        QPoint(width - 1, height // 2),
    )


@pytest.mark.parametrize("variant", ["primary", "secondary", "destructive"])
def test_action_button_paints_all_four_edges_in_every_state(qtbot, variant):
    button = ActionButton("Configure checker…", variant=variant)
    qtbot.addWidget(button)
    button.resize(220, 44)
    button.show()
    qtbot.wait(60)
    states = ("rest", "hover", "pressed")
    for state in states:
        if state == "hover":
            button.enterEvent(_enter_event(button))
        elif state == "pressed":
            button.mousePressEvent(_press_event(button))
        qtbot.wait(180)
        image = button.grab().toImage()
        for point in _edge_midpoints(image):
            assert qAlpha(image.pixel(point)) == 255, (
                f"{variant} {state}: edge pixel {point.x()},{point.y()} is not painted"
            )


def test_action_button_never_scales_its_paint():
    button = ActionButton("Run")
    assert not hasattr(button, "scale")
    assert not hasattr(button, "animate_scale")


def test_no_action_button_paints_outside_its_own_rectangle(qtbot):
    button = ActionButton("Build", variant="hero", with_arrow=True)
    qtbot.addWidget(button)
    button.resize(180, 44)
    button.show()
    qtbot.wait(60)
    button.enterEvent(_enter_event(button))
    button.mousePressEvent(_press_event(button))
    qtbot.wait(180)
    assert button.rect().contains(button._arrow_label.geometry())


def test_home_page_keeps_every_visible_child_inside_its_parent(qtbot):
    from ui.pages.home import HomePage

    page = HomePage()
    qtbot.addWidget(page)
    for width, height in SIZES:
        page.resize(width, height)
        page.show()
        qtbot.wait(80)
        for child in page.findChildren(QWidget):
            if not child.isVisible() or child.objectName() in CROP_ALLOWED:
                continue
            parent = child.parentWidget()
            if parent is None:
                continue
            allowed = parent.rect().adjusted(-1, -1, 1, 1)
            area = parent.parentWidget()
            if area is not None and hasattr(area, "viewport") and area.widget() is child:
                # A scroll body is meant to be taller than its viewport; only its
                # width has to fit, so the page never drifts sideways.
                assert child.width() <= allowed.width() + 2, (
                    f"home {width}x{height}: the scroll body is wider than the viewport"
                )
                continue
            assert allowed.contains(child.geometry()), (
                f"home {width}x{height}: {child.objectName() or type(child).__name__} "
                f"sticks out of {parent.objectName() or type(parent).__name__}"
            )


def test_home_page_labels_fit_their_text(qtbot):
    from ui.pages.home import HomePage

    page = HomePage()
    qtbot.addWidget(page)
    page.resize(960, 600)
    page.show()
    qtbot.wait(80)
    for label in page.findChildren(QLabel):
        if not label.isVisible() or label.wordWrap() or not label.text():
            continue
        if label.objectName() in CROP_ALLOWED:
            continue
        needed = label.fontMetrics().horizontalAdvance(label.text())
        assert needed <= label.width() + 2, (
            f"home: label {label.objectName() or label.text()!r} needs {needed}px, "
            f"has {label.width()}px"
        )


def test_home_page_buttons_are_inside_their_parent(qtbot):
    from ui.pages.home import HomePage

    page = HomePage()
    qtbot.addWidget(page)
    page.resize(960, 600)
    page.show()
    qtbot.wait(80)
    buttons = [child for child in page.findChildren(QPushButton) if child.isVisible()]
    assert buttons, "home page has no visible button"
    for button in buttons:
        parent = button.parentWidget()
        assert parent is not None
        assert parent.rect().adjusted(-1, -1, 1, 1).contains(button.geometry()), (
            f"home: button {button.text()!r} hangs outside its parent"
        )
