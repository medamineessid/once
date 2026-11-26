"""My automations: the list controls own a row above the list.

The page used to add the list first and the Preview / Clear drafts controls
after it, so at a narrow height the controls floated over the last row.

Without a service the page shows its empty state and hides the list, which is
why a naive geometry check measured zero-height widgets. This harness shows the
list, activates its parent's layout, and only then measures.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ui.pages.my_automations import MyAutomationsPage


def _laid_out_page(qtbot) -> MyAutomationsPage:
    """A 960x600 page with the list visible and its layout computed."""
    page = MyAutomationsPage()
    qtbot.addWidget(page)
    page.resize(960, 600)
    page.show()
    page._workflow_list.setVisible(True)
    page._empty_state.setVisible(False)
    body = page._workflow_list.parentWidget()
    assert isinstance(body, QWidget)
    body.layout().activate()
    qtbot.wait(100)
    return page


def test_the_toolbar_is_added_before_the_list(qtbot):
    page = _laid_out_page(qtbot)
    body = page._toolbar.parentWidget()
    assert body is not None
    layout = body.layout()
    assert layout.indexOf(page._toolbar) < layout.indexOf(page._workflow_list)


def test_the_toolbar_sits_above_the_list(qtbot):
    page = _laid_out_page(qtbot)
    assert page._toolbar.geometry().bottom() < page._workflow_list.geometry().top()


def test_the_toolbar_does_not_overlap_the_list(qtbot):
    page = _laid_out_page(qtbot)
    assert page._toolbar.geometry().intersected(page._workflow_list.geometry()).isEmpty()


def test_both_list_controls_are_above_the_list(qtbot):
    page = _laid_out_page(qtbot)
    body = page._workflow_list.parentWidget()
    list_top = page._workflow_list.geometry().top()
    for button in (page._preview_button, page._clear_drafts_button):
        bottom = button.mapTo(body, button.rect().bottomLeft()).y()
        assert bottom < list_top, f"{button.text()} is not above the list"


def test_the_list_keeps_a_usable_minimum_height(qtbot):
    page = MyAutomationsPage()
    qtbot.addWidget(page)
    assert page._workflow_list.minimumHeight() >= 200
