"""Read-only canvas view tests: the REAL scene draws the plan exactly (P3)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.editor.canvas import CanvasView
from ui.editor.layout import FINISH_ID, START_ID, auto_layout


def canvas_workflow(steps: int) -> Workflow:
    return Workflow(
        workflow_id="canvas-golden",
        name="Canvas golden",
        steps=tuple(
            WorkflowStep(
                step_id=f"s{index}",
                name=f"Step {index}",
                kind=StepKind.REPORT,
                message=f"m{index}",
            )
            for index in range(1, steps + 1)
        ),
    )


@pytest.fixture
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


@pytest.fixture
def canvas(qtbot, app):
    view = CanvasView()
    qtbot.addWidget(view)
    return view


def test_canvas_positions_match_plan_exactly(qtbot, canvas):
    workflow = canvas_workflow(2)
    plan = auto_layout(workflow)
    canvas.set_workflow(workflow)

    for member_id, slot in plan.slots.items():
        card = canvas.nodes[member_id]
        # The drawn polygon item sits at the plan's exact coordinates.
        assert card.slot == slot
        # The scene item itself sits at the plan's exact coordinates.
        assert (card.pos().x(), card.pos().y()) == (slot.x, slot.y)
    x1, y1, w1, h1 = (  # spot-check one exact golden slot (s2)
        plan.slots["s2"].x,
        plan.slots["s2"].y,
        plan.slots["s2"].w,
        plan.slots["s2"].h,
    )
    assert (x1, y1, w1, h1) == (144.0 + 288.0, 0.0, 232.0, 88.0)


def test_canvas_terminal_and_kind_labels(qtbot, canvas):
    workflow = canvas_workflow(1)
    canvas.set_workflow(workflow)
    assert canvas.nodes[START_ID].slot.w == 88.0
    assert canvas.nodes[FINISH_ID].slot.w == 88.0
    # Edge count: chain of 3 members -> 2 connectors, plus 2 arrowheads.
    assert len(canvas.edge_items) == 2


def test_canvas_scene_rect_covers_extents(qtbot, canvas):
    workflow = canvas_workflow(6)
    canvas.set_workflow(workflow)
    rect = canvas.scene().sceneRect()
    assert rect.width() >= 1872.0 + 88.0  # finish slot's right edge
    assert rect.bottom() >= 44.0


def test_canvas_wrap_workflow_renders_both_rows(qtbot, canvas):
    workflow = canvas_workflow(8)
    canvas.set_workflow(workflow)
    assert len(canvas.nodes) == 10  # start + 8 steps + finish
    assert len(canvas.edge_items) == 9
    # The wrap connector s6 -> s7 exists in the plan.
    plan = auto_layout(workflow)
    wrap_edges = [e for e in plan.edges if e.wrap]
    assert len(wrap_edges) == 1
    assert canvas.nodes["s7"].pos().y() == 88.0 + 96.0


def test_canvas_none_clears_the_scene(qtbot, canvas):
    canvas.set_workflow(canvas_workflow(1))
    assert canvas.nodes
    canvas.set_workflow(None)
    assert canvas.nodes == {}
    assert canvas.edge_items == []


def test_canvas_grab_renders_non_empty(qtbot, canvas):
    canvas.set_workflow(canvas_workflow(8))
    canvas.resize(1000, 500)
    canvas.show()
    qtbot.wait(30)
    pixmap = canvas.grab()
    assert not pixmap.isNull()
    assert pixmap.width() > 0 and pixmap.height() > 0


def test_review_page_canvas_renders_chain(qtbot, app):
    """Opening a workflow fills the read-only canvas AND keeps the list."""
    from ui.pages.review import ReviewPage

    page = ReviewPage()
    qtbot.addWidget(page)
    page.show_workflow(canvas_workflow(8))

    assert len(page._canvas.nodes) == 10  # start + 8 steps + finish
    assert page._steps_list.count() == 8
    page.show_workflow(None)
    assert page._canvas.nodes == {}
