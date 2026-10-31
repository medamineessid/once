"""Golden auto-layout tests: exact float coordinates (P3, design 2.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.errors import WorkflowValidationError
from engine.workflow import StepKind, Workflow, WorkflowStep
from ui.editor.layout import (
    CARD_H,
    CARD_W,
    FINISH_ID,
    H_GAP,
    START_ID,
    TERMINAL_W,
    V_GAP,
    WRAP_DROP,
    auto_layout,
)


def workflow_with(steps: int) -> Workflow:
    return Workflow(
        workflow_id="layout-golden",
        name="Golden",
        steps=tuple(
            WorkflowStep(
                step_id=f"s{index}", name=f"Step {index}", kind=StepKind.REPORT, message=f"m{index}"
            )
            for index in range(1, steps + 1)
        ),
    )


def test_layout_rejects_malformed_saved_position():
    with pytest.raises(WorkflowValidationError):
        auto_layout(workflow_with(1), {"s1": {"x": 1.0}})


def test_layout_module_imports_no_qt():
    """ui/editor/layout.py must stay pure: no Qt imports, ever (design 2.3)."""
    source = Path("ui/editor/layout.py").read_text(encoding="utf-8")
    for forbidden in ("PySide6", "PyQt5", "PyQt6", "QtWidgets", "QtGui", "QtCore"):
        assert forbidden not in source


def test_layout_is_deterministic():
    workflow = workflow_with(3)
    saved = {"s2": (500.0, 400.0)}
    first = auto_layout(workflow, saved)
    second = auto_layout(workflow, saved)
    assert first.slots == second.slots
    assert first.edges == second.edges
    assert first.wrap_edges == second.wrap_edges


def test_golden_empty_workflow_single_row():
    plan = auto_layout(workflow_with(0))
    start = plan.slots[START_ID]
    finish = plan.slots[FINISH_ID]
    assert (start.x, start.y, start.w, start.h) == (0.0, 0.0, 88.0, 44.0)
    assert (finish.x, finish.y, finish.w, finish.h) == (88.0 + 56.0, 0.0, 88.0, 44.0)
    # One straight Start -> Finish edge; no wrap.
    assert len(plan.edges) == 1
    edge = plan.edges[0]
    assert edge.points == ((start.x + start.w, start.h / 2), (finish.x, finish.h / 2))
    assert edge.wrap is False
    assert plan.wrap_edges == frozenset()


def test_golden_one_step_exact_coordinates():
    plan = auto_layout(workflow_with(1))
    start = plan.slots[START_ID]
    s1 = plan.slots["s1"]
    finish = plan.slots[FINISH_ID]
    assert (s1.x, s1.y, s1.w, s1.h) == (TERMINAL_W + H_GAP, 0.0, CARD_W, CARD_H)
    assert (finish.x, finish.y) == (TERMINAL_W + H_GAP + CARD_W + H_GAP, 0.0)

    edge_start = plan.edges[0]
    assert edge_start.points == (
        (start.x + start.w, start.h / 2),
        (s1.x, s1.h / 2),
    )
    edge_finish = plan.edges[1]
    assert edge_finish.points == (
        (s1.x + CARD_W, CARD_H / 2),
        (finish.x, finish.h / 2),
    )
    assert not edge_start.wrap and not edge_finish.wrap


def test_golden_six_steps_single_row_including_terminals():
    """Six steps still fit one row: terminals do not count toward ROW_LIMIT."""
    plan = auto_layout(workflow_with(6))
    assert plan.wrap_edges == frozenset()
    xs = [plan.slots[f"s{index}"].x for index in range(1, 7)]
    assert xs == [144.0, 432.0, 720.0, 1008.0, 1296.0, 1584.0]
    finish = plan.slots[FINISH_ID]
    assert (finish.x, finish.y) == (1584.0 + CARD_W + H_GAP, 0.0)
    assert all(slot.y == 0.0 for slot in plan.slots.values())


def test_golden_eight_steps_wrap_row():
    plan = auto_layout(workflow_with(8))
    # Row 0: start + six step cards.
    assert plan.slots["s6"].x == 1584.0 and plan.slots["s6"].y == 0.0
    # Row 1 begins at the canvas left edge, one card + V_GAP lower.
    row1_y = CARD_H + V_GAP
    assert (plan.slots["s7"].x, plan.slots["s7"].y) == (0.0, row1_y)
    assert (plan.slots["s8"].x, plan.slots["s8"].y) == (CARD_W + H_GAP, row1_y)
    finish = plan.slots[FINISH_ID]
    assert (finish.x, finish.y) == (2.0 * (CARD_W + H_GAP), row1_y)

    wrap = plan.edges[6]  # s6 -> s7
    assert wrap.from_id == "s6" and wrap.to_id == "s7" and wrap.wrap is True
    start = (plan.slots["s6"].x + plan.slots["s6"].w / 2, plan.slots["s6"].y + CARD_H)
    channel_y = start[1] + WRAP_DROP
    port = (plan.slots["s7"].x, plan.slots["s7"].y + plan.slots["s7"].h / 2)
    assert wrap.points == (
        start,
        (start[0], channel_y),
        (port[0], channel_y),
        port,
    )
    assert plan.wrap_edges == frozenset({"s6"})


def test_saved_position_overrides_grid_for_that_node_only():
    plan = auto_layout(workflow_with(3), {"s2": (500.0, 400.0)})
    assert (plan.slots["s2"].x, plan.slots["s2"].y) == (500.0, 400.0)
    # Studio grid stays where the pure algorithm put it.
    assert plan.slots["s1"].x == 144.0
    assert plan.slots["s3"].x == 720.0
    assert plan.slots[FINISH_ID].x == 1008.0


def test_grid_slot_colliding_with_saved_is_nudged_down():
    """A grid node overlapping a saved node moves down by V_GAP, in chain order."""
    plan = auto_layout(workflow_with(2), {"s1": (0.0, 0.0)})
    # s1 keeps its saved spot on the start slot; Start (grid, no override)
    # yields and drops below it.
    assert (plan.slots["s1"].x, plan.slots["s1"].y) == (0.0, 0.0)
    assert (plan.slots[START_ID].x, plan.slots[START_ID].y) == (0.0, V_GAP)
    # Every non-saved member keeps its own grid slot here (Start occupies
    # the first slot, so s2 and Finish sit two and three slot-pitches out).
    assert (plan.slots["s2"].x, plan.slots["s2"].y) == (144.0 + CARD_W + H_GAP, 0.0)
    assert (plan.slots[FINISH_ID].x, plan.slots[FINISH_ID].y) == (
        144.0 + 2.0 * (CARD_W + H_GAP),
        0.0,
    )


def test_saved_record_af_style_monitoring_dict():
    """The P4 layout record shape {"x": float, "y": float} is accepted."""
    plan = auto_layout(workflow_with(1), {"s1": {"x": 12.0, "y": 34.0}})
    assert (plan.slots["s1"].x, plan.slots["s1"].y) == (12.0, 34.0)


def test_row_collision_moves_the_grid_member_down_one_gap():
    """Saved on a grid slot: that grid member drops exactly one V_GAP."""
    row1_y = CARD_H + V_GAP
    plan = auto_layout(workflow_with(8), {"s7": (CARD_W + H_GAP, row1_y)})
    assert plan.slots["s7"].y == row1_y
    assert plan.slots["s8"].y == row1_y + V_GAP
    assert plan.slots["s8"].x == CARD_W + H_GAP
